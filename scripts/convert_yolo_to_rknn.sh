#!/usr/bin/env bash
# =============================================================================
# Convert a YOLOv8/YOLO11 model to Rockchip RKNN (rk3588) for NPU inference.
#
#   >>> RUN THIS ON AN x86_64 LINUX PC (NOT on the Orange Pi). <<<
#   rknn-toolkit2 (the converter) does not build/run on arm64.
#
# Output: a "<model>_rknn_model/" directory containing the .rknn + metadata.
# Copy that directory to the robot at:  ~/dorabot_ws/src/perception/models/
# then run perception with:  --detection_model_name <model>_rknn_model
#
# Usage (on the x86 PC):
#   bash convert_yolo_to_rknn.sh [yolov8n.pt] [rk3588]
# =============================================================================
set -euo pipefail

MODEL="${1:-yolov8n.pt}"
TARGET="${2:-rk3588}"

# librknnrt.so on the robot is 2.3.0 -> use a matching 2.3.x toolkit so the
# exported model is runtime-compatible with rknn-toolkit-lite2 on the board.
RKNN_TOOLKIT_VERSION="${RKNN_TOOLKIT_VERSION:-2.3.0}"

if [[ "$(uname -m)" != "x86_64" ]]; then
    echo "ERROR: RKNN conversion must run on x86_64 (this is $(uname -m))." >&2
    echo "       Run this script on a Linux PC, then copy the result to the robot." >&2
    exit 1
fi

echo "[convert] Setting up an isolated venv for conversion..."
python3 -m venv /tmp/rknn_convert_venv
# shellcheck disable=SC1091
source /tmp/rknn_convert_venv/bin/activate
pip install --upgrade pip
pip install "ultralytics>=8.3.65" "rknn-toolkit2==${RKNN_TOOLKIT_VERSION}"

echo "[convert] Exporting ${MODEL} -> RKNN (${TARGET}, FP16)..."
yolo export model="${MODEL}" format=rknn name="${TARGET}"

OUT_DIR="${MODEL%.pt}_rknn_model"
echo
echo "[convert] Done. Created: ${OUT_DIR}/"
echo
echo "Next: copy it to the robot, e.g.:"
echo "  scp -r ${OUT_DIR} orangepi@<robot-ip>:~/dorabot_ws/src/perception/models/"
echo
echo "Then on the robot, run perception with:"
echo "  --detection_model_name ${OUT_DIR}"
