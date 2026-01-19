#!/usr/bin/env bash
# Save Current Map
# Calls the map_manager service to save the current map with a timestamp

set -euo pipefail

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Saving Current Map${NC}"
echo -e "${BLUE}========================================${NC}"
echo

# Check if map_manager service is available
if ! ros2 service list 2>/dev/null | grep -q "/map_manager/save_map"; then
    echo -e "${RED}Error: map_manager service not found!${NC}"
    echo -e "${YELLOW}Make sure the orchestrator with mapping is running:${NC}"
    echo -e "${YELLOW}  ./scripts/start_orchestrator_with_mapping.sh${NC}"
    exit 1
fi

# Check if there's a current map
echo -e "${BLUE}Checking for available map...${NC}"

# Call the save_map service
echo -e "${BLUE}Calling save service...${NC}"
RESPONSE=$(ros2 service call /map_manager/save_map std_srvs/srv/Trigger "{}" 2>&1)

# Parse the response
if echo "$RESPONSE" | grep -q "success: true" || echo "$RESPONSE" | grep -q "success=True"; then
    # Extract the map name from the response
    MAP_NAME=$(echo "$RESPONSE" | grep -oP "message[=:] ['\"]?Map saved as \K[^'\"]*" || echo "unknown")
    
    echo
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}  ✓ Map Saved Successfully!${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo
    echo -e "${GREEN}Map name: ${MAP_NAME}${NC}"
    echo -e "${GREEN}Location: ~/dorabot_ws/maps/${NC}"
    echo
    echo -e "${BLUE}Files created:${NC}"
    
    if [ "$MAP_NAME" != "unknown" ]; then
        echo -e "  - ${MAP_NAME}.pgm  (map image)"
        echo -e "  - ${MAP_NAME}.yaml (map metadata)"
        echo
        
        # List the saved files if they exist
        if [ -f "$HOME/dorabot_ws/maps/${MAP_NAME}.yaml" ]; then
            echo -e "${BLUE}Map details:${NC}"
            cat "$HOME/dorabot_ws/maps/${MAP_NAME}.yaml"
        fi
    else
        echo -e "${YELLOW}Check ~/dorabot_ws/maps/ for the saved files${NC}"
    fi
    
else
    echo
    echo -e "${RED}========================================${NC}"
    echo -e "${RED}  ✗ Failed to Save Map${NC}"
    echo -e "${RED}========================================${NC}"
    echo
    
    # Extract error message if available
    ERROR_MSG=$(echo "$RESPONSE" | grep -oP "message[=:] ['\"]?\K[^'\"]*" || echo "Unknown error")
    echo -e "${RED}Error: ${ERROR_MSG}${NC}"
    echo
    echo -e "${YELLOW}Possible reasons:${NC}"
    echo -e "${YELLOW}  - No map data available yet${NC}"
    echo -e "${YELLOW}  - Map generator not running${NC}"
    echo -e "${YELLOW}  - Camera not publishing data${NC}"
    echo
    echo -e "${YELLOW}Try:${NC}"
    echo -e "${YELLOW}  1. Check if map is being generated: ros2 topic hz /map_generator/occupancy_grid${NC}"
    echo -e "${YELLOW}  2. View map in RViz2: rviz2 -d src/nav/config/mapping.rviz${NC}"
    echo -e "${YELLOW}  3. Wait a few seconds for map data to accumulate${NC}"
    exit 1
fi

echo
echo -e "${GREEN}Done!${NC}"

