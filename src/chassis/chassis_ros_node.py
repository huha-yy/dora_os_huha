#!/usr/bin/env python3
"""
底盘 ROS 2 节点 — 桥接 /cmd_vel 和 ST3215 舵机

订阅 /cmd_vel (geometry_msgs/Twist) → 全向轮运动学 → 串口 → ST3215
读取舵机编码器 → 计算里程计 → 发布 /odom (nav_msgs/Odometry)

服用 omni_wheel.py 的运动学公式和串口协议, 输入来源从"手柄"换为"ROS 话题",
新增里程计输出供导航使用。
"""
import math
import time
import logging

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from std_msgs.msg import Header
from geometry_msgs.msg import Pose, Point, Quaternion, Twist as OdometryTwist, Vector3, TransformStamped
from tf2_ros import TransformBroadcaster

# ── 串口通信 (优先 scservo_sdk, 回退至 pyserial) ──────────────────────
try:
    from scservo_sdk import *
    _HAS_SCSERVO = True
except ImportError:
    _HAS_SCSERVO = False
    import serial

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("chassis_node")


# ==========================================================================
#                       用 户 配 置 (按实际接线修改)
# ==========================================================================

DEVICE          = "/dev/ttyUSB0"   # RS-485 串口号
BAUDRATE        = 1000000          # 波特率 (ST3215 默认 1Mbps)
MAX_SPEED       = 3600             # 最大速度 (0~4095)
ACC             = 50               # 加速度

# 舵机 ID 与安装角度 (与 omni_wheel.py 保持一致)
WHEEL_MAP = {
    3: math.radians(90),    # 正前方
    1: math.radians(330),   # 左后方
    2: math.radians(210),   # 右后方
}
WHEEL_IDS = [1, 2, 3]

L = 1.0                           # 旋转增益
WHEEL_RADIUS    = 0.05            # 轮子半径 (米)
ENCODER_RES     = 4096            # 编码器分辨率 (一圈的脉冲数)
GEAR_RATIO      = 1.0             # 减速比 (直驱=1)

# 里程计参数
ODOM_FRAME      = "odom"
BASE_FRAME      = "base_link"


# ==========================================================================
#                       串 口 通 信 层
# ==========================================================================

class ServoBus:
    """ST3215 串口总线 (支持 scservo_sdk 或 pyserial 回退)"""

    def __init__(self, device: str, baudrate: int):
        self.device = device
        self.baudrate = baudrate
        self._sdk = _HAS_SCSERVO
        self._open()

    def _open(self):
        if self._sdk:
            self._port = PortHandler(self.device)
            self._pkt = sms_sts(self._port)
            if not self._port.openPort():
                raise IOError(f"打开串口失败: {self.device}")
            self._port.setBaudRate(self.baudrate)
        else:
            self._ser = serial.Serial(self.device, self.baudrate, timeout=0.05)

    def close(self):
        if self._sdk:
            self._port.closePort()
        else:
            self._ser.close()

    def wheel_mode(self, sid: int):
        """切换轮子模式 (连续旋转)"""
        if self._sdk:
            self._pkt.WheelMode(sid)
        else:
            # SMS_STS 协议: 写 MODE=1 到地址 33
            self._write1(sid, 33, 1)

    def unlock_eprom(self, sid: int):
        """解锁 EEPROM"""
        if self._sdk:
            self._pkt.unLockEprom(sid)

    def torque_enable(self, sid: int):
        """使能扭矩"""
        if self._sdk:
            self._pkt.write1ByteTxRx(sid, SMS_STS_TORQUE_ENABLE, 1)
        else:
            self._write1(sid, 40, 1)  # TORQUE_ENABLE 地址

    def write_speed(self, sid: int, speed: int, acc: int):
        """写速度指令 (-4095 ~ 4095)"""
        if self._sdk:
            self._pkt.WriteSpec(sid, speed, acc)
        else:
            # 简化: 直接写速度寄存器
            speed = max(-4095, min(4095, speed))
            direction = 1 if speed >= 0 else 0
            abs_speed = abs(speed)
            self._write2(sid, 46, abs_speed & 0xFF, (abs_speed >> 8) & 0xFF)  # GOAL_SPEED
            self._write1(sid, 40, 1)  # 使能

    def read_position(self, sid: int) -> int:
        """读当前位置 (0~4095)"""
        if self._sdk:
            pos, _, _ = self._pkt.ReadPos(sid)
            return pos
        else:
            return self._read2(sid, 56)  # PRESENT_POSITION

    # ── 底层协议辅助 ──
    def _checksum(self, buf):
        return (~sum(buf)) & 0xFF

    def _send(self, sid: int, instruction: int, params: list):
        """发送 SMS_STS 指令包"""
        length = len(params) + 2
        pkt = [0xFF, 0xFF, sid & 0xFF, length, instruction] + params
        ck = self._checksum(pkt[2:])
        pkt.append(ck)
        self._ser.write(bytes(pkt))
        self._ser.flush()

    def _write1(self, sid: int, addr: int, val: int):
        self._send(sid, 0x03, [addr, val])

    def _write2(self, sid: int, addr: int, lo: int, hi: int):
        self._send(sid, 0x03, [addr, lo, hi])

    def _read2(self, sid: int, addr: int) -> int:
        self._send(sid, 0x02, [addr, 2])
        resp = self._ser.read(8)
        if len(resp) < 8:
            return 0
        return resp[5] | (resp[6] << 8)


