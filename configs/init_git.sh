#!/usr/bin/env bash
# Initialize configs directory as a git repository

set -e

CONFIGS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$CONFIGS_DIR"

echo "========================================="
echo "  Initialize Configs Git Repository"
echo "========================================="
echo

# Check if already initialized
if [ -d ".git" ]; then
    echo "Git repository already initialized."
    echo "Current status:"
    git status
    exit 0
fi

# Initialize git
echo "Initializing git repository..."
git init

# Create initial commit
echo "Creating initial commit..."
git add .
git commit -m "Initial commit: Dorabot configuration files

- Orchestrator configurations
- Navigation configurations
- Example configurations
- README and .gitignore"

echo
echo "Git repository initialized successfully!"
echo
echo "Next steps:"
echo "1. Add remote repository:"
echo "   git remote add origin <your-repo-url>"
echo
echo "2. Push to remote:"
echo "   git push -u origin main"
echo
echo "3. To clone on another machine:"
echo "   cd ~/dorabot_ws"
echo "   git clone <your-repo-url> configs"
echo
