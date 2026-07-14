#!/usr/bin/env python3
"""
手臂舵机 ROS2 节点
独立串口, 订阅 /arm_cmd → 执行预设动作/单舵机控制
"""
import os, sys, time
sys.path.insert(0, os.path.expanduser("~/ST32XX"))

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

# ── 串口 ──
try:
    from scservo_sdk import *
    _HAS_SCSERVO = True
except ImportError:
    _HAS_SCSERVO = False
    import serial

# ── 配置 ──
DEVICE   = "/dev/ttyACM1"   # 手臂独立串口
BAUDRATE = 1000000
SPEED    = 2400
ACC      = 50

ARM_IDS  = [6, 7, 8, 9, 10, 11, 12, 13]

# 预设动作 (Windows 实测)
PRESETS = {
    "home":       {6:1, 7:39, 8:2680, 9:1389, 10:3764, 11:1088, 12:2656, 13:1551},
    "hug":        {6:231,7:3409,8:2790,9:196,10:3766,11:1873,12:2529,13:2770},
    "raise_right":{6:230,7:3402,8:2683,9:43,10:3765,11:2133,12:2656,13:1651},
    "raise_left": {6:232,7:3037,8:2685,9:1340,10:3765,11:1605,12:2658,13:2675},
}

# ── 串口层 ──
class ServoBus:
    def __init__(self, device, baudrate):
        self._sdk = _HAS_SCSERVO
        if self._sdk:
            self._port = PortHandler(device)
            self._pkt = sms_sts(self._port)
            if not self._port.openPort():
                raise IOError(f"打开串口失败: {device}")
            self._port.setBaudRate(baudrate)
        else:
            self._ser = serial.Serial(device, baudrate, timeout=0.05)

    def close(self):
        if self._sdk: self._port.closePort()
        else: self._ser.close()

    def init_servo(self, sid):
        if self._sdk:
            self._pkt.write1ByteTxRx(sid, 33, 0)           # 位置模式
            self._pkt.write1ByteTxRx(sid, SMS_STS_TORQUE_ENABLE, 1)

    def write_pos(self, sid, pos, speed=2400, acc=50):
        if self._sdk:
            self._pkt.WritePosEx(sid, pos, speed, acc)

    def read_pos(self, sid):
        if self._sdk:
            p, r, _ = self._pkt.ReadPos(sid)
            return p if r == COMM_SUCCESS else 0
        return 0


class ArmNode(Node):
    def __init__(self):
        super().__init__("arm_node")

        device = self.declare_parameter("device", DEVICE).value
        baud = self.declare_parameter("baudrate", BAUDRATE).value

        self.get_logger().info(f"手臂串口: {device}")
        self.bus = ServoBus(device, baud)

        # 初始化所有舵机
        for sid in ARM_IDS:
            self.bus.init_servo(sid)
            pos = self.bus.read_pos(sid)
            self.get_logger().info(f"  舵机 ID:{sid:02d} 初始化 OK, 位置:{pos}")

        # 订阅 /arm_cmd
        self.sub = self.create_subscription(String, "/arm_cmd", self._on_cmd, 10)
        self.get_logger().info("手臂节点就绪, 监听 /arm_cmd")

    def _on_cmd(self, msg: String):
        cmd = msg.data.strip().lower()
        self.get_logger().info(f"收到手臂指令: {cmd}")

        if cmd in PRESETS:
            targets = PRESETS[cmd]
            self.get_logger().info(f"执行预设: {cmd}")
            for sid in ARM_IDS:
                target = targets.get(sid, 2048)
                self.bus.write_pos(sid, target, SPEED, ACC)
                time.sleep(0.03)
            self.get_logger().info(f"预设 {cmd} 完成")
        else:
            self.get_logger().warn(f"未知手臂指令: {cmd}")

    def destroy_node(self):
        for sid in ARM_IDS:
            try:
                self.bus.write_pos(sid, PRESETS["home"].get(sid, 2048), SPEED, ACC)
            except: pass
        self.bus.close()
        super().destroy_node()


def main():
    rclpy.init()
    node = ArmNode()
    try: rclpy.spin(node)
    except KeyboardInterrupt: pass
    finally: node.destroy_node(); rclpy.shutdown()

if __name__ == "__main__": main()
