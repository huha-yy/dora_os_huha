#!/usr/bin/env bash
# Start Dorabot Orchestrator with Full Navigation Suite
# Uses full navigation configuration file

set -euo pipefail

ROOT="$HOME/dorabot_ws"
cd "$ROOT"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Dorabot Full Navigation Suite${NC}"
echo -e "${GREEN}========================================${NC}"
echo

# Activate virtual environment if it exists
VENV_PATH="$ROOT/.venv"
if [ -d "$VENV_PATH" ]; then
    echo -e "${GREEN}Activating virtual environment...${NC}"
    source "$VENV_PATH/bin/activate"
else
    echo -e "${YELLOW}Warning: Virtual environment not found at $VENV_PATH${NC}"
    echo -e "${YELLOW}Create it with: cd $ROOT && uv venv .venv${NC}"
fi

# Check if workspace is sourced
if [ -z "$AMENT_PREFIX_PATH" ]; then
    echo -e "${YELLOW}Sourcing workspace...${NC}"
    source install/setup.bash
fi

# Set ROS environment
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
unset CYCLONEDDS_URI

echo -e "${BLUE}Using configuration: configs/orchestrator/config_full.yaml${NC}"
echo
echo -e "${YELLOW}Note: Make sure you have sufficient system resources!${NC}"
echo
echo "Logs will be saved to: ~/logs/"
echo
echo "Useful commands:"
echo "  - Save map: ros2 service call /map_manager/save_map std_srvs/srv/Trigger"
echo "  - List maps: ros2 service call /map_manager/list_maps std_srvs/srv/Trigger"
echo "  - View in RViz: rviz2 -d src/nav/config/mapping.rviz"
echo
echo "Press Ctrl+C to stop all services."
echo

# Execute with full configuration
exec python3 src/orchestrator/main.py --config configs/orchestrator/config_full.yaml
