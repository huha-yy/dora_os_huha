#!/usr/bin/env bash
# Start Dorabot Orchestrator with specified configuration
# Default: basic configuration (core services only)

set -euo pipefail

ROOT="$HOME/dorabot_ws"
cd "$ROOT"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}      Dorabot Orchestrator${NC}"
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

# Default configuration
CONFIG="configs/orchestrator/config.yaml"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --config|-c)
            CONFIG="$2"
            shift 2
            ;;
        --list)
            python3 src/orchestrator/main.py --list-configs
            exit 0
            ;;
        --help|-h)
            echo "Usage: $0 [--config <path>] [--list]"
            echo
            echo "Options:"
            echo "  --config, -c <path>  Use specified configuration file"
            echo "  --list               List available configuration files"
            echo "  --help, -h           Show this help message"
            echo
            echo "Available preset configurations:"
            echo "  configs/orchestrator/config.yaml          Basic mode (core services only)"
            echo "  configs/orchestrator/config_mapping.yaml  With custom mapping"
            echo "  configs/orchestrator/config_slam.yaml     With RTAB-Map SLAM"
            echo "  configs/orchestrator/config_full.yaml     Full navigation suite"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

echo "Using configuration: $CONFIG"
echo
echo "Logs will be saved to: ~/logs/"
echo "Press Ctrl+C to stop all services."
echo

# Execute
exec python3 src/orchestrator/main.py --config "$CONFIG"
