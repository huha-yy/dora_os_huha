#!/usr/bin/env bash
# Backup Current Map Before It Gets Overwritten
# Keeps last N versions as safety net

set -euo pipefail

# Configuration
MAPS_DIR="$HOME/dorabot_ws/maps"
BACKUP_DIR="$MAPS_DIR/backups"
CURRENT_MAP="home"
KEEP_VERSIONS=5  # Keep last 5 versions

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Check if current map exists
if [ ! -f "$MAPS_DIR/${CURRENT_MAP}.yaml" ]; then
    echo -e "${YELLOW}No current map to backup${NC}"
    exit 0
fi

# Generate backup filename with timestamp
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="${CURRENT_MAP}_backup_${TIMESTAMP}"

# Copy current map to backup
echo -e "${BLUE}Backing up current map...${NC}"
cp "$MAPS_DIR/${CURRENT_MAP}.yaml" "$BACKUP_DIR/${BACKUP_NAME}.yaml"
cp "$MAPS_DIR/${CURRENT_MAP}.pgm" "$BACKUP_DIR/${BACKUP_NAME}.pgm" 2>/dev/null || true

echo -e "${GREEN}✓ Backup saved: ${BACKUP_NAME}${NC}"

# Cleanup old backups (keep only last N)
echo -e "${BLUE}Cleaning up old backups...${NC}"
BACKUP_COUNT=$(find "$BACKUP_DIR" -name "${CURRENT_MAP}_backup_*.yaml" | wc -l)

if [ "$BACKUP_COUNT" -gt "$KEEP_VERSIONS" ]; then
    # Find oldest backups to delete
    TO_DELETE=$((BACKUP_COUNT - KEEP_VERSIONS))
    OLD_BACKUPS=$(find "$BACKUP_DIR" -name "${CURRENT_MAP}_backup_*.yaml" -type f | sort | head -n "$TO_DELETE")
    
    for backup in $OLD_BACKUPS; do
        echo -e "${YELLOW}  Deleting old backup: $(basename "$backup")${NC}"
        rm "${backup%.yaml}.yaml" 2>/dev/null || true
        rm "${backup%.yaml}.pgm" 2>/dev/null || true
    done
    
    echo -e "${GREEN}✓ Kept last ${KEEP_VERSIONS} backups${NC}"
else
    echo -e "${GREEN}✓ Currently have ${BACKUP_COUNT} backups (keeping up to ${KEEP_VERSIONS})${NC}"
fi

# Show backup list
echo
echo -e "${BLUE}Current backups:${NC}"
ls -lht "$BACKUP_DIR"/${CURRENT_MAP}_backup_*.yaml 2>/dev/null | head -n "$KEEP_VERSIONS" | awk '{print "  " $9}' || echo "  None"

echo
echo -e "${GREEN}Done!${NC}"

