# Configs Repository Management Guide

## Overview

The Dorabot configuration files have been moved to a dedicated `configs/` directory that can be managed as a separate git repository. This provides better separation of concerns and makes it easier to manage configurations across different environments and teams.

## Directory Structure

```
dorabot_ws/
├── configs/                    # ← Separate repository
│   ├── .git/                  # Git repository
│   ├── .gitignore             # Ignore sensitive files
│   ├── README.md              # Configs documentation
│   ├── init_git.sh            # Initialize git helper
│   │
│   ├── orchestrator/          # Orchestrator configurations
│   │   ├── config.yaml
│   │   ├── config_mapping.yaml
│   │   ├── config_slam.yaml
│   │   └── config_full.yaml
│   │
│   ├── nav/                   # Navigation configurations
│   │   ├── map_generator.yaml
│   │   ├── map_manager.yaml
│   │   └── mapping_params.yaml
│   │
│   ├── examples/              # Example configurations
│   │   ├── dev_environment.yaml
│   │   ├── production.yaml
│   │   └── testing.yaml
│   │
│   └── environments/          # Environment-specific (optional)
│       ├── dev/
│       ├── staging/
│       └── prod/
│
├── src/                       # Source code repository
├── scripts/                   # Helper scripts
└── ...
```

## Quick Start

### Initialize as Git Repository

```bash
cd ~/dorabot_ws/configs
./init_git.sh
```

This will:
- Initialize git repository
- Create initial commit
- Show next steps for adding remote

### Add Remote Repository

```bash
cd ~/dorabot_ws/configs
git remote add origin git@github.com:your-org/dorabot-configs.git
git push -u origin main
```

### Clone on Another Machine

```bash
cd ~/dorabot_ws

# If configs directory doesn't exist
git clone git@github.com:your-org/dorabot-configs.git configs

# Or if it exists but isn't a repo
rm -rf configs
git clone git@github.com:your-org/dorabot-configs.git configs
```

## Usage

### Basic Usage

All scripts and commands now use the new location automatically:

```bash
# Default config (uses configs/orchestrator/config.yaml)
python3 src/orchestrator/main.py

# Specific config
python3 src/orchestrator/main.py -c configs/orchestrator/config_slam.yaml

# Using scripts
./scripts/start_orchestrator.sh
./scripts/start_orchestrator_with_mapping.sh --slam
```

### List Available Configs

```bash
python3 src/orchestrator/main.py --list-configs
```

Output:
```
configs/orchestrator/config.yaml
configs/orchestrator/config_mapping.yaml
configs/orchestrator/config_slam.yaml
configs/orchestrator/config_full.yaml
```

## Managing Configurations

### Creating New Configuration

```bash
cd ~/dorabot_ws/configs/orchestrator

# Copy existing config
cp config.yaml config_custom.yaml

# Edit
nano config_custom.yaml

# Validate
cd ~/dorabot_ws
python3 -c "import yaml; print(yaml.safe_load(open('configs/orchestrator/config_custom.yaml')))"

# Test
python3 src/orchestrator/main.py -c configs/orchestrator/config_custom.yaml --skip-sub-services

# Commit
cd configs
git add orchestrator/config_custom.yaml
git commit -m "Add custom configuration for X"
git push
```

### Updating Existing Configuration

```bash
cd ~/dorabot_ws/configs

# Edit the file
nano orchestrator/config_slam.yaml

# Validate
cd ~/dorabot_ws
./scripts/validate_configs.sh

# Commit
cd configs
git add orchestrator/config_slam.yaml
git commit -m "Update SLAM configuration: enable new camera"
git push
```

### Creating Environment-Specific Configs

```bash
cd ~/dorabot_ws/configs

# Create environment directory
mkdir -p environments/staging

# Create config
cp orchestrator/config_full.yaml environments/staging/orchestrator.yaml

# Customize for staging
nano environments/staging/orchestrator.yaml

# Use it
cd ~/dorabot_ws
python3 src/orchestrator/main.py -c configs/environments/staging/orchestrator.yaml
```

## Best Practices

### 1. Version Control Everything (Except Secrets)

```bash
cd ~/dorabot_ws/configs

# Add all config files
git add orchestrator/ nav/ examples/

# But NOT secrets
# .gitignore already excludes:
# - **/secrets.yaml
# - **/credentials.yaml
# - **/*.secret.yaml
# - *.local.yaml
```