# ==========================================================================
#                       全 向 轮 运 动 学
# ==========================================================================

def compute_wheel_speeds(vx: float, vy: float, omega: float) -> dict:
    """三轮全向轮逆运动学: v = -sin(θ)*Vx + cos(θ)*Vy + L*ω"""
    speeds = {}
    for sid in WHEEL_IDS:
        theta = WHEEL_MAP[sid]
        v = -math.sin(theta) * vx + math.cos(theta) * vy + L * omega
        speeds[sid] = v
    return speeds


def wheel_speeds_to_odom(wheel_deltas: dict, dt: float) -> tuple:
    """
    全向轮正运动学: 从三个轮子的位移 → 机器人位移 (dx, dy, dtheta)
    wheel_deltas: {id: 本次周期内轮子转过的圈数}
    返回 (dx, dy, dtheta) 机器人坐标系下的位移
    """
    # 三轮全向轮: 三个轮子方向互相 120°
    # 简化: 直接用三个已安装角度的逆解
    dx, dy, dtheta = 0.0, 0.0, 0.0
    n = 0
    for sid in WHEEL_IDS:
        theta = WHEEL_MAP[sid]
        d = wheel_deltas.get(sid, 0.0)  # 轮子转过的圈数 * 周长 = 位移
        dist = d * 2 * math.pi * WHEEL_RADIUS
        # 每个轮子的位移在机器人坐标系下的投影
        dx += dist * math.cos(theta)
        dy += dist * math.sin(theta)
        dtheta += dist / L
        n += 1
    if n > 0:
        dx /= n
        dy /= n
        dtheta /= n
    return dx, dy, dtheta


# ==========================================================================
#                       ROS 2 节 点
# ==========================================================================

