# Configuration-Based Orchestrator Guide

## Overview

The Dorabot orchestrator now uses YAML configuration files to control which services are enabled. This provides a cleaner, more maintainable approach compared to multiple CLI flags.

## Key Features

✅ **Configuration Files**: YAML-based service configuration  
✅ **Virtual Environment**: Automatic uv venv activation  
✅ **Preset Configs**: Ready-to-use configurations for common scenarios  
✅ **Flexible**: Easy to create custom configurations  
✅ **Cleaner CLI**: Simple `--config` option instead of many flags

## Quick Start

### Method 1: Using Scripts (Recommended)

```bash
# Basic mode (core services only)
./scripts/start_orchestrator.sh

# With mapping
./scripts/start_orchestrator_with_mapping.sh

# With SLAM
./scripts/start_orchestrator_with_mapping.sh --slam

# Full navigation suite
./scripts/start_orchestrator_full.sh
```

### Method 2: Direct Python Command

```bash
# Default configuration
python3 src/orchestrator/main.py

# Specific configuration
python3 src/orchestrator/main.py -c src/orchestrator/config_slam.yaml

# List available configurations
python3 src/orchestrator/main.py --list-configs
```

## Available Configurations

### 1. config.yaml - Basic Mode

**Services**: AI Agent, Camera, Perception  
**Use Case**: Default operation without navigation

```bash
python3 src/orchestrator/main.py -c src/orchestrator/config.yaml
```

### 2. config_mapping.yaml - With Mapping

**Services**: Basic + Map Generator + Map Manager  
**Use Case**: Custom 2D mapping without SLAM

```bash
python3 src/orchestrator/main.py -c src/orchestrator/config_mapping.yaml
```

### 3. config_slam.yaml - With SLAM

**Services**: Basic + Mapping + RTAB-Map SLAM  
**Use Case**: Robust mapping with loop closure (recommended)

```bash
python3 src/orchestrator/main.py -c src/orchestrator/config_slam.yaml
```

### 4. config_full.yaml - Full Navigation

**Services**: All above + Nav2 Navigation  
**Use Case**: Complete autonomous navigation

```bash
python3 src/orchestrator/main.py -c src/orchestrator/config_full.yaml
```

## Configuration File Structure

### Example: config_slam.yaml

```yaml
# Orchestrator Configuration - With SLAM

# Core settings
language: "zh"  # Language for AI agent
orchestrator_port: 8000
venv_path: "~/dorabot_ws/.venv"  # Virtual environment path

# Service control (enable/disable services)
services:
  ai_agent: true
  realsense_camera: true
  perception: true
  map_generator: true
  map_manager: true
  rtabmap_slam: true   # Enable SLAM
  nav2_navigation: false

# Service-specific settings
perception:
  debug_video_path: null  # Use real camera
  print_fps: false

camera:
  align_depth: true  # Required for mapping

mapping:
  config_file: "src/nav/config/map_generator.yaml"

map_manager:
  config_file: "src/nav/config/map_manager.yaml"

rtabmap:
  rgb_topic: "/camera/camera/color/image_raw"
  depth_topic: "/camera/camera/aligned_depth_to_color/image_raw"
  camera_info_topic: "/camera/camera/color/camera_info"
  approx_sync: true
  frame_id: "camera_link"
```

## Creating Custom Configurations

### Step 1: Copy an Existing Config

```bash
cd ~/dorabot_ws/src/orchestrator
cp config.yaml config_custom.yaml
```

### Step 2: Edit Configuration

```yaml
# config_custom.yaml
language: "en"  # Change language

services:
  ai_agent: true
  realsense_camera: true
  perception: true
  map_generator: true   # Enable custom service
  map_manager: false    # Disable this
  rtabmap_slam: false
  nav2_navigation: false

perception:
  debug_video_path: "/path/to/test/video.mp4"  # Use debug video
  print_fps: true  # Enable FPS display
```

### Step 3: Use Your Config

