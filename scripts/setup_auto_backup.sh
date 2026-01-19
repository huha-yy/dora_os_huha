#!/usr/bin/env bash
# Setup Automatic Map Backups using Cron
# Runs backup before each auto-save cycle

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_SCRIPT="$SCRIPT_DIR/backup_current_map.sh"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Setup Automatic Map Backups${NC}"
echo -e "${BLUE}========================================${NC}"
echo

# Auto-save interval from config (default 10 minutes)
INTERVAL_MINUTES=10

echo -e "${BLUE}Configuration:${NC}"
echo -e "  Auto-save interval: ${INTERVAL_MINUTES} minutes"
echo -e "  Backup before each auto-save"
echo -e "  Keep last 5 versions"
echo

# Create cron job entry
CRON_ENTRY="*/${INTERVAL_MINUTES} * * * * $BACKUP_SCRIPT >> /tmp/map_backup.log 2>&1"

echo -e "${BLUE}Setting up cron job...${NC}"
echo -e "${YELLOW}Cron entry:${NC}"
echo -e "  ${CRON_ENTRY}"
echo

# Check if cron entry already exists
if crontab -l 2>/dev/null | grep -q "backup_current_map.sh"; then
    echo -e "${YELLOW}⚠ Cron job already exists${NC}"
    read -p "Replace existing cron job? [y/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Aborted."
        exit 0
    fi
    
    # Remove old entry
    crontab -l | grep -v "backup_current_map.sh" | crontab -
fi

# Add new cron entry
(crontab -l 2>/dev/null; echo "$CRON_ENTRY") | crontab -

echo
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  ✓ Auto-backup Enabled!${NC}"
echo -e "${GREEN}========================================${NC}"
echo
echo -e "${GREEN}Backups will run every ${INTERVAL_MINUTES} minutes${NC}"
echo -e "${BLUE}Location: ~/dorabot_ws/maps/backups/${NC}"
echo
echo -e "${BLUE}To check status:${NC}"
echo -e "  crontab -l"
echo
echo -e "${BLUE}To view backup logs:${NC}"
echo -e "  tail -f /tmp/map_backup.log"
echo
echo -e "${BLUE}To disable:${NC}"
echo -e "  crontab -e  # Remove the backup_current_map.sh line"
echo

