#!/usr/bin/env bash
# Test script for Dorabot mapping module

set -e

echo "======================================"
echo "  Dorabot Mapping Module Test Script"
echo "======================================"
echo

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if workspace is sourced
if [ -z "$AMENT_PREFIX_PATH" ]; then
    echo -e "${YELLOW}Sourcing workspace...${NC}"
    source ~/dorabot_ws/install/setup.bash
fi

echo "Step 1: Checking package installation..."
if ros2 pkg list | grep -q "^nav$"; then
    echo -e "${GREEN}✓ nav package found${NC}"
else
    echo -e "${RED}✗ nav package not found${NC}"
    echo "Please build the package first: colcon build --packages-select nav --merge-install"
    exit 1
fi

echo
echo "Step 2: Checking executables..."
for exec in map_generator map_manager; do
    if ros2 pkg executables nav | grep -q "$exec"; then
        echo -e "${GREEN}✓ $exec executable registered${NC}"
    else
        echo -e "${RED}✗ $exec executable not found${NC}"
        exit 1
    fi
done

echo
echo "Step 3: Checking launch files..."
for launch in map_generator.launch.py map_manager.launch.py mapping_full.launch.py; do
    if [ -f ~/dorabot_ws/src/nav/launch/$launch ]; then
        echo -e "${GREEN}✓ $launch exists${NC}"
    else
        echo -e "${RED}✗ $launch missing${NC}"
        exit 1
    fi
done

echo
echo "Step 4: Checking configuration files..."
for config in map_generator.yaml map_manager.yaml mapping.rviz; do
    if [ -f ~/dorabot_ws/src/nav/config/$config ]; then
        echo -e "${GREEN}✓ $config exists${NC}"
    else
        echo -e "${RED}✗ $config missing${NC}"
        exit 1
    fi
done

echo
echo "Step 5: Checking documentation..."
for doc in README.md src/mapping/README.md; do
    if [ -f ~/dorabot_ws/src/nav/$doc ]; then
        echo -e "${GREEN}✓ $doc exists${NC}"
    else
        echo -e "${YELLOW}⚠ $doc missing${NC}"
    fi
done

echo
echo "Step 6: Verifying maps directory..."
if [ -d ~/dorabot_ws/maps ]; then
    echo -e "${GREEN}✓ Maps directory exists${NC}"
    echo "  Contents:"
    ls -lh ~/dorabot_ws/maps/ 2>/dev/null | tail -n +2 || echo "  (empty)"
else
    echo -e "${YELLOW}⚠ Maps directory not found, will be created on first use${NC}"
fi

echo
echo "======================================"
echo "  Installation Check: PASSED"
echo "======================================"
echo
echo "You can now test the mapping system:"
echo
echo "1. Test with RTAB-Map SLAM (recommended):"
echo "   ./scripts/start_slam.sh"
echo
echo "2. Test custom map generator:"
echo "   ros2 launch nav mapping_full.launch.py launch_rtabmap:=false launch_map_generator:=true"
echo
echo "3. Test map manager services:"
echo "   ros2 run nav map_manager"
echo "   ros2 service call /map_manager/save_map std_srvs/srv/Trigger"
echo
echo "4. View in RViz:"
echo "   rviz2 -d ~/dorabot_ws/src/nav/config/mapping.rviz"
echo
echo "For detailed instructions, see:"
echo "  - ~/dorabot_ws/MAPPING_QUICKSTART.md"
echo "  - ~/dorabot_ws/MAPPING_MODULE_SUMMARY.md"
echo
