#!/usr/bin/env bash
# Start Dorabot Orchestrator with Mapping Services
# Uses configuration file approach

set -euo pipefail

ROOT="$HOME/dorabot_ws"
cd "$ROOT"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Dorabot Orchestrator with Mapping${NC}"
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

# Parse command line arguments
CONFIG="configs/orchestrator/config_mapping.yaml"

while [[ $# -gt 0 ]]; do
    case $1 in
        --with-rtabmap|--slam)
            CONFIG="configs/orchestrator/config_slam.yaml"
            shift
            ;;
        --with-nav|--full)
            CONFIG="configs/orchestrator/config_full.yaml"
            shift
            ;;
        --config|-c)
            CONFIG="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--with-rtabmap|--slam] [--with-nav|--full] [--config <path>]"
            echo
            echo "Options:"
            echo "  --with-rtabmap, --slam  Use SLAM configuration (includes RTAB-Map)"
            echo "  --with-nav, --full      Use full navigation configuration"
            echo "  --config, -c <path>     Use custom configuration file"
            exit 1
            ;;
    esac
done

echo "Using configuration: $CONFIG"
echo
echo "Logs will be saved to: ~/logs/"
echo
echo "Useful commands:"
echo "  - Save map: ros2 service call /map_manager/save_map std_srvs/srv/Trigger"
echo "  - View RViz: rviz2 -d src/nav/config/mapping.rviz"
echo
echo "Press Ctrl+C to stop all services."
echo

# Execute
exec python3 src/orchestrator/main.py --config "$CONFIG"
