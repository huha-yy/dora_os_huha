# Dorabot Workspace

Autonomous robot stack: live vision + fall detection, voice chatbot, and (optional) mapping/navigation.

## Overview

On a typical deployment (Orange Pi 5 / RK3588S + RealSense D415), one orchestrator process manages:

```
chatbot (:8000) ──┐
RealSense D415 ───┤
perception ───────┼──► orchestrator (:8080) ──► unified web UI
                  │        ├─ live annotated camera (MJPEG)
fall events ──────┘        └─ chatbot sidebar
```

**Implemented today:** orchestrated services, RealSense camera, YOLO + MediaPipe fall detection, unified monitor UI, voice chatbot (MiniMax LLM).

**Optional / in development:** RTAB-Map SLAM, 2D mapping, Nav2 navigation.

### Camera heart-rate readout (rPPG)

A live heart-rate estimate from the face, plus an on-demand 30-second scan with a
面色 / complexion **appearance** card. Uses classical POS/CHROM remote
photoplethysmography — CPU-only, no training data, no extra models.

> **仅供参考，非医疗设备 · For reference only, not a medical device.**
> This is a demo readout, not a health, wellness, or diagnostic feature. Readings
> depend heavily on lighting, camera white balance, and how still the subject is.
> The 面色 card describes visual **appearance** only and is not a health indicator.

Heart rate is the only metric produced. Respiratory rate, HRV, and SpO2 appear in
the message schema but are always `null` and are not implemented. When quality
gates fail — no face, too small, low FPS, head motion, lighting change — the
reading is **withheld** (`null`), never guessed.

Disable the feature entirely with `HEALTH_ENABLED=0`; fall detection is untouched
when it is off. Select the estimator with `HEALTH_BACKEND=pos|chrom` (default `pos`).

```bash
HEALTH_ENABLED=0 bash scripts/start_dorabot.sh    # run without the health readout
```

**Not yet validated on real faces or on-device.** See `docs/superpowers/STATE.md`
(Tasks 16a / 16b) before trusting any number it prints.

See also **[DEPLOYMENT.md](DEPLOYMENT.md)** for platform-specific notes (RK3588 NPU, performance tuning).

---

## 快速开始 Quick Start

完成下方 [New robot setup](#new-robot-setup) 中的依赖安装后，**通过 SSH 远程登录机器人**即可启动前后端，无需在机器人上接键盘。

**1. 启动后端**（摄像头、感知、聊天机器人、Web 服务）— 在 SSH 终端中运行，保持前台：

```bash
bash ~/dorabot_ws/scripts/start_dorabot.sh
```

**2. 启动前端**（在机器人屏幕全屏打开监控界面）— **另开一个 SSH 终端**：

```bash
bash ~/dorabot_ws/scripts/start-frontend-ssh.sh
```

浏览器会打开 `http://localhost:8080/`（左侧实时画面 + 右侧语音助手）。

**停止：**

```bash
# 关闭机器人屏幕上的前端
bash ~/dorabot_ws/scripts/start-frontend-ssh.sh --stop

# 关闭后端：在运行 start_dorabot.sh 的终端按 Ctrl+C
```

| 脚本 | 作用 |
|------|------|
| `scripts/start_dorabot.sh` | 后端：orchestrator + 摄像头 + 感知 + chatbot |
| `scripts/start-frontend-ssh.sh` | 前端：Chromium 全屏 kiosk（需机器人桌面/X 已启动） |
| `scripts/start-frontend-local.sh` | 前端：在机器人本机桌面打开浏览器（接键盘时用） |

日志目录：`~/logs/` · 局域网访问 UI：`http://<机器人IP>:8080/`

---

## New robot setup

Target platform: **Ubuntu 22.04 (jammy) arm64**, e.g. Orange Pi 5 with RealSense **D415**.

### Hardware

| Component | Notes |
|-----------|--------|
| Board | Orange Pi 5 / RK3588S, 8 GB RAM recommended |
| Camera | Intel RealSense D415 (USB 3) |
| Display | 1024×600 panel (or any desktop for local browser mode) |
| OS | Ubuntu 22.04 LTS |

RK3588 NPU runtime (`librknnrt.so`) should be present on the board image for fast detection. Without it, perception falls back to CPU (~2–5 FPS).

### 1. Clone the workspace

```bash
git clone <your-repo-url> ~/dorabot_ws
cd ~/dorabot_ws
```

### 2. Install system dependencies (sudo)

Run as your normal user — scripts call `sudo` where needed.

**a) ROS 2 Humble + build tools** (required):

```bash
bash ~/dorabot_ws/scripts/install_ros2_humble.sh
```

Installs: `ros-humble-ros-base`, `cv-bridge`, `colcon`, `rosdep`, `build-essential`, and adds ROS sourcing to `~/.bashrc`.

