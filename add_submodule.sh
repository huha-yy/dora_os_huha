#!/usr/bin/env bash
# Helper script to add a submodule to the workspace

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

if [ $# -lt 2 ]; then
    echo -e "${RED}Usage: $0 <repo-url> <local-path>${NC}"
    echo
    echo "Examples:"
    echo "  $0 git@github.com:user/nav.git src/nav"
    echo "  $0 https://github.com/user/ai_agent.git src/ai_agent"
    echo "  $0 git@github.com:user/configs.git configs"
    exit 1
fi

REPO_URL="$1"
LOCAL_PATH="$2"

WORKSPACE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$WORKSPACE_ROOT"

echo -e "${GREEN}Adding submodule...${NC}"
echo "  Repository: $REPO_URL"
echo "  Path: $LOCAL_PATH"
echo

# Check if path already exists
if [ -d "$LOCAL_PATH" ] && [ ! -d "$LOCAL_PATH/.git" ]; then
    echo -e "${YELLOW}Warning: $LOCAL_PATH exists but is not a git repository${NC}"
    echo "You may want to:"
    echo "  1. Backup the directory"
    echo "  2. Remove it"
    echo "  3. Then add the submodule"
    echo
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Aborted."
        exit 0
    fi
    # Backup existing directory
    BACKUP_NAME="${LOCAL_PATH}.backup.$(date +%Y%m%d_%H%M%S)"
    echo -e "${YELLOW}Backing up to: $BACKUP_NAME${NC}"
    mv "$LOCAL_PATH" "$BACKUP_NAME"
fi

# Add submodule
git submodule add "$REPO_URL" "$LOCAL_PATH"

echo
echo -e "${GREEN}Submodule added successfully!${NC}"
echo
echo "To initialize and update all submodules:"
echo -e "  ${GREEN}git submodule update --init --recursive${NC}"
echo
echo "To commit this change:"
echo -e "  ${GREEN}git commit -m \"Add $LOCAL_PATH submodule\"${NC}"
echo -e "  ${GREEN}git push${NC}"
echo
