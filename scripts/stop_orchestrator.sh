#!/usr/bin/env bash
# Stop Dorabot Orchestrator and Clean Up All Services
# Stops the orchestrator and ensures all child processes are terminated

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Stopping Dorabot Orchestrator${NC}"
echo -e "${BLUE}========================================${NC}"
echo

# Function to kill processes by pattern
kill_processes() {
    local pattern=$1
    local description=$2
    
    if pgrep -f "$pattern" > /dev/null 2>&1; then
        echo -e "${YELLOW}Stopping ${description}...${NC}"
        pkill -SIGTERM -f "$pattern" 2>/dev/null || true
        sleep 1
        
        # Force kill if still running
        if pgrep -f "$pattern" > /dev/null 2>&1; then
            echo -e "${YELLOW}Force killing ${description}...${NC}"
            pkill -SIGKILL -f "$pattern" 2>/dev/null || true
        fi
        echo -e "${GREEN}✓ ${description} stopped${NC}"
    else
        echo -e "${GREEN}✓ ${description} not running${NC}"
    fi
}

# Stop orchestrator main process
echo -e "${BLUE}[1/8] Stopping Orchestrator Main Process${NC}"
kill_processes "python3 src/orchestrator/main.py" "Orchestrator"
kill_processes "start_orchestrator" "Orchestrator launcher"

# Stop AI Agent
echo -e "${BLUE}[2/8] Stopping AI Agent${NC}"
kill_processes "src/ai_agent/run_server.py" "AI Agent"

# Stop Perception
echo -e "${BLUE}[3/8] Stopping Perception System${NC}"
kill_processes "src/perception/main.py" "Perception"

# Stop RealSense Camera
echo -e "${BLUE}[4/8] Stopping RealSense Camera${NC}"
kill_processes "realsense2_camera_node" "RealSense Camera Node"
kill_processes "realsense2_camera" "RealSense Camera (all instances)"
kill_processes "run_camera.py" "RealSense Publisher (pyrealsense2)"
kill_processes "rs_launch.py" "RealSense Launch"

# Stop Map Generator
echo -e "${BLUE}[5/8] Stopping Map Generator${NC}"
kill_processes "map_generator" "Map Generator"

# Stop Map Manager
echo -e "${BLUE}[6/8] Stopping Map Manager${NC}"
kill_processes "map_manager" "Map Manager"

# Stop Static TF Publisher
echo -e "${BLUE}[7/8] Stopping Static TF Publisher${NC}"
kill_processes "static_transform_publisher.*camera_link" "Static TF Publisher (camera)"

# Stop RTAB-Map (if running)
echo -e "${BLUE}[8/8] Stopping RTAB-Map SLAM (if running)${NC}"
kill_processes "rtabmap" "RTAB-Map"

# Additional cleanup - any orphaned ROS2 processes
echo
echo -e "${BLUE}Cleaning up orphaned processes...${NC}"
kill_processes "ros2 run nav" "Nav package processes"
kill_processes "ros2 launch" "ROS2 launch processes"

echo
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  All Services Stopped${NC}"
echo -e "${GREEN}========================================${NC}"
echo

# Check if any ROS2 nodes are still running
echo -e "${BLUE}Checking for remaining ROS2 nodes...${NC}"
if command -v ros2 &> /dev/null; then
    REMAINING_NODES=$(ros2 node list 2>/dev/null | grep -E "(map_generator|map_manager|dorabot_orchestrator|body_tracking|camera)" || true)
    
    if [ -n "$REMAINING_NODES" ]; then
        echo -e "${YELLOW}Warning: Some nodes are still running:${NC}"
        echo "$REMAINING_NODES"
        echo
        
        # Ask user if they want to force kill
        read -p "Force kill all remaining ROS2 nodes? [y/N] " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            echo -e "${YELLOW}Force killing remaining nodes...${NC}"
            # Kill camera nodes specifically
            pkill -9 -f "camera/camera" 2>/dev/null || true
            pkill -9 -f "realsense" 2>/dev/null || true
            # Kill any remaining ROS2 processes
            pkill -9 -f "ros2 run" 2>/dev/null || true
            pkill -9 -f "ros2 launch" 2>/dev/null || true
            sleep 1
            echo -e "${GREEN}✓ Force kill complete${NC}"
        else
            echo -e "${YELLOW}Skipping force kill. Nodes may be from other sessions.${NC}"
        fi
    else
        echo -e "${GREEN}✓ No orchestrator-related nodes running${NC}"
    fi
else
    echo -e "${YELLOW}Note: ros2 command not available in this shell${NC}"
fi

echo
echo -e "${GREEN}Cleanup complete!${NC}"