> **Note:** This does **not** install `realsense2_camera` (no arm64 apt package). The camera is published via a lightweight **pyrealsense2** node instead.

**b) UI + utilities** (recommended):

```bash
sudo apt install -y chromium-browser curl git
```

**c) Python package manager `uv`** (required for venv setup):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"   # add to ~/.bashrc if needed
```

**d) Camera access** — plug in the D415, add your user to the `video` group, then re-login:

```bash
sudo usermod -aG video "$USER"
```

After step 3, verify the camera:

```bash
source ~/dorabot_ws/.venv/bin/activate
python -c "import pyrealsense2 as rs; print(list(rs.context().devices))"
```

**Optional (mapping / SLAM later):**

```bash
sudo apt install ros-humble-rtabmap-ros ros-humble-nav2-bringup
```

### 3. Create Python virtual environments (no sudo)

Open a **new terminal** (or `source ~/.bashrc`) so ROS 2 is on your PATH.

**a) Perception + orchestrator** — `~/dorabot_ws/.venv`:

```bash
source /opt/ros/humble/setup.bash
bash ~/dorabot_ws/scripts/setup_perception_env.sh
```

**b) Chatbot** — `~/dorabot_ws/src/chatbot/.venv`:

```bash
cd ~/dorabot_ws/src/chatbot
uv venv .venv --python 3.10
uv pip install -r requirements.txt
```

ASR/TTS model weights under `src/chatbot/models/` are included in the repo (~1 GB).

### 4. Perception model files

`src/perception/models/` is gitignored. Copy or create models on each robot:

| File / directory | Purpose | How to get it |
|------------------|---------|---------------|
| `pose_landmarker_lite.task` | MediaPipe pose | Copy from another robot, or run the `wget` below |
| `yolo11n_rknn_model/` | **Recommended** — NPU detection | Convert on x86 PC (see below) or `scp` from another robot |
| `yolov8n.pt` | CPU fallback | Auto-downloads on first YOLO run, or copy from another robot |

Download the pose model:

```bash
mkdir -p ~/dorabot_ws/src/perception/models
wget -O ~/dorabot_ws/src/perception/models/pose_landmarker_lite.task \
  https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task
```

**Convert RKNN model on an x86 Linux PC** (not on the Orange Pi):

```bash
# on x86 PC:
bash scripts/convert_yolo_to_rknn.sh yolo11n.pt rk3588
scp -r yolo11n_rknn_model orangepi@<robot-ip>:~/dorabot_ws/src/perception/models/
```

Default config uses `yolo11n_rknn_model` — see `configs/orchestrator/config.yaml`.

### 5. Chatbot API key

The LLM reads **`MINIMAX_API_KEY`** from the environment (`config.json` keeps `"api_key": null`):

```bash
echo 'export MINIMAX_API_KEY="your-key-here"' >> ~/.bashrc
source ~/.bashrc
```

Start scripts load this automatically via `scripts/load_minimax_env.sh`.

### 6. Sanity checks

```bash
source /opt/ros/humble/setup.bash
source ~/dorabot_ws/.venv/bin/activate

python -c "import rclpy, pyrealsense2, cv2, mediapipe; print('deps OK')"

# camera + detection smoke test (no ROS):
PYTHONPATH=src/perception python src/perception/cam_perception_test.py
```

安装完成后 → 见上方 **[快速开始](#快速开始-quick-start)**，通过 SSH 启动前后端。

---

## Launch

> **日常启动请直接用上方 [快速开始](#快速开始-quick-start) 中的三条命令。**

### Start backends (orchestrator + chatbot + camera + perception)

```bash
bash ~/dorabot_ws/scripts/start_dorabot.sh
```

This starts everything and prints the UI URL, e.g. `http://192.168.x.x:8080/`.

- **Orchestrator** (UI, MJPEG, events): port **8080**
- **Chatbot** (WebSocket + web UI): port **8000**
- **Logs:** `~/logs/{chatbot,realsense_d415,perception,camera_mount_tf}.log`
- **Stop:** `Ctrl+C` in the start terminal (orchestrator tears down all child services)

Custom config:

```bash
bash ~/dorabot_ws/scripts/start_dorabot.sh -c configs/orchestrator/config_mapping.yaml
```

### Open the monitor UI

**Remote via SSH** (robot has a display, no local keyboard) — **recommended:**

```bash
bash ~/dorabot_ws/scripts/start-frontend-ssh.sh
bash ~/dorabot_ws/scripts/start-frontend-ssh.sh --stop   # stop kiosk
```

**On the robot desktop** (keyboard attached):

```bash
bash ~/dorabot_ws/scripts/start-frontend-local.sh
```

**From any browser on the network:**

```
http://<robot-ip>:8080/
```

### Stop / clean up