class ChassisNode(Node):
    """底盘控制 ROS 节点"""

    def __init__(self):
        super().__init__("chassis_node")

        # ── 参数 ──
        self.declare_parameter("device", DEVICE)
        self.declare_parameter("baudrate", BAUDRATE)
        self.declare_parameter("max_speed", MAX_SPEED)
        self.declare_parameter("acc", ACC)
        self.declare_parameter("wheel_radius", WHEEL_RADIUS)
        self.declare_parameter("encoder_res", ENCODER_RES)
        self.declare_parameter("publish_odom_tf", True)

        device = self.get_parameter("device").value
        baudrate = self.get_parameter("baudrate").value
        self.max_speed = self.get_parameter("max_speed").value
        self.acc = self.get_parameter("acc").value
        self.wheel_radius = self.get_parameter("wheel_radius").value
        self.encoder_res = self.get_parameter("encoder_res").value
        self.publish_tf = self.get_parameter("publish_odom_tf").value

        # ── 串口 ──
        self.get_logger().info(f"连接舵机总线: {device} @ {baudrate}")
        self.bus = ServoBus(device, baudrate)

        # ── 初始化舵机 ──
        self._init_servos()

        # ── ROS 接口 ──
        self.cmd_sub = self.create_subscription(
            Twist, "/cmd_vel", self._cmd_callback, 10
        )
        self.odom_pub = self.create_publisher(Odometry, "/odom", 10)
        self.tf_broadcaster = TransformBroadcaster(self)

        # ── 里程计状态 ──
        self._last_pos = {sid: 0 for sid in WHEEL_IDS}
        self._x = 0.0
        self._y = 0.0
        self._theta = 0.0
        self._last_time = self.get_clock().now()

        # 先读一次初始位置
        for sid in WHEEL_IDS:
            pos = self.bus.read_position(sid)
            self._last_pos[sid] = pos

        # ── 定时器: 50Hz 控制+里程计 ──
        self._timer = self.create_timer(0.02, self._control_loop)
        self._current_vx = 0.0
        self._current_vy = 0.0
        self._current_omega = 0.0

        self.get_logger().info("底盘节点启动完成")

    def _init_servos(self):
        """初始化所有舵机: 解锁 → 轮子模式 → 使能扭矩"""
        for sid in WHEEL_IDS:
            self.bus.unlock_eprom(sid)
            self.bus.wheel_mode(sid)
            self.bus.torque_enable(sid)
            self.get_logger().info(f"舵机 [ID:{sid}] 初始化完成")

    def _cmd_callback(self, msg: Twist):
        """接收 /cmd_vel"""
        self._current_vx = msg.linear.x
        self._current_vy = msg.linear.y
        self._current_omega = msg.angular.z

    def _control_loop(self):
        """50Hz 主循环: 发送速度 + 读取编码器 + 发布里程计"""
        now = self.get_clock().now()
        dt = (now - self._last_time).nanoseconds / 1e9
        if dt <= 0:
            dt = 0.02
        self._last_time = now

        # ── 1. 发送速度到舵机 ──
        vx = self._current_vx
        vy = self._current_vy
        omega = self._current_omega
        speeds = compute_wheel_speeds(vx, vy, omega)

        max_abs = max(max(abs(v) for v in speeds.values()), 1e-6)
        scale = min(1.0, 1.0 / max_abs)
        for sid in WHEEL_IDS:
            raw = int(speeds[sid] * self.max_speed * scale)
            raw = max(-4095, min(4095, raw))
            self.bus.write_speed(sid, raw, self.acc)

        # ── 2. 读编码器, 算里程计 ──
        wheel_deltas = {}
        for sid in WHEEL_IDS:
            pos = self.bus.read_position(sid)
            delta = pos - self._last_pos[sid]
            # 处理编码器溢出 (0→4095 或 4095→0)
            if delta > self.encoder_res / 2:
                delta -= self.encoder_res
            elif delta < -self.encoder_res / 2:
                delta += self.encoder_res
            wheel_deltas[sid] = delta / self.encoder_res  # 圈数
            self._last_pos[sid] = pos

        dx, dy, dtheta = wheel_speeds_to_odom(wheel_deltas, dt)

        # 世界坐标系下积分
        self._x += dx * math.cos(self._theta) - dy * math.sin(self._theta)
        self._y += dx * math.sin(self._theta) + dy * math.cos(self._theta)
        self._theta += dtheta

        # ── 3. 发布 /odom ──
        odom = Odometry()
        odom.header = Header(stamp=now.to_msg(), frame_id=ODOM_FRAME)
        odom.child_frame_id = BASE_FRAME
        odom.pose.pose = Pose(
            position=Point(x=self._x, y=self._y, z=0.0),
            orientation=Quaternion(
                x=0.0, y=0.0,
                z=math.sin(self._theta / 2.0),
                w=math.cos(self._theta / 2.0),
            ),
        )
        odom.twist.twist = OdometryTwist(
            linear=Vector3(x=vx, y=vy, z=0.0),
            angular=Vector3(x=0.0, y=0.0, z=omega),
        )
        self.odom_pub.publish(odom)

        # ── 4. 发布 TF ──
        if self.publish_tf:
            t = TransformStamped()
            t.header = odom.header
            t.child_frame_id = BASE_FRAME
            t.transform.translation.x = self._x
            t.transform.translation.y = self._y
            t.transform.rotation = odom.pose.pose.orientation
            self.tf_broadcaster.sendTransform(t)

    def stop(self):
        """安全停止所有舵机"""
        for sid in WHEEL_IDS:
            self.bus.write_speed(sid, 0, self.acc)
        self.get_logger().info("所有舵机已停止")

    def destroy_node(self):
        self.stop()
        self.bus.close()
        super().destroy_node()


# ==========================================================================
#                       入 口
# ==========================================================================

def main():
    rclpy.init()
    node = ChassisNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