### 2. Use Environment Variables for Secrets

Instead of hardcoding sensitive data:

```yaml
# DON'T DO THIS
database:
  password: "my_secret_password"

# DO THIS
database:
  password: "${DB_PASSWORD}"
```

Then set environment variable:
```bash
export DB_PASSWORD="my_secret_password"
```

### 3. Document Changes

Always document what and why:

```yaml
# configs/orchestrator/config_slam.yaml

# Modified: 2026-01-18
# Author: Frank
# Changes: 
#   - Enabled SLAM for better mapping quality
#   - Increased map resolution to 0.03m
#   - Added depth filtering parameters

language: "zh"
# ... rest of config
```

### 4. Use Branches for Experiments

```bash
cd ~/dorabot_ws/configs

# Create feature branch
git checkout -b experiment-new-slam-params

# Make changes
nano orchestrator/config_slam.yaml

# Commit
git add orchestrator/config_slam.yaml
git commit -m "Experiment: test new SLAM parameters"

# Test thoroughly
cd ~/dorabot_ws
python3 src/orchestrator/main.py -c configs/orchestrator/config_slam.yaml

# If successful, merge
cd configs
git checkout main
git merge experiment-new-slam-params
git push

# If failed, just delete branch
git branch -D experiment-new-slam-params
```

### 5. Keep Examples Updated

When you create a good configuration, share it:

```bash
cd ~/dorabot_ws/configs

# Copy your working config to examples
cp orchestrator/config_custom.yaml examples/mapping_session_setup.yaml

# Add documentation
cat >> examples/mapping_session_setup.yaml << 'EOF'

# This configuration is optimized for mapping sessions
# Features:
#   - RTAB-Map enabled for best quality
#   - Higher update rate for real-time feedback
#   - Debug FPS enabled for monitoring
# 
# Usage:
#   python3 src/orchestrator/main.py -c configs/examples/mapping_session_setup.yaml
EOF

git add examples/mapping_session_setup.yaml
git commit -m "Add example: optimal mapping session setup"
git push
```

## Team Workflow

### For New Team Members

1. **Clone main workspace:**
   ```bash
   git clone <main-repo> ~/dorabot_ws
   cd ~/dorabot_ws
   ```

2. **Clone configs:**
   ```bash
   git clone <configs-repo> configs
   ```

3. **Setup:**
   ```bash
   # Source workspace
   source install/setup.bash
   
   # Test configs
   ./scripts/validate_configs.sh
   ```

### Sharing Configurations

```bash
# Create config on your machine
cd ~/dorabot_ws/configs
cp orchestrator/config.yaml orchestrator/config_my_setup.yaml
# Edit and test...

# Share with team
git add orchestrator/config_my_setup.yaml
git commit -m "Add my setup configuration"
git push

# Teammate pulls
cd ~/dorabot_ws/configs
git pull

# Teammate uses it
cd ~/dorabot_ws
python3 src/orchestrator/main.py -c configs/orchestrator/config_my_setup.yaml
```

### Handling Conflicts

```bash
cd ~/dorabot_ws/configs

# Before making changes, pull latest
git pull

# If there's a conflict
git status  # Shows conflicted files

# Edit conflicted files to resolve
nano orchestrator/config_slam.yaml

# Mark as resolved
git add orchestrator/config_slam.yaml
git commit -m "Resolve conflict: merge SLAM config changes"
git push
```

## Environment-Specific Deployments

### Development Environment

```yaml
# configs/environments/dev/orchestrator.yaml
language: "en"
services:
  ai_agent: false          # Faster startup
  realsense_camera: false  # Use test video
  perception: true
  map_generator: true
  
perception:
  debug_video_path: "/home/frank/test_videos/room.mp4"
  print_fps: true
```

Usage:
```bash
export DORABOT_ENV=dev
python3 src/orchestrator/main.py -c configs/environments/$DORABOT_ENV/orchestrator.yaml
```

### Production Environment

```yaml
# configs/environments/prod/orchestrator.yaml
language: "zh"
services:
  ai_agent: true
  realsense_camera: true
  perception: true
  map_generator: false
  map_manager: true        # Load pre-built maps
  nav2_navigation: true
  
perception:
  debug_video_path: null   # Use real camera
  print_fps: false         # No debug output
```

## Advanced: Config Encryption

For sensitive configurations, use git-crypt:

