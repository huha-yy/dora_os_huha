#!/usr/bin/env bash
# =============================================================================
# Create the Python virtual environment for the perception + orchestrator
# services (NO sudo required). Run AFTER scripts/install_ros2_humble.sh.
#
#     bash ~/dorabot_ws/scripts/setup_perception_env.sh
#
# The venv lives at $ROOT/.venv (the path the existing start scripts expect).
# It uses Python 3.10 to match ROS 2 Humble; rclpy/cv_bridge are picked up from
# the sourced ROS 2 install via PYTHONPATH at runtime (not installed here).
# =============================================================================
set -euo pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
log()  { echo -e "${GREEN}[setup-env]${NC} $*"; }
warn() { echo -e "${YELLOW}[setup-env]${NC} $*"; }

ROOT="${HOME}/dorabot_ws"
VENV="${ROOT}/.venv"

if ! command -v uv >/dev/null 2>&1; then
    warn "uv not found on PATH; trying ~/.local/bin/uv"
    export PATH="${HOME}/.local/bin:${PATH}"
fi
command -v uv >/dev/null 2>&1 || { echo "uv is required (https://docs.astral.sh/uv/)"; exit 1; }

log "Creating venv at ${VENV} (python 3.10)..."
uv venv --python 3.10 "${VENV}"

PY="${VENV}/bin/python"

log "Installing perception + orchestrator Python dependencies..."
# numpy pinned <2 for mediapipe + ROS cv_bridge ABI compatibility.
uv pip install --python "${PY}" \
    "numpy==1.26.4" \
    pyrealsense2 \
    "opencv-python==4.11.0.86" \
    mediapipe \
    ultralytics \
    rknn-toolkit-lite2 \
    click \
    tqdm \
    "fastapi" \
    "uvicorn[standard]" \
    requests \
    pyyaml \
    pydantic

log "Verifying key imports (ROS 2 must be sourced for rclpy)..."
set +e
set +u
source "/opt/ros/humble/setup.bash" 2>/dev/null
set -u
"${PY}" - <<'PYEOF'
mods = ["pyrealsense2", "cv2", "mediapipe", "numpy", "fastapi", "uvicorn", "click"]
ok = True
for m in mods:
    try:
        __import__(m)
        print(f"  ok   {m}")
    except Exception as e:
        ok = False
        print(f"  FAIL {m}: {e}")
try:
    from rknnlite.api import RKNNLite  # noqa
    print("  ok   rknnlite (NPU inference)")
except Exception as e:
    print(f"  FAIL rknnlite: {e}")
try:
    import rclpy  # noqa
    print("  ok   rclpy (ROS 2)")
except Exception as e:
    print(f"  WARN rclpy not importable yet: {e}")
    print("       -> source /opt/ros/humble/setup.bash, then re-test.")
print("RESULT:", "OK" if ok else "SOME_FAILED")
PYEOF
set -e

cat <<EOF

${GREEN}=============================================================${NC}
 Perception/orchestrator venv ready at: ${VENV}
${GREEN}=============================================================${NC}

 To run anything that uses ROS 2, source ROS first, then the venv:
     source /opt/ros/humble/setup.bash
     source ${VENV}/bin/activate

EOF