```bash
# if start_dorabot.sh is still running: Ctrl+C

# force-kill leftover processes:
bash ~/dorabot_ws/scripts/stop_orchestrator.sh
```

### Quick health checks

```bash
curl -s http://localhost:8080/video/status
curl -s http://localhost:8080/health

source /opt/ros/humble/setup.bash
ros2 topic list | grep -E 'camera|body_tracking|fall'

tail -f ~/logs/perception.log | grep FPS    # when print_fps: true in config
```

---

## Configuration

Main config: **`configs/orchestrator/config.yaml`**

| Setting | Default | Notes |
|---------|---------|-------|
| `orchestrator_port` | `8080` | UI + MJPEG |
| `camera.width/height/fps` | `424×240 @ 15` | Sized for 1024×600 display |
| `camera.align_depth` | `false` | Auto-enables when map/SLAM services are on |
| `camera.flip_180` | `true` | D415 mounted upside down on this robot |
| `perception.detection_model_name` | `yolo11n_rknn_model` | NPU model directory name |
| `perception.process_every_n` | `2` | Run detection every N-th frame |
| `perception.print_fps` | `true` | Log FPS to `~/logs/perception.log` |

Other profiles: `config_mapping.yaml`, `config_slam.yaml`, `config_full.yaml`.

```bash
python src/orchestrator/main.py --help
```

---

## Architecture

```
dorabot_ws/
├── configs/orchestrator/   # YAML service profiles
├── scripts/                # install, setup, start/stop scripts
├── src/
│   ├── orchestrator/       # service manager, web UI, MJPEG stream
│   ├── chatbot/            # voice assistant (own .venv, port 8000)
│   ├── perception/         # camera publisher, YOLO, fall detection
│   ├── nav/                # mapping & navigation (optional)
│   └── ai_agent/           # legacy agent (not used by default stack)
├── maps/                   # saved navigation maps
└── logs/                   # runtime logs (~/logs/ at runtime)
```

---

## Advanced: mapping & navigation

These require a `colcon` build and optional apt packages (see step 2 above).

```bash
cd ~/dorabot_ws
colcon build --merge-install
source install/setup.bash
```

```bash
# mapping + RTAB-Map
bash scripts/start_orchestrator_with_mapping.sh --with-rtabmap

# full stack including Nav2
bash scripts/start_orchestrator_full.sh
```

See **[docs/QUICK_START_GUIDE.md](docs/QUICK_START_GUIDE.md)** and **[docs/MAPPING_QUICKSTART.md](docs/MAPPING_QUICKSTART.md)** for details.

### Map management (when mapping is running)

```bash
ros2 service call /map_manager/save_map std_srvs/srv/Trigger
ros2 service call /map_manager/load_map std_srvs/srv/Trigger
ros2 service call /map_manager/list_maps std_srvs/srv/Trigger
ros2 service call /map_generator/reset_map std_srvs/srv/Empty
```

---

## Troubleshooting

### Camera not detected

```bash
# after venv is set up:
source ~/dorabot_ws/.venv/bin/activate
python -c "import pyrealsense2 as rs; print(list(rs.context().devices))"

sudo udevadm control --reload-rules && sudo udevadm trigger
# re-plug USB; ensure user is in group 'video'
```

### `rclpy not importable`

ROS 2 must be sourced **before** the venv:

```bash
source /opt/ros/humble/setup.bash
source ~/dorabot_ws/.venv/bin/activate
python -c "import rclpy"
```

### Chatbot LLM fails to init

```bash
grep MINIMAX_API_KEY ~/.bashrc
bash ~/dorabot_ws/scripts/load_minimax_env.sh && echo "${MINIMAX_API_KEY:+set}"
```

### Stream unavailable / services exit immediately

```bash
tail -30 ~/logs/perception.log
tail -30 ~/logs/realsense_d415.log
tail -30 ~/logs/chatbot.log
```

Common causes: missing perception models, wrong CLI flags, port 8000/8080 already in use.

### Perception slow on CPU

Ensure `yolo11n_rknn_model/` exists and `detection_model_name` points to it in config. CPU fallback (`yolov8n.pt`) works but is much slower.

---

## Documentation

| Doc | Description |
|-----|-------------|
| [DEPLOYMENT.md](DEPLOYMENT.md) | Orange Pi / RK3588 bring-up, NPU models, topics & ports |
| [docs/QUICK_START_GUIDE.md](docs/QUICK_START_GUIDE.md) | Legacy quick start (mapping-focused) |
| [docs/MAPPING_QUICKSTART.md](docs/MAPPING_QUICKSTART.md) | Creating maps |
| [configs/README.md](configs/README.md) | Configuration profiles |

---

## License

Proprietary — Dorabot Project

**Maintainer:** frank (frank123111@gmail.com)

**Status:** Active development · **Last updated:** May 2026
