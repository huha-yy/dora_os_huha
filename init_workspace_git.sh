#!/usr/bin/env bash
# Initialize dorabot_ws as main git repository with submodules

set -e

WORKSPACE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$WORKSPACE_ROOT"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================"
echo "  Initialize Dorabot Workspace Git Repo"
echo "========================================${NC}"
echo

# Check if already initialized
if [ -d ".git" ]; then
    echo -e "${YELLOW}Git repository already exists!${NC}"
    echo "Current status:"
    git status
    echo
    read -p "Do you want to reinitialize? This will backup existing .git (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Aborted."
        exit 0
    fi
    mv .git .git.backup.$(date +%Y%m%d_%H%M%S)
    echo -e "${GREEN}Backed up existing .git directory${NC}"
fi

# Step 1: Initialize git repository
echo -e "${GREEN}[1/6] Initializing git repository...${NC}"
git init
echo

# Step 2: Create .gitignore
echo -e "${GREEN}[2/6] Creating .gitignore...${NC}"
cat > .gitignore << 'EOF'
# ROS2 build artifacts
build/
install/
log/

# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
*.egg-info/
dist/
*.egg

# Virtual environment
.venv/
venv/
ENV/

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# OS
.DS_Store
Thumbs.db

# Logs
logs/
*.log

# Temporary files
*.tmp
*.bak
*.backup
*.old

# Cache
cache/
.cache/

# Generated files
*.pyc
*.pyo
*.pdf
*.gv

# Local configuration overrides
*.local.yaml
.env
.env.*

# Maps (optional - uncomment if you don't want to commit maps)
# maps/*.pgm
# maps/*.yaml
# maps/*.png

EOF
echo -e "${GREEN}Created .gitignore${NC}"
echo

# Step 3: Detect submodules under src/
echo -e "${GREEN}[3/6] Detecting potential submodules in src/...${NC}"
echo

SUBMODULES=()
if [ -d "src" ]; then
    for dir in src/*/; do
        if [ -d "$dir" ]; then
            dirname=$(basename "$dir")
            # Skip if it's already a git repo
            if [ -d "${dir}.git" ]; then
                echo -e "${BLUE}  Found existing git repo: src/${dirname}${NC}"
                SUBMODULES+=("$dirname")
            else
                echo -e "${YELLOW}  Not a git repo yet: src/${dirname}${NC}"
                echo -e "    You can initialize it later with:"
                echo -e "    cd src/${dirname} && git init"
            fi
        fi
    done
fi

if [ ${#SUBMODULES[@]} -eq 0 ]; then
    echo -e "${YELLOW}No git repositories found in src/${NC}"
    echo "Note: You'll need to initialize submodules separately."
else
    echo -e "${GREEN}Found ${#SUBMODULES[@]} submodule(s)${NC}"
fi
echo

# Step 4: Create README if it doesn't exist
if [ ! -f "README.md" ]; then
    echo -e "${GREEN}[4/6] README.md already exists, skipping...${NC}"
else
    echo -e "${GREEN}[4/6] README.md exists${NC}"
fi
echo

# Step 5: Initial commit
echo -e "${GREEN}[5/6] Creating initial commit...${NC}"
git add .gitignore README.md
git add docs/ configs/ scripts/ change_logs/ 2>/dev/null || true
git add pyproject.toml 2>/dev/null || true

# Add source files but not the submodule directories themselves
if [ -d "src" ]; then
    # Add src directory structure but exclude submodule contents
    find src -maxdepth 1 -type f -exec git add {} \; 2>/dev/null || true
fi

git commit -m "Initial commit: Dorabot workspace

- Documentation structure
- Configuration repository
- Scripts and tools
- Change logs

Submodules will be added separately for:
$(for mod in "${SUBMODULES[@]}"; do echo "  - src/$mod"; done)
"

echo -e "${GREEN}Initial commit created${NC}"
echo

# Step 6: Instructions for adding submodules
echo -e "${GREEN}[6/6] Setup complete!${NC}"
echo
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Git Repository Initialized${NC}"
echo -e "${BLUE}========================================${NC}"
echo
echo "Current status:"
git status
echo
echo -e "${YELLOW}Next Steps:${NC}"
echo
echo "1. Add remote repository:"
echo -e "   ${BLUE}git remote add origin <your-repo-url>${NC}"
echo
echo "2. Push to remote:"
echo -e "   ${BLUE}git branch -M main${NC}"
echo -e "   ${BLUE}git push -u origin main${NC}"
echo
echo "3. Initialize submodules for source directories:"
echo
if [ ${#SUBMODULES[@]} -gt 0 ]; then
    echo "   Detected git repositories:"
    for mod in "${SUBMODULES[@]}"; do
        echo -e "   ${BLUE}cd src/${mod}${NC}"
        echo -e "   ${BLUE}git remote add origin <${mod}-repo-url>${NC}"
        echo -e "   ${BLUE}git push -u origin main${NC}"
        echo -e "   ${BLUE}cd ../${NC}"
        echo
    done
    echo "   Then add them as submodules to this repo:"
    for mod in "${SUBMODULES[@]}"; do
        echo -e "   ${BLUE}git submodule add <${mod}-repo-url> src/${mod}${NC}"
    done
else
    echo "   No git repositories found. Initialize them first:"
    echo -e "   ${BLUE}cd src/<module-name>${NC}"
    echo -e "   ${BLUE}git init${NC}"
    echo -e "   ${BLUE}git add .${NC}"
    echo -e "   ${BLUE}git commit -m \"Initial commit\"${NC}"
    echo -e "   ${BLUE}git remote add origin <repo-url>${NC}"
    echo -e "   ${BLUE}git push -u origin main${NC}"
    echo
    echo "   Then add as submodule:"
    echo -e "   ${BLUE}cd ${WORKSPACE_ROOT}${NC}"
    echo -e "   ${BLUE}git submodule add <repo-url> src/<module-name>${NC}"
fi
echo
echo "4. For configs repository (if separate):"
echo -e "   ${BLUE}cd configs${NC}"
echo -e "   ${BLUE}./init_git.sh${NC}"
echo -e "   ${BLUE}git remote add origin <configs-repo-url>${NC}"
echo -e "   ${BLUE}git push -u origin main${NC}"
echo -e "   ${BLUE}cd ..${NC}"
echo -e "   ${BLUE}git submodule add <configs-repo-url> configs${NC}"
echo
echo -e "${GREEN}Done!${NC}"
echo
