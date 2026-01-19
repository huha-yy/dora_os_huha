# Dorabot Workspace Git Repository Guide

This guide explains how to manage the dorabot_ws workspace as a git repository with submodules.

## Repository Structure

```
dorabot_ws/                    # Main workspace repository
├── .git/                      # Main repo git data
├── src/                       # Source modules (submodules)
│   ├── nav/                   # Navigation module (submodule)
│   ├── ai_agent/              # AI agent module (submodule)
│   ├── perception/            # Perception module (submodule)
│   ├── orchestrator/          # Orchestrator module (submodule)
│   └── ...
├── configs/                   # Configuration repo (optional submodule)
├── docs/                      # Documentation
├── scripts/                   # Helper scripts
└── change_logs/               # Development history
```

## Quick Start

### Initialize Main Repository

```bash
cd ~/dorabot_ws
./init_workspace_git.sh
```

This will:
1. Initialize git repository
2. Create .gitignore
3. Make initial commit
4. Provide next steps

### Add Remote

```bash
git remote add origin git@github.com:your-org/dorabot-workspace.git
git branch -M main
git push -u origin main
```

## Working with Submodules

### Option 1: Add Existing Git Repositories as Submodules

If your source directories are already git repositories:

```bash
# For each module in src/
cd ~/dorabot_ws

# Add nav module
git submodule add git@github.com:your-org/dorabot-nav.git src/nav

# Add ai_agent module
git submodule add git@github.com:your-org/dorabot-ai-agent.git src/ai_agent

# Add perception module
git submodule add git@github.com:your-org/dorabot-perception.git src/perception

# Add orchestrator module
git submodule add git@github.com:your-org/dorabot-orchestrator.git src/orchestrator

# Commit submodule additions
git commit -m "Add source module submodules"
git push
```

### Option 2: Initialize and Add New Modules

If your source directories are not yet git repositories:

```bash
# Initialize each module
cd ~/dorabot_ws/src/nav
git init
git add .
git commit -m "Initial commit: Navigation module"
git remote add origin git@github.com:your-org/dorabot-nav.git
git push -u origin main

# Return to workspace and add as submodule
cd ~/dorabot_ws
git submodule add git@github.com:your-org/dorabot-nav.git src/nav
git commit -m "Add nav submodule"
git push
```

### Using the Helper Script

```bash
cd ~/dorabot_ws
./add_submodule.sh git@github.com:your-org/dorabot-nav.git src/nav
```

## Cloning the Workspace

When someone else clones the workspace:

### Method 1: Clone with Submodules
```bash
git clone --recurse-submodules git@github.com:your-org/dorabot-workspace.git ~/dorabot_ws
```

### Method 2: Clone Then Initialize Submodules
```bash
git clone git@github.com:your-org/dorabot-workspace.git ~/dorabot_ws
cd ~/dorabot_ws
git submodule update --init --recursive
```

## Daily Workflow

### Update Main Workspace

```bash
cd ~/dorabot_ws
git pull
git submodule update --remote --merge
```

### Work on a Submodule

```bash
# Go to the submodule
cd ~/dorabot_ws/src/nav

# Create a branch
git checkout -b feature-new-mapping

# Make changes
# ... edit files ...

# Commit in submodule
git add .
git commit -m "Add new mapping feature"
git push origin feature-new-mapping

# Update main workspace to point to new commit
cd ~/dorabot_ws
git add src/nav
git commit -m "Update nav submodule: new mapping feature"
git push
```

### Update a Submodule

```bash
# Update specific submodule
cd ~/dorabot_ws
git submodule update --remote src/nav

# Or update all submodules
git submodule update --remote --merge

# Commit the updates
git add .
git commit -m "Update submodules"
git push
```

## Common Operations

### List All Submodules

```bash
cd ~/dorabot_ws
git submodule status
```

### Add New Submodule

```bash
cd ~/dorabot_ws
./add_submodule.sh <repo-url> <local-path>
```

Or manually:
```bash
git submodule add <repo-url> <local-path>
git commit -m "Add <name> submodule"
git push
```

### Remove a Submodule

```bash
# Remove from .gitmodules
git submodule deinit -f src/nav

# Remove from .git/modules
rm -rf .git/modules/src/nav

# Remove from working tree
git rm -f src/nav

# Commit
git commit -m "Remove nav submodule"
git push
```

### Check Submodule Status

```bash
cd ~/dorabot_ws
git submodule status

# More detailed
git submodule foreach git status
```

### Run Command in All Submodules

```bash
cd ~/dorabot_ws

# Check git status in all submodules
git submodule foreach git status

# Pull latest in all submodules
git submodule foreach git pull origin main

# Create branch in all submodules
git submodule foreach git checkout -b feature-xyz
```

