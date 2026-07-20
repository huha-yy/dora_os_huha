#!/usr/bin/env bash
# =============================================================================
# Start the full Dorabot stack via the orchestrator:
#   - chatbot          (src/chatbot, its own venv, port 8000)
#   - realsense_d415   (pyrealsense2 -> ROS color/depth topics)
#   - perception       (YOLO + MediaPipe fall detection, annotated stream)
#   - orchestrator     (UI + MJPEG + events API, port 8080)
#
# Open the UI at:   http://<robot-ip>:8080/
#
# Frontend (separate terminal, after backends are up):
#   bash scripts/start-frontend-ssh.sh    # from SSH -> kiosk on robot display
#   bash scripts/start-frontend-local.sh  # on robot desktop with keyboard
#
# Prereqs (run once):
#   1) bash scripts/install_ros2_humble.sh      # sudo, installs ROS 2
#   2) bash scripts/setup_perception_env.sh     # creates ~/dorabot_ws/.venv
#   3) chatbot venv exists at src/chatbot/.venv  (already set up)
#
# Usage:
#   bash scripts/start_dorabot.sh [-c configs/orchestrator/config.yaml]
# Stop with Ctrl+C (the orchestrator tears down all child services).
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/load_minimax_env.sh"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
ROOT="${HOME}/dorabot_ws"
cd "${ROOT}"

# =============================================================================
# 清理旧进程：杀掉上一轮残留的 camera / perception / chatbot / orchestrator
# =============================================================================
echo -e "${YELLOW}Cleaning up old processes...${NC}"

KILL_PATTERNS=(
    "run_camera.py"
    "realsense_publisher_node"
    "src/perception"
    "src/chatbot/main.py"
    "src/orchestrator/main.py"
    "servo_action.py"
    "static_transform_publisher.*camera"
)

KILLED_ANY=false
for pattern in "${KILL_PATTERNS[@]}"; do
    pids=$(pgrep -f "$pattern" 2>/dev/null || true)
    if [[ -n "$pids" ]]; then
        echo "  Killing: $pattern (PIDs: $(echo $pids | tr '\n' ' '))"
        kill $pids 2>/dev/null || true
        KILLED_ANY=true
    fi
done

if $KILLED_ANY; then
    sleep 1.5
    for pattern in "${KILL_PATTERNS[@]}"; do
        pids=$(pgrep -f "$pattern" 2>/dev/null || true)
        if [[ -n "$pids" ]]; then
            echo "  Force killing: $pattern (PIDs: $(echo $pids | tr '\n' ' '))"
            kill -9 $pids 2>/dev/null || true
        fi
    done
    echo -e "${GREEN}Old processes cleaned.${NC}"
else
    echo -e "${GREEN}No old processes found.${NC}"
fi
echo

CONFIG="configs/orchestrator/config.yaml"
while [[ $# -gt 0 ]]; do
    case "$1" in
        -c|--config) CONFIG="$2"; shift 2 ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

# --- ROS 2 ---
ROS_SETUP="/opt/ros/humble/setup.bash"
if [[ ! -f "${ROS_SETUP}" ]]; then
    echo -e "${RED}ROS 2 not found at ${ROS_SETUP}.${NC}"
    echo "Run: bash scripts/install_ros2_humble.sh"
    exit 1
fi
# ROS setup.bash references optional vars (e.g. AMENT_TRACE_SETUP_FILES) that
# are unset; `set -u` above would abort. Disable briefly while sourcing.
set +u
# shellcheck disable=SC1090
source "${ROS_SETUP}"
set -u
export RMW_IMPLEMENTATION="${RMW_IMPLEMENTATION:-rmw_fastrtps_cpp}"
unset CYCLONEDDS_URI 2>/dev/null || true

# --- perception/orchestrator venv ---
VENV="${ROOT}/.venv"
if [[ ! -d "${VENV}" ]]; then
    echo -e "${RED}venv not found at ${VENV}.${NC}"
    echo "Run: bash scripts/setup_perception_env.sh"
    exit 1
fi
# shellcheck disable=SC1090
source "${VENV}/bin/activate"

# rclpy must be importable now (ROS sourced).
if ! python -c "import rclpy" 2>/dev/null; then
    echo -e "${RED}rclpy not importable even after sourcing ROS 2.${NC}"
    echo "Check that the venv uses Python 3.10 (matching ROS 2 Humble)."
    exit 1
fi

if [[ -z "${MINIMAX_API_KEY:-}" ]]; then
    echo -e "${YELLOW}warning: MINIMAX_API_KEY not set (expected in ~/.bashrc).${NC}"
    echo -e "${YELLOW}         The chatbot LLM will fail to init without it.${NC}"
fi

echo -e "${GREEN}Starting Dorabot orchestrator with ${CONFIG}${NC}"
echo "UI:        http://$(hostname -I 2>/dev/null | awk '{print $1}'):8080/"
echo "Logs:      ~/logs/"
echo "Ctrl+C to stop all services."
echo
exec python src/orchestrator/main.py --config "${CONFIG}"
