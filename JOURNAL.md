# Dorabot 联调日志

> 最后更新：2026-07-09 | 记录关键决策、架构和当前状态

---

## 项目概述

**Dorabot（哆啦机器人）** — 戴恩科技陪伴机器人，基于 Orange Pi 5 (RK3588) + Ubuntu 22.04。

### 硬件

| 部件 | 型号 | 连接 |
|------|------|------|
| 主板 | Orange Pi 5 / RK3588S | — |
| 摄像头 | Intel RealSense D415 | USB 3.0 |
| 底盘电机 | ST3215 ×3 (全向轮) | RS-485 → /dev/ttyACM0 |
| 头颈舵机 | ST3250 ×2 (pan/tilt) | RS-485 → /dev/ttyACM0 (同总线) |
| 舵机协议 | SMS_STS (scservo_sdk) | ID: 轮1,2,3 + 头4,5 |
| 显示屏 | 1024×600 | HDMI |
| 网络 | 192.168.10.80 | WiFi |

### 软件架构

```
/home/orangepi/
├── data/dorabot_ws/     ★ 主项目 (GitHub: huha-yy/dora_os_huha, dev分支)
│   ├── src/
│   │   ├── chatbot/     语音助手 (LLM/TTS/ASR/VAD, 端口8000)
│   │   ├── orchestrator/ 编排器 (服务管理+Web UI, 端口8080)
│   │   ├── perception/   视觉感知 (YOLO+MediaPipe+跌倒检测)
│   │   ├── chassis/      底盘ROS2节点 (全向轮+头颈舵机)
│   │   ├── nav/          导航/SLAM (可选, ROS2)
│   │   └── ai_agent/     Live2D虚拟人 (未启用)
│   ├── configs/          配置文件
│   └── scripts/          启动/停止脚本
│
├── ros2_ws/             ROS2 机械臂+底盘遥控
│   ├── qnbot_cmd_bridge/  外骨骼→底盘桥接
│   ├── qnbot_teleoperator/ 遥操作
│   ├── f710_teleop/       F710手柄
│   └── openarm_*/         机械臂控制
│
├── ST32XX/              头颈舵机脚本 (已集成到chassis_node)
├── action/              机械臂动作JSON
└── logs/                运行日志
```

### 串口分配

```
/dev/ttyACM0 ── chassis_ros_node (唯一串口总管)
  ├── ID 1,2,3: ST3215 底盘全向轮 (速度模式)
  └── ID 4,5:   ST3250 头颈俯仰/左右 (位置模式)
```

### 话题通信

```
/cmd_vel  (Twist)      ← exo_cmd_bridge / F710 / ChassisControlSkill
/head_cmd (String)     ← ServoControlSkill
/odom     (Odometry)   → 导航 (chassis_node发布)
/camera/camera/color/image_raw  → 视觉感知
/body_tracking/image_annotated   → Web UI 展示
```

---

## 关键决策记录

### 2026-07-09

| # | 决策 | 原因 |
|---|------|------|
| 1 | **底盘+头颈统一由 chassis_ros_node 管理串口** | 避免多进程抢 /dev/ttyACM0 |
| 2 | **头颈舵机 ID: 1,2→4,5** | 底盘轮子用 ID 1,2,3，避免冲突 |
| 3 | **WHEEL_MAP 角度 (0°/240°/120°)** | 修正前进→右移的90°偏差 |
| 4 | **/cmd_vel 统一话题名** | exo_cmd_bridge 从 /svtrobot_cmd 改为 /cmd_vel |
| 5 | **Skill 用 subprocess ros2 topic pub** | relay方案不稳定，回归简单可靠方式 |
| 6 | **唤醒词"小戴"** | 不以"小戴"开头的语句静默忽略，不截断原文 |
| 7 | **TTS 前清洗 emoji/[标记]/Markdown** | 避免朗读"眼角含笑"等奇怪内容 |
| 8 | **看门狗 1s 自动停** | chassis_node 1秒无新指令归零，防止失控 |
| 9 | **Camera 分辨率 640x480** | D415不支持424x240，改回标准分辨率 |
| 10 | **Git 用 dev 分支** | main 保持可运行 baseline，dev 日常开发 |

### 语音控制优先级

```
用户说话 → 唤醒词检查(小戴) → 关键词匹配:
  1. ArmControlSkill (机械臂动作)
  2. ServoControlSkill (头颈动作)
  3. ChassisControlSkill (底盘运动)
  4. LLM 聊天回复 (MiniMax-M2.7)
```

---

## 当前状态 (2026-07-09)

### ✅ 已通过 (19项)

- 底盘: 全向移动、方向正确、看门狗、急停
- 头颈: 左右/俯仰/回中
- 语音: ASR识别、TTS合成、LLM对话、唤醒词
- 语音控制: 底盘(前进/后退/左转/右转/停止) + 头颈(转头/抬头/低头/回正)
- 系统: 全栈启动、Web UI、Git管理

### ⚠️ 部分通过 (4项)

- 视觉感知: CPU模式YOLO ~2.5FPS，待NPU模型部署
- MJPEG视频流: 随检测帧率波动
- Camera: 偶有USB超时

### ⏳ 待测 (5项)

- 语音音质评估
- 机械臂端到端
- 导航建图/SLAM (依赖编码器里程计)
- 自主导航

---

## 常用命令

### 启动系统

```bash
# 后端 (orchestrator + camera + perception + chatbot)
bash ~/dorabot_ws/scripts/start_dorabot.sh

# 前端 (全屏浏览器)
bash ~/dorabot_ws/scripts/start-frontend-ssh.sh

# 底盘节点 (如果被 killed)
source /opt/ros/humble/setup.bash
cd ~/data/dorabot_ws
python3 src/chassis/chassis_ros_node.py
```

### 手动控制

```bash
# 底盘
ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist "{linear: {x: 0.2}}"  # 前进
ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist "{}"                   # 停止

# 头颈
ros2 topic pub --once /head_cmd std_msgs/msg/String "{data: 'head_left'}"    # 左转
ros2 topic pub --once /head_cmd std_msgs/msg/String "{data: 'center_all'}"   # 回中
```

### Git

```bash
cd ~/claude/robot
git branch   # dev
git status
# 工作目录: ~/data/dorabot_ws/ → 同步到 ~/claude/robot/ → git push
```

### 诊断

```bash
ros2 node list
ros2 topic list
tail -f ~/logs/chatbot.log
tail -f ~/logs/perception.log
ss -tlnp | grep -E "8000|8080"
```

---

## 文件对应关系

| 工作目录 (运行) | Git仓库 (备份) |
|------|------|
| `~/data/dorabot_ws/src/*` | `~/claude/robot/src/*` |
| `~/ST32XX/*` | `~/claude/robot/board/ST32XX/*` |
| `~/ros2_ws/src/qnbot_cmd_bridge/config/*` | `~/claude/robot/board/ros2_ws/qnbot_cmd_bridge/config/*` |

> 工作目录的修改需手动 cp 到 Git 仓库再 push。

---

## 下一步

1. **NPU 模型部署**: x86 上 `model.export(format="rknn", name="rk3588")` → scp 到 Orange Pi
2. **机械臂联调**: 语音控制 → ArmControlSkill → ROS2 trajectory
3. **视觉性能**: NPU 部署后重测 FPS