```bash
python3 src/orchestrator/main.py -c src/orchestrator/config_custom.yaml
```

## Virtual Environment Handling

The orchestrator automatically activates the uv virtual environment specified in the config:

```yaml
venv_path: "~/dorabot_ws/.venv"
```

**What it does:**
1. Expands `~` to home directory
2. Adds venv's `bin/` to PATH
3. Sets VIRTUAL_ENV environment variable
4. Removes PYTHONHOME if set

**If venv doesn't exist:**
- Prints a warning
- Continues with system Python
- Services may fail if dependencies are missing

**To create the venv:**
```bash
cd ~/dorabot_ws
uv venv .venv
uv pip install -r requirements.txt
```

## Service Configuration Details

### Core Services

#### ai_agent
- **Config key**: `services.ai_agent`
- **Command**: `python3 src/ai_agent/run_server.py --lang <language>`
- **Settings**: Uses `language` from config

#### realsense_camera
- **Config key**: `services.realsense_camera`
- **Command**: `ros2 launch realsense2_camera rs_launch.py`
- **Settings**: Uses `camera.align_depth` flag

#### perception
- **Config key**: `services.perception`
- **Command**: `python3 src/perception/main.py [options]`
- **Settings**: Uses `perception.debug_video_path` and `perception.print_fps`

### Navigation Services

#### map_generator
- **Config key**: `services.map_generator`
- **Command**: `ros2 run nav map_generator`
- **Settings**: Uses `mapping.config_file`

#### map_manager
- **Config key**: `services.map_manager`
- **Command**: `ros2 run nav map_manager`
- **Settings**: Uses `map_manager.config_file`

#### rtabmap_slam
- **Config key**: `services.rtabmap_slam`
- **Command**: `ros2 launch rtabmap_launch rtabmap.launch.py`
- **Settings**: Uses all `rtabmap.*` parameters

#### nav2_navigation
- **Config key**: `services.nav2_navigation`
- **Command**: `ros2 launch nav navigation.launch.py`
- **Settings**: None yet (placeholder)

## Migration Guide

### Old CLI Approach

```bash
# Old way with many flags
python3 src/orchestrator/main.py \
    --lang zh \
    --enable-mapping \
    --enable-rtabmap \
    --enable-navigation
```

### New Config Approach

```bash
# New way with config file
python3 src/orchestrator/main.py -c src/orchestrator/config_full.yaml
```

**Benefits:**
- Cleaner command line
- Reusable configurations
- Version controllable
- Easier to document
- More maintainable

## Command Reference

### List Available Configs

```bash
python3 src/orchestrator/main.py --list-configs
```

### Use Specific Config

```bash
python3 src/orchestrator/main.py --config <path>
python3 src/orchestrator/main.py -c <path>
```

### API Server Only (No Services)

```bash
python3 src/orchestrator/main.py --skip-sub-services
```

### Get Help

```bash
python3 src/orchestrator/main.py --help
```

## Script Reference

### start_orchestrator.sh

General purpose launcher with config file selection:

```bash
# Default config
./scripts/start_orchestrator.sh

# Specific config
./scripts/start_orchestrator.sh --config src/orchestrator/config_slam.yaml

# List available configs
./scripts/start_orchestrator.sh --list

# Help
./scripts/start_orchestrator.sh --help
```

### start_orchestrator_with_mapping.sh

Convenience script for mapping modes:

```bash
# Just mapping
./scripts/start_orchestrator_with_mapping.sh

# With SLAM
./scripts/start_orchestrator_with_mapping.sh --slam

# Full navigation
./scripts/start_orchestrator_with_mapping.sh --full

# Custom config
./scripts/start_orchestrator_with_mapping.sh --config my_config.yaml
```

### start_orchestrator_full.sh

Launches complete navigation suite:

```bash
./scripts/start_orchestrator_full.sh
```

## Configuration Best Practices

### 1. Version Control Your Configs

```bash
# Add to git
git add src/orchestrator/config_*.yaml
git commit -m "Add orchestrator configurations"
```

