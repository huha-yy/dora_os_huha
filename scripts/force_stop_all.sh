#!/usr/bin/env bash
# Force Stop All ROS2 and Orchestrator Processes
# Nuclear option - kills everything related to orchestrator and ROS2

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${RED}========================================${NC}"
echo -e "${RED}  FORCE STOP ALL SERVICES${NC}"
echo -e "${RED}========================================${NC}"
echo
echo -e "${YELLOW}⚠️  This will forcefully kill ALL ROS2 and orchestrator processes!${NC}"
echo

# Confirm action
read -p "Are you sure you want to continue? [y/N] " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 0
fi

echo
echo -e "${RED}Force killing all processes...${NC}"
echo

# Kill orchestrator
echo "→ Orchestrator processes..."
pkill -9 -f "orchestrator/main.py" 2>/dev/null || true
pkill -9 -f "start_orchestrator" 2>/dev/null || true

# Kill AI Agent
echo "→ AI Agent..."
pkill -9 -f "ai_agent" 2>/dev/null || true

# Kill Perception
echo "→ Perception..."
pkill -9 -f "perception/main.py" 2>/dev/null || true
pkill -9 -f "body_tracking" 2>/dev/null || true

# Kill RealSense
echo "→ RealSense Camera..."
pkill -9 -f "realsense" 2>/dev/null || true

# Kill all nav processes
echo "→ Navigation services..."
pkill -9 -f "map_generator" 2>/dev/null || true
pkill -9 -f "map_manager" 2>/dev/null || true
pkill -9 -f "rtabmap" 2>/dev/null || true

# Kill static TF
echo "→ Static TF publishers..."
pkill -9 -f "static_transform_publisher" 2>/dev/null || true

# Kill all ROS2 run/launch processes
echo "→ ROS2 processes..."
pkill -9 -f "ros2 run" 2>/dev/null || true
pkill -9 -f "ros2 launch" 2>/dev/null || true

# Kill any Python processes related to nav package
echo "→ Nav package processes..."
pkill -9 -f "install/lib/nav" 2>/dev/null || true

# Kill RViz2 if running
echo "→ RViz2..."
pkill -9 -f "rviz2" 2>/dev/null || true

echo
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  All Processes Terminated${NC}"
echo -e "${GREEN}========================================${NC}"
echo

# Show remaining nodes
if command -v ros2 &> /dev/null; then
    echo -e "${YELLOW}Checking for remaining ROS2 nodes...${NC}"
    NODES=$(ros2 node list 2>/dev/null || echo "")
    if [ -z "$NODES" ]; then
        echo -e "${GREEN}✓ No ROS2 nodes running${NC}"
    else
        echo -e "${YELLOW}Remaining nodes:${NC}"
        echo "$NODES"
        echo
        echo -e "${YELLOW}These may be system nodes or from other applications.${NC}"
    fi
fi

echo
echo -e "${GREEN}Force cleanup complete!${NC}"
echo -e "${YELLOW}Note: You may want to restart the ROS2 daemon:${NC}"
echo -e "${YELLOW}  ros2 daemon stop && ros2 daemon start${NC}"