### Setup git-crypt

```bash
cd ~/dorabot_ws/configs

# Install git-crypt
sudo apt install git-crypt

# Initialize
git-crypt init

# Add collaborator's GPG key
git-crypt add-gpg-user <gpg-key-id>

# Specify files to encrypt
echo "secrets.yaml filter=git-crypt diff=git-crypt" >> .gitattributes
echo "**/secrets/** filter=git-crypt diff=git-crypt" >> .gitattributes

git add .gitattributes
git commit -m "Add git-crypt for sensitive configs"
```

### Use encrypted secrets

```bash
# Create secrets file (will be encrypted on commit)
cat > orchestrator/secrets.yaml << 'EOF'
api_keys:
  openai: "sk-..."
  firebase: "..."
EOF

git add orchestrator/secrets.yaml
git commit -m "Add API keys (encrypted)"
git push

# On another machine with access
cd ~/dorabot_ws/configs
git pull
git-crypt unlock  # Decrypts files
```

## Validation

### Validate All Configs

```bash
cd ~/dorabot_ws
./scripts/validate_configs.sh
```

### Validate Specific Config

```bash
python3 -c "import yaml; print(yaml.safe_load(open('configs/orchestrator/config.yaml')))"
```

### Validate Before Commit

Create pre-commit hook:

```bash
cd ~/dorabot_ws/configs

cat > .git/hooks/pre-commit << 'EOF'
#!/bin/bash
cd "$(git rev-parse --show-toplevel)/.."
./scripts/validate_configs.sh
if [ $? -ne 0 ]; then
    echo "Config validation failed! Commit aborted."
    exit 1
fi
EOF

chmod +x .git/hooks/pre-commit
```

## Backup Strategy

### Automatic Backups

```bash
# Create backup script
cat > ~/dorabot_ws/configs/backup.sh << 'EOF'
#!/bin/bash
BACKUP_DIR=~/dorabot_backups/configs
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p "$BACKUP_DIR"
cd ~/dorabot_ws
tar -czf "$BACKUP_DIR/configs_$DATE.tar.gz" configs/
echo "Backup created: $BACKUP_DIR/configs_$DATE.tar.gz"
EOF

chmod +x ~/dorabot_ws/configs/backup.sh

# Add to crontab for daily backups
crontab -e
# Add: 0 2 * * * ~/dorabot_ws/configs/backup.sh
```

### Restore from Backup

```bash
cd ~/dorabot_ws
tar -xzf ~/dorabot_backups/configs/configs_20260118_020000.tar.gz
```

## Troubleshooting

### Config Not Found

```bash
# Check if configs directory exists
ls -la ~/dorabot_ws/configs/

# Check if it's a git repo
cd ~/dorabot_ws/configs
git status

# If not a repo, initialize
./init_git.sh
```

### Wrong Config Location

If you get "config not found" errors:

```bash
# Check your command
python3 src/orchestrator/main.py -c configs/orchestrator/config.yaml

# NOT this (old location)
python3 src/orchestrator/main.py -c src/orchestrator/config.yaml
```

### Git Conflicts

```bash
cd ~/dorabot_ws/configs
git status  # See what's conflicted
git diff    # See the differences

# Resolve manually or
git checkout --theirs <file>  # Use their version
# or
git checkout --ours <file>    # Use your version

git add <file>
git commit
```

## Migration Checklist

- [x] Configs moved to `configs/` directory
- [x] Paths updated in all config files
- [x] Scripts updated to use new paths
- [x] Config loader updated
- [x] Validation script updated
- [x] .gitignore created
- [x] README created
- [x] Example configs created
- [x] Git init script created
- [ ] Initialize git repository: `cd configs && ./init_git.sh`
- [ ] Add remote and push
- [ ] Update team documentation
- [ ] Test on clean machine

## Summary

The configs repository provides:

✅ **Separation of Concerns** - Configs separate from code  
✅ **Version Control** - Track configuration changes  
✅ **Environment Management** - Different configs for dev/staging/prod  
✅ **Team Collaboration** - Easy to share configurations  
✅ **Security** - Gitignore for secrets, optional encryption  
✅ **Flexibility** - Easy to manage across machines  

**Next Steps:**
1. Initialize git: `cd ~/dorabot_ws/configs && ./init_git.sh`
2. Add remote repository
3. Push configs
4. Share with team

For more information, see `configs/README.md`.