## Configuration Repository as Submodule

If you want configs/ as a separate repository:

```bash
cd ~/dorabot_ws/configs
./init_git.sh
git remote add origin git@github.com:your-org/dorabot-configs.git
git push -u origin main

cd ~/dorabot_ws
git submodule add git@github.com:your-org/dorabot-configs.git configs
git commit -m "Add configs submodule"
git push
```

## Best Practices

### 1. Pin Submodule Versions

The main repository tracks specific commits of submodules:

```bash
# Update to specific commit
cd ~/dorabot_ws/src/nav
git checkout <commit-hash>

cd ~/dorabot_ws
git add src/nav
git commit -m "Pin nav to version X.Y.Z"
git push
```

### 2. Use Branches in Submodules

```bash
# Work on feature branch in submodule
cd ~/dorabot_ws/src/nav
git checkout -b feature-xyz
# ... make changes ...
git push origin feature-xyz

# Main repo still points to specific commit
cd ~/dorabot_ws
git add src/nav
git commit -m "Update nav submodule"
```

### 3. Document Submodule Structure

In main README.md:

```markdown
## Submodules

- `src/nav` - Navigation module
  - Repository: git@github.com:your-org/dorabot-nav.git
  - Documentation: src/nav/README.md

- `src/ai_agent` - AI agent module
  - Repository: git@github.com:your-org/dorabot-ai-agent.git
```

### 4. Automated Updates

Create a script to update all submodules:

```bash
#!/bin/bash
cd ~/dorabot_ws
git submodule foreach 'git checkout main && git pull'
git add .
git commit -m "Update all submodules"
git push
```

## Troubleshooting

### Submodule Out of Sync

```bash
cd ~/dorabot_ws
git submodule update --init --recursive
```

### Submodule Detached HEAD

```bash
cd ~/dorabot_ws/src/nav
git checkout main
git pull
cd ~/dorabot_ws
git add src/nav
git commit -m "Update nav to latest main"
```

### Submodule Conflicts

```bash
# Reset submodule to committed state
cd ~/dorabot_ws
git submodule update --force
```

### Clone Failed to Get Submodules

```bash
cd ~/dorabot_ws
git submodule update --init --recursive
```

## GitHub/GitLab Configuration

### .gitmodules File

After adding submodules, you'll have a `.gitmodules` file:

```ini
[submodule "src/nav"]
    path = src/nav
    url = git@github.com:your-org/dorabot-nav.git
[submodule "src/ai_agent"]
    path = src/ai_agent
    url = git@github.com:your-org/dorabot-ai-agent.git
[submodule "configs"]
    path = configs
    url = git@github.com:your-org/dorabot-configs.git
```

### Repository Naming Convention

Suggested naming:
- Main workspace: `dorabot-workspace` or `dorabot`
- Navigation: `dorabot-nav`
- AI Agent: `dorabot-ai-agent`
- Perception: `dorabot-perception`
- Orchestrator: `dorabot-orchestrator`
- Configs: `dorabot-configs`

## CI/CD with Submodules

### GitHub Actions Example

```yaml
name: Build

on: [push, pull_request]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
        with:
          submodules: recursive
      
      - name: Build workspace
        run: |
          source /opt/ros/humble/setup.bash
          colcon build --merge-install
```

## Alternative: Monorepo

If you prefer not to use submodules:

```bash
# Just track everything in one repo
cd ~/dorabot_ws
git init
git add .
git commit -m "Initial commit: Dorabot workspace"
git remote add origin <repo-url>
git push -u origin main
```

Pros:
- Simpler workflow
- Easier for beginners
- Single version control

Cons:
- Larger repository
- Can't version modules independently
- Harder to share modules across projects

## Summary

### Submodules Approach (Recommended)
- ✅ Modular development
- ✅ Independent versioning
- ✅ Reusable modules
- ⚠️ More complex workflow

### Monorepo Approach
- ✅ Simple workflow
- ✅ Easy setup
- ⚠️ Less modular
- ⚠️ Harder to share modules

Choose based on your team size and project complexity.

## Quick Reference

```bash
# Initialize workspace
./init_workspace_git.sh

# Add submodule
./add_submodule.sh <url> <path>

# Clone with submodules
git clone --recurse-submodules <url>

# Update submodules
git submodule update --remote --merge

# Work in submodule
cd src/nav && git checkout -b feature

# Update main after submodule change
git add src/nav && git commit -m "Update"
```

For more information, see:
- Git Submodules: https://git-scm.com/book/en/v2/Git-Tools-Submodules
- Main README: [README.md](README.md)