### 2. Environment-Specific Configs

```yaml
# config_dev.yaml - Development
perception:
  debug_video_path: "/path/to/test/video.mp4"
  print_fps: true

# config_prod.yaml - Production
perception:
  debug_video_path: null
  print_fps: false
```

### 3. Document Your Custom Configs

Add comments in YAML:

```yaml
# Custom configuration for testing navigation
# Author: Your Name
# Date: 2026-01-18

services:
  # Disable AI agent for faster testing
  ai_agent: false
  
  # Use debug video instead of camera
  realsense_camera: false
```

### 4. Validate Before Running

Check syntax:
```bash
python3 -c "import yaml; yaml.safe_load(open('src/orchestrator/config.yaml'))"
```

## Troubleshooting

### Config File Not Found

```
Error: FileNotFoundError: Configuration file not found
```

**Solution**: Check the path is relative to workspace root:
```bash
cd ~/dorabot_ws
ls -l src/orchestrator/config.yaml
```

### Virtual Environment Not Activated

```
Warning: Virtual environment not found at ~/dorabot_ws/.venv
```

**Solution**: Create the virtual environment:
```bash
cd ~/dorabot_ws
uv venv .venv
```

### Service Fails to Start

Check logs:
```bash
tail -f ~/logs/<service_name>.log
```

Verify configuration:
```bash
python3 src/orchestrator/main.py -c src/orchestrator/config.yaml --skip-sub-services
```

### YAML Syntax Error

```
Error loading configuration: ...
```

**Solution**: Validate YAML syntax:
```bash
python3 -c "import yaml; print(yaml.safe_load(open('src/orchestrator/config.yaml')))"
```

## Examples

### Example 1: Development Mode

```yaml
# config_dev.yaml
language: "en"
venv_path: "~/dorabot_ws/.venv"

services:
  ai_agent: false  # Disable for faster startup
  realsense_camera: false
  perception: false
  map_generator: true
  map_manager: true
  rtabmap_slam: false
  nav2_navigation: false

perception:
  debug_video_path: "/home/frank/test_videos/room.mp4"
  print_fps: true
```

Usage:
```bash
python3 src/orchestrator/main.py -c src/orchestrator/config_dev.yaml
```

### Example 2: Mapping Session

```yaml
# config_mapping_session.yaml
language: "zh"
venv_path: "~/dorabot_ws/.venv"

services:
  ai_agent: true
  realsense_camera: true
  perception: true
  map_generator: true
  map_manager: true
  rtabmap_slam: true  # Enable SLAM for best mapping
  nav2_navigation: false

camera:
  align_depth: true  # Required for mapping
```

Usage:
```bash
python3 src/orchestrator/main.py -c src/orchestrator/config_mapping_session.yaml
```

### Example 3: Testing Navigation

```yaml
# config_nav_test.yaml
language: "en"
venv_path: "~/dorabot_ws/.venv"

services:
  ai_agent: false
  realsense_camera: true
  perception: false
  map_generator: false
  map_manager: true  # Need this to load saved map
  rtabmap_slam: false
  nav2_navigation: true  # Test navigation only

map_manager:
  config_file: "src/nav/config/map_manager.yaml"
```

Usage:
```bash
python3 src/orchestrator/main.py -c src/orchestrator/config_nav_test.yaml
```

## Summary

The configuration-based approach provides:

✅ **Simplicity**: One config file instead of many flags  
✅ **Flexibility**: Easy to create custom configurations  
✅ **Maintainability**: Version control your setups  
✅ **Clarity**: Clear service dependencies  
✅ **Reusability**: Share configurations across team  

**Migration Path:**
1. Use provided preset configs initially
2. Create custom configs as needed
3. Version control your configurations
4. Share successful configurations with team

**For more information:**
- See preset configs in `src/orchestrator/config*.yaml`
- Check `config_loader.py` for configuration structure
- Review `main.py` for CLI options
