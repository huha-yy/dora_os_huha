# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project identity

**Dorabot (哆啦机器人)** — companion robot by 戴恩科技, running on Orange Pi 5 (RK3588) + Ubuntu 22.04.
GitHub: `huha-yy/dora_os_huha` (dev branch). Local IP: `192.168.10.80`.

## Quick start / stop

```bash
# Backend (orchestrator + camera + perception + chatbot)
bash ~/dorabot_ws/scripts/start_dorabot.sh

# Frontend (Chromium kiosk on robot display)
bash ~/dorabot_ws/scripts/start-frontend-ssh.sh
bash ~/dorabot_ws/scripts/start-frontend-ssh.sh --stop

# Chassis node (must be started separately if killed)
source /opt/ros/humble/setup.bash
cd ~/data/dorabot_ws && python3 src/chassis/chassis_ros_node.py
```

UI: `http://192.168.10.80:8080/` (left: camera + detection overlay, right: chatbot).

## Architecture

```
Orchestrator (:8080) manages 4 subprocesses:
  chatbot (:8000) — voice assistant (MiniMax LLM + Sherpa-ONNX ASR + Edge TTS + Silero VAD)
  realsense_d415 — pyrealsense2 → ROS /camera/camera/color/image_raw
  perception — YOLO person detection + MediaPipe pose + fall detection → /body_tracking/image_annotated
  camera_mount_tf — static transform (D415 mounted upside-down, flip_180=on)

chassis_ros_node (separate process) — /dev/ttyACM0 → ST3215×3 + ST3250×2 via RS-485
```

### ROS topics

| Topic | Type | Flow |
|-------|------|------|
| `/cmd_vel` | `Twist` | chatbot(F710/bridge/orchestrator) → chassis_node |
| `/head_cmd` | `String` | chatbot(ServoSkill) → chassis_node |
| `/odom` | `Odometry` | chassis_node → nav |
| `/camera/camera/color/image_raw` | `Image` | D415 → perception |
| `/body_tracking/image_annotated` | `Image` | perception → orchestrator(MJPEG) |
| `/fall_event` | `String`(JSON) | perception → orchestrator |

### Serial bus (critical)

`/dev/ttyACM0` is the SINGLE RS-485 bus. `chassis_ros_node` must be the **only process** opening it.
All other modules communicate via ROS topics, never directly.

| Servo ID | Type | Mode | Function |
|----------|------|------|----------|
| 1, 2, 3 | ST3215 | Continuous (wheel) | Omni wheels |
| 4 | ST3250 | Position | Head pan (left/right) |
| 5 | ST3250 | Position | Head tilt (up/down) |

### Voice interaction pipeline

```
Mic → VAD(Silero) → ASR(Sherpa-ONNX SenseVoice) → wake-word check ("小戴" prefix)
  → skill keyword matching (arm > servo > chassis > LLM)
  → execute or LLM(MiniMax-M2.7) → TTS(Edge) → speak
```

Wake word is a gate, NOT stripped from the text. Utterances without "小戴" prefix are silently ignored.

Skills publish commands via `robot_bus.py` (subprocess `ros2 topic pub --once`).
Arm → ROS2 trajectory scripts. Servo → `/head_cmd`. Chassis → `/cmd_vel` (timed stop after 2s).

## Key design decisions

1. **Single serial owner**: `chassis_ros_node` owns `/dev/ttyACM0` exclusively. Originally head servos used `servo_action.py` which opened the port directly — this has been migrated to ROS topics.
2. **Head servo IDs changed**: 1,2 → 4,5 because wheels use 1,2,3.
3. **WHEEL_MAP angles**: `(0°, 240°, 120°)`. Original code had `(90°, 330°, 210°)` which caused forward cmd → rightward motion.
4. **Topic unification**: exo_cmd_bridge changed from `/svtrobot_cmd` to `/cmd_vel`.
5. **Skill execution uses subprocess**: A persistent relay was attempted but proved unstable; reverted to `ros2 topic pub --once` via subprocess for reliability.
6. **Watchdog**: `chassis_ros_node` auto-stops if no `/cmd_vel` received for 1 second.
7. **TTS text cleaning**: `clean_text_for_tts()` strips emoji, `[bracket tags]`, and markdown formatting before TTS.
8. **Chatbot venv is isolated**: specifications.py line 58 clears PYTHONPATH for the chatbot process, so it can't import rclpy. This is intentional.

## Key files (what to edit for common tasks)

| Task | File |
|------|------|
| Add voice commands | `src/chatbot/skills/<skill>/config.yaml` (keywords only, no code) |
| Change LLM persona | `src/chatbot/config.json` → `system_prompt` |
| Camera settings | `configs/orchestrator/config.yaml` → `camera.*` |
| Chassis kinematics | `src/chassis/chassis_ros_node.py` → `WHEEL_MAP`, `compute_wheel_speeds()` |
| TTS voice/engine | `src/chatbot/config.json` → `tts_engine` |
| Wake word | `src/chatbot/websocket_handler.py` → `_process_speech()` wake-word block |

## Working directory vs Git repo

- **Working code**: `~/data/dorabot_ws/` (runs on the robot)
- **Git repo**: `~/claude/robot/` (cloned from GitHub, dev branch)
- **Also tracked**: `~/ST32XX/` → `board/ST32XX/`, `~/ros2_ws/src/qnbot_cmd_bridge/config/` → `board/ros2_ws/...`
- To commit: `cp` changed files from working dir to git repo, then `git add/commit/push`

## Diagnostics

```bash
ros2 node list && ros2 topic list
ss -tlnp | grep -E "8000|8080"
tail -f ~/logs/{chatbot,perception,realsense_d415}.log
grep -E "Skill|RobotBus|Error|Failed" ~/logs/chatbot.log | tail -20
```

## Related docs

- `JOURNAL.md` — decision log and detailed status
- `README.md` — setup instructions and architecture overview
- `DEPLOYMENT.md` — platform-specific notes (NPU, topics, ports)
- Memory: `robot-test-plan.md` — 28 test cases with pass/fail status
