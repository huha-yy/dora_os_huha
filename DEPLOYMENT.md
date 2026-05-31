# Dorabot — Orchestrator + Perception + Chatbot (Orange Pi 5 / RK3588S)

This brings up the full robot stack from a single command via the **orchestrator**:

```
chatbot (port 8000) ─┐
realsense_d415 ───────┤
perception ───────────┼──► orchestrator (port 8080)  ──► Web UI
                      │        ├─ live annotated camera (MJPEG)
fall_event ───────────┘        └─ embedded chatbot sidebar
```

Open the UI at **`http://<robot-ip>:8080/`** — the main panel shows the live
camera with human-tracking/fall-detection overlays, and the right sidebar is the
chatbot.

---

## Hardware / platform

- Orange Pi 5, **RK3588S** (NPU, 6 TOPS), 8 GB RAM, Ubuntu 22.04 (jammy), arm64, headless.
- Intel RealSense **D415** (USB).
- RKNN runtime present: `/usr/lib/librknnrt.so` **v2.3.0**.

## Model choice (limited hardware)

- **Person detection:** YOLOv8n (nano). On the **NPU via RKNN** it is fast; the
  CPU fallback runs but is only ~2–3 FPS at 640×480 (measured), so the NPU path
  is strongly recommended.
- **Pose / fall:** MediaPipe `pose_landmarker_lite` (CPU, runs per person box).

The detector auto-selects the backend from the model name passed to perception:
- `yolov8n.pt`            → CPU (Ultralytics/PyTorch) — fallback, works out of the box.
- `yolov8n_rknn_model`    → **NPU** (Ultralytics AutoBackend + rknn-toolkit-lite2).

---

## One-time setup

### 1. Install ROS 2 Humble (needs sudo)
```bash
bash ~/dorabot_ws/scripts/install_ros2_humble.sh
```
Installs ROS 2 Humble base + `cv_bridge` via apt (arm64). It does **not** build
`librealsense`/`realsense2_camera` (no arm64 binaries) — the camera is published
to ROS by a small `pyrealsense2`-backed node instead.

### 2. Create the perception/orchestrator venv (no sudo)
```bash
source /opt/ros/humble/setup.bash
bash ~/dorabot_ws/scripts/setup_perception_env.sh
```
Creates `~/dorabot_ws/.venv` (Python 3.10) with pyrealsense2, ultralytics,
mediapipe, rknn-toolkit-lite2, opencv, fastapi, etc. `rclpy`/`cv_bridge` come
from the sourced ROS 2 install.

### 3. (Recommended) Build the NPU model on an x86 PC
RKNN **conversion** can't run on arm64. On any x86_64 Linux PC:
```bash
bash scripts/convert_yolo_to_rknn.sh yolov8n.pt rk3588
# produces yolov8n_rknn_model/  — copy it to the robot:
scp -r yolov8n_rknn_model orangepi@<robot-ip>:~/dorabot_ws/src/perception/models/
```
Then set perception to use it (see config note below). Until you do this, the
stack runs on the CPU fallback automatically.

### 4. Chatbot
The chatbot venv (`src/chatbot/.venv`) and `config.json` are already set up.
The MiniMax API key is read from **`MINIMAX_API_KEY` in `~/.bashrc`**
(`config.json` has `"api_key": null`). The start scripts source bashrc when
needed so non-interactive launches still pick it up.

---

## Run everything
```bash
bash ~/dorabot_ws/scripts/start_dorabot.sh
# UI: http://<robot-ip>:8080/
```
The orchestrator starts the chatbot, camera publisher, and perception, monitors
them, and tears them all down on Ctrl+C. Per-service logs are in `~/logs/`.

### Using the NPU model
Perception currently defaults to `yolov8n.pt` (CPU). To use the NPU model, run
perception with `--detection_model_name yolov8n_rknn_model` (e.g. via the
orchestrator service command in `src/orchestrator/services/specs.py`, or test it
directly):
```bash
source /opt/ros/humble/setup.bash && source ~/dorabot_ws/.venv/bin/activate
cd ~/dorabot_ws
python src/perception/main.py --detection_model_name yolov8n_rknn_model
```

---

## Topics
| Topic | Type | Publisher → Subscriber |
|---|---|---|
| `/camera/camera/color/image_raw` | `sensor_msgs/Image` | realsense_d415 → perception |
| `/camera/camera/color/camera_info` | `sensor_msgs/CameraInfo` | realsense_d415 |
| `/camera/camera/aligned_depth_to_color/image_raw` | `sensor_msgs/Image` | realsense_d415 (with `--enable-depth`) |
| `/body_tracking/image_annotated` | `sensor_msgs/Image` | perception → orchestrator (MJPEG) |
| `/fall_event` | `std_msgs/String` (JSON) | perception → orchestrator (safety) |
| `/person_detection` | `geometry_msgs/Point` | perception |

## Ports
| Service | Port |
|---|---|
| Orchestrator (UI + MJPEG + events) | 8080 |
| Chatbot (websocket + frontend) | 8000 |

## Quick checks
```bash
# camera only (no ROS needed):
src/perception/.venv-cam-test/bin/python src/perception/cam_perception_test.py
# after ROS up, list topics:
source /opt/ros/humble/setup.bash && ros2 topic list
# video stream:
curl -s http://localhost:8080/video/status
```
