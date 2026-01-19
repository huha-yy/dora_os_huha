#!/usr/bin/env bash
# List All Saved Maps
# Shows all map files in the maps directory with details

set -euo pipefail

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

MAPS_DIR="$HOME/dorabot_ws/maps"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Saved Maps${NC}"
echo -e "${BLUE}========================================${NC}"
echo

if [ ! -d "$MAPS_DIR" ]; then
    echo -e "${YELLOW}Maps directory not found: $MAPS_DIR${NC}"
    exit 1
fi

# Find all .yaml files (each map has a .yaml metadata file)
YAML_FILES=$(find "$MAPS_DIR" -maxdepth 1 -name "*.yaml" -type f | sort -r)

if [ -z "$YAML_FILES" ]; then
    echo -e "${YELLOW}No maps found in $MAPS_DIR${NC}"
    echo
    echo -e "${BLUE}To create a map:${NC}"
    echo -e "  1. Start orchestrator: ./scripts/start_orchestrator_with_mapping.sh"
    echo -e "  2. Launch RViz2: rviz2 -d src/nav/config/mapping.rviz"
    echo -e "  3. Move camera to scan the room"
    echo -e "  4. Save map: ./scripts/save_map.sh"
    exit 0
fi

# Count maps
MAP_COUNT=$(echo "$YAML_FILES" | wc -l)
echo -e "${GREEN}Found ${MAP_COUNT} map(s)${NC}"
echo

# List each map with details
MAP_NUM=1
while IFS= read -r yaml_file; do
    MAP_NAME=$(basename "$yaml_file" .yaml)
    PGM_FILE="${MAPS_DIR}/${MAP_NAME}.pgm"
    PNG_FILE="${MAPS_DIR}/${MAP_NAME}.png"
    
    echo -e "${CYAN}[$MAP_NUM] ${MAP_NAME}${NC}"
    echo -e "    Location: ${yaml_file}"
    
    # Check if image files exist
    if [ -f "$PGM_FILE" ]; then
        PGM_SIZE=$(du -h "$PGM_FILE" | cut -f1)
        echo -e "    Image: ${MAP_NAME}.pgm (${PGM_SIZE})"
    fi
    
    if [ -f "$PNG_FILE" ]; then
        PNG_SIZE=$(du -h "$PNG_FILE" | cut -f1)
        echo -e "    Image: ${MAP_NAME}.png (${PNG_SIZE})"
    fi
    
    # Parse YAML for map details
    if [ -f "$yaml_file" ]; then
        RESOLUTION=$(grep "^resolution:" "$yaml_file" | awk '{print $2}' || echo "")
        WIDTH=$(grep "^width:" "$yaml_file" | awk '{print $2}' || echo "")
        HEIGHT=$(grep "^height:" "$yaml_file" | awk '{print $2}' || echo "")
        CREATED=$(grep "^created_at:" "$yaml_file" | cut -d"'" -f2 2>/dev/null || echo "")
        
        # Show resolution if available
        if [ -n "$RESOLUTION" ]; then
            echo -e "    Resolution: ${RESOLUTION} m/pixel"
        fi
        
        # Show size if width and height available
        if [ -n "$WIDTH" ] && [ -n "$HEIGHT" ]; then
            if [ -n "$RESOLUTION" ]; then
                # Calculate map size in meters (using awk for compatibility)
                MAP_WIDTH=$(awk "BEGIN {printf \"%.1f\", $RESOLUTION * $WIDTH}" 2>/dev/null || echo "?")
                MAP_HEIGHT=$(awk "BEGIN {printf \"%.1f\", $RESOLUTION * $HEIGHT}" 2>/dev/null || echo "?")
                echo -e "    Size: ${WIDTH}x${HEIGHT} cells (${MAP_WIDTH}m x ${MAP_HEIGHT}m)"
            else
                echo -e "    Size: ${WIDTH}x${HEIGHT} cells"
            fi
        fi
        
        # Show creation date if available
        if [ -n "$CREATED" ]; then
            echo -e "    Created: ${CREATED}"
        fi
    fi
    
    echo
    ((MAP_NUM++))
done <<< "$YAML_FILES"

echo -e "${BLUE}========================================${NC}"
echo
echo -e "${BLUE}Commands:${NC}"
echo -e "  View map metadata: ${CYAN}cat $MAPS_DIR/<map_name>.yaml${NC}"
echo -e "  Save new map:      ${CYAN}./scripts/save_map.sh${NC}"
echo -e "  Load map in ROS2:  ${CYAN}ros2 service call /map_manager/load_map ...${NC}"
echo

