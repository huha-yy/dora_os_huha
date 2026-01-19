#!/usr/bin/env bash
# Monitor Auto-Save Activity in Real-Time

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

MAP_FILE="$HOME/dorabot_ws/maps/home.yaml"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Monitoring Auto-Save (Ctrl+C to stop)${NC}"
echo -e "${BLUE}========================================${NC}"
echo
echo -e "${YELLOW}Watching: ${MAP_FILE}${NC}"
echo -e "${YELLOW}Auto-save interval: 60 seconds${NC}"
echo

# Get initial timestamp
LAST_MOD=$(stat -c %Y "$MAP_FILE" 2>/dev/null || echo 0)

while true; do
    # Get current timestamp
    CURRENT_MOD=$(stat -c %Y "$MAP_FILE" 2>/dev/null || echo 0)
    
    # Check if file was modified
    if [ "$CURRENT_MOD" -ne "$LAST_MOD" ]; then
        MOD_TIME=$(stat -c %y "$MAP_FILE" 2>/dev/null)
        echo -e "${GREEN}✓ Map updated at: ${MOD_TIME}${NC}"
        LAST_MOD=$CURRENT_MOD
    fi
    
    # Show current time and next expected save
    CURRENT_TIME=$(date +%H:%M:%S)
    echo -ne "\r${BLUE}Current: ${CURRENT_TIME}${NC} | ${YELLOW}Waiting for next save...${NC}"
    
    sleep 1
done

