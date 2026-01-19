# Dorabot Configuration Repository

This directory contains all configuration files for the Dorabot system. It can be maintained as a separate git repository for easier management across different environments.

## Structure

```
configs/
├── orchestrator/          # Orchestrator service configurations
│   ├── config.yaml       # Basic mode
│   ├── config_mapping.yaml
│   ├── config_slam.yaml
│   └── config_full.yaml
├── nav/                  # Navigation module configurations
│   ├── map_generator.yaml
│   ├── map_manager.yaml
│   └── mapping_params.yaml
├── examples/             # Example configurations
├── environments/         # Environment-specific configs (optional)
│   ├── dev/
│   ├── staging/
│   └── prod/
└── README.md            # This file
```

## Usage

### With Orchestrator

```bash
# Use default config
python3 src/orchestrator/main.py

# Use specific config
python3 src/orchestrator/main.py -c configs/orchestrator/config_slam.yaml

# Use environment-specific config
python3 src/orchestrator/main.py -c configs/environments/prod/orchestrator.yaml
```

### Direct Paths

The orchestrator configs reference navigation configs:

```yaml
# In orchestrator config
mapping:
  config_file: "configs/nav/map_generator.yaml"
```

## Configuration Types

### Orchestrator Configurations

Located in `orchestrator/`:

- **config.yaml** - Basic operation (core services only)
- **config_mapping.yaml** - With custom mapping
- **config_slam.yaml** - With RTAB-Map SLAM
- **config_full.yaml** - Full navigation suite

### Navigation Configurations

Located in `nav/`:

- **map_generator.yaml** - Map generation parameters
- **map_manager.yaml** - Map persistence settings
- **mapping_params.yaml** - Advanced mapping parameters

## Environment-Specific Configurations

For different deployment environments, create subdirectories:

```
environments/
├── dev/
│   └── orchestrator.yaml      # Development settings
├── staging/
│   └── orchestrator.yaml      # Staging settings
└── prod/
    └── orchestrator.yaml      # Production settings
```

### Example Environment Config

```yaml
# environments/dev/orchestrator.yaml
language: "en"
venv_path: "~/dorabot_ws/.venv"

services:
  ai_agent: false          # Disabled in dev
  realsense_camera: false  # Use test video
  perception: true
  map_generator: true
  map_manager: true
  rtabmap_slam: false
  nav2_navigation: false

perception:
  debug_video_path: "/home/frank/test_videos/room.mp4"
  print_fps: true

camera:
  align_depth: true
```

## Managing as Separate Repository

### Initialize as Git Repository

```bash
cd ~/dorabot_ws/configs
git init
git add .
git commit -m "Initial configuration repository"

# Add remote (if you have one)
git remote add origin <your-config-repo-url>
git push -u origin main
```

### .gitignore for Sensitive Data

```gitignore
# Sensitive configurations
**/secrets.yaml
**/credentials.yaml
**/*.secret.yaml

# Local overrides
*.local.yaml
.env

# Temporary files
*.tmp
*.bak
*~
```

### Usage with Team

1. **Clone the config repo:**
   ```bash
   cd ~/dorabot_ws
   git clone <config-repo-url> configs
   ```

2. **Use in orchestrator:**
   ```bash
   python3 src/orchestrator/main.py -c configs/orchestrator/config_slam.yaml
   ```

3. **Pull updates:**
   ```bash
   cd ~/dorabot_ws/configs
   git pull
   ```

## Best Practices

### 1. Version Control

```bash
# Commit configuration changes
cd ~/dorabot_ws/configs
git add orchestrator/config_slam.yaml
git commit -m "Update SLAM configuration for new camera"
git push
```

### 2. Environment Variables

For sensitive data, use environment variables:

```yaml
# config.yaml
database:
  host: "${DB_HOST}"
  password: "${DB_PASSWORD}"
```

### 3. Configuration Validation

```bash
# Validate before committing
cd ~/dorabot_ws
./scripts/validate_configs.sh
```

### 4. Documentation

Always document changes:

```yaml
# config_slam.yaml
# Modified: 2026-01-18
# Author: Frank
# Changes: Enabled SLAM for better mapping quality

language: "zh"
# ... rest of config
```

### 5. Backup Sensitive Configs

Keep sensitive configs encrypted or in a secure vault:

```bash
# Example: Using git-crypt
git-crypt init
echo "secrets.yaml filter=git-crypt diff=git-crypt" >> .gitattributes
git-crypt add-gpg-user <key-id>
```

## Configuration Templates

### Creating New Configurations

1. **Copy an existing config:**
   ```bash
   cd ~/dorabot_ws/configs/orchestrator
   cp config.yaml config_custom.yaml
   ```

2. **Modify as needed:**
   ```bash
   nano config_custom.yaml
   ```

3. **Validate:**
   ```bash
   cd ~/dorabot_ws
   python3 -c "import yaml; print(yaml.safe_load(open('configs/orchestrator/config_custom.yaml')))"
   ```

4. **Test:**
   ```bash
   python3 src/orchestrator/main.py -c configs/orchestrator/config_custom.yaml --skip-sub-services
   ```

5. **Commit:**
   ```bash
   cd configs
   git add orchestrator/config_custom.yaml
   git commit -m "Add custom configuration for X"
   git push
   ```

## Sharing Configurations

### Export Configuration

```bash
# Create shareable configuration
cd ~/dorabot_ws/configs
cp orchestrator/config_slam.yaml examples/mapping_session_example.yaml

# Document it
echo "# Example configuration for mapping sessions" >> examples/mapping_session_example.yaml
```

### Import Configuration

```bash
# Received a config from teammate
cd ~/dorabot_ws/configs/examples
# Place the file here
git add examples/new_config.yaml
git commit -m "Add configuration from teammate"
```

## Troubleshooting

### Config Not Found

```bash
# Check if configs directory exists
ls -la ~/dorabot_ws/configs/

# Check specific config
ls -la ~/dorabot_ws/configs/orchestrator/config.yaml
```

### Path Issues

All paths in configs should be relative to workspace root:

```yaml
# Correct
mapping:
  config_file: "configs/nav/map_generator.yaml"

# Incorrect (absolute path)
mapping:
  config_file: "/home/frank/dorabot_ws/configs/nav/map_generator.yaml"
```

### Validation

```bash
# Validate all configs
cd ~/dorabot_ws
./scripts/validate_configs.sh

# Validate specific config
python3 -c "import yaml; print(yaml.safe_load(open('configs/orchestrator/config_slam.yaml')))"
```

## Migration Guide

If you're moving from the old location:

1. **Configs are already moved** to `configs/` directory
2. **Update your commands:**
   ```bash
   # Old
   python3 src/orchestrator/main.py -c src/orchestrator/config_slam.yaml
   
   # New
   python3 src/orchestrator/main.py -c configs/orchestrator/config_slam.yaml
   ```

3. **Scripts automatically updated** to use new location

## Advanced Usage

### Multiple Config Files

Load base config and override:

```bash
# Not yet implemented, but possible future feature
python3 src/orchestrator/main.py \
  -c configs/orchestrator/config.yaml \
  --override configs/environments/dev/overrides.yaml
```

### Dynamic Configuration

Use environment-specific configs:

```bash
# Set environment
export DORABOT_ENV=prod

# Load config based on environment
python3 src/orchestrator/main.py -c configs/environments/$DORABOT_ENV/orchestrator.yaml
```

### Configuration Validation Script

```python
#!/usr/bin/env python3
# configs/validate.py
import yaml
import sys
from pathlib import Path

def validate_config(config_file):
    try:
        with open(config_file) as f:
            config = yaml.safe_load(f)
        
        # Check required keys
        required = ['language', 'orchestrator_port', 'venv_path', 'services']
        for key in required:
            if key not in config:
                print(f"ERROR: Missing required key: {key}")
                return False
        
        print(f"✓ {config_file} is valid")
        return True
    except Exception as e:
        print(f"ERROR in {config_file}: {e}")
        return False

if __name__ == "__main__":
    configs = Path("orchestrator").glob("*.yaml")
    all_valid = all(validate_config(c) for c in configs)
    sys.exit(0 if all_valid else 1)
```

## Support

- **Validation**: `./scripts/validate_configs.sh`
- **Documentation**: See main workspace docs
- **Examples**: Check `examples/` directory

## Summary

This directory contains all Dorabot configurations:
- ✅ Centralized configuration management
- ✅ Version controlled
- ✅ Environment-specific configs
- ✅ Team collaboration ready
- ✅ Separate from code repository

For usage, see **QUICK_START_GUIDE.md** in the main workspace.
