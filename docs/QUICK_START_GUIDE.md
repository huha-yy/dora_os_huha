# Dorabot Quick Start Guide

## Prerequisites

1. **Virtual Environment**: Create if not exists
   ```bash
   cd ~/dorabot_ws
   uv venv .venv
   source .venv/bin/activate
   uv pip install pyyaml click uvicorn fastapi rclpy numpy opencv-python
   ```
   
   **Note**: The convenience scripts automatically activate the venv. 
   If running Python directly, activate venv first: `source .venv/bin/activate`

2. **ROS2 Workspace**: Source the workspace
   ```bash
   cd ~/dorabot_ws
   source install/setup.bash
   ```

3. **Build Navigation Package** (if not done):
   ```bash
   colcon build --packages-select nav --merge-install
   ```

## Quick Start (Choose One Method)

### Method 1: Basic Operation (No Navigation)

```bash
cd ~/dorabot_ws
python3 src/orchestrator/main.py
```

**What runs:**
- AI Agent
- RealSense Camera
- Perception System

**Use case:** General operation without mapping/navigation

---

### Method 2: With Mapping

```bash
cd ~/dorabot_ws
./scripts/start_orchestrator_with_mapping.sh
```

**What runs:**
- Everything from Method 1
- Map Generator (custom 2D mapping)
- Map Manager (save/load maps)

**Use case:** Create maps with custom generator

---

### Method 3: With SLAM (Recommended for Mapping)

```bash
cd ~/dorabot_ws
./scripts/start_orchestrator_with_mapping.sh --slam
```

**What runs:**
- Everything from Method 2
- RTAB-Map SLAM (robust mapping)

**Use case:** Best quality mapping with loop closure

---

### Method 4: Full Navigation Suite

```bash
cd ~/dorabot_ws
./scripts/start_orchestrator_full.sh
```

**What runs:**
- Everything from Method 3
- Nav2 Navigation Stack

**Use case:** Complete autonomous navigation

---

## Common Operations

### Save a Map

```bash
ros2 service call /map_manager/save_map std_srvs/srv/Trigger
```

### Load a Map

```bash
ros2 service call /map_manager/load_map std_srvs/srv/Trigger
```

### List Saved Maps

```bash
ros2 service call /map_manager/list_maps std_srvs/srv/Trigger
```

### View Map in RViz

```bash
rviz2 -d src/nav/config/mapping.rviz
```

### Check Running Services

```bash
ros2 node list
ros2 topic list
```

### View Logs

```bash
ls -lh ~/logs/
tail -f ~/logs/map_generator.log
tail -f ~/logs/rtabmap_slam.log
```

---

## Configuration Files

The orchestrator uses YAML files for configuration:

| File | Services | Use Case |
|------|----------|----------|
| `config.yaml` | Core only | Basic operation |
| `config_mapping.yaml` | Core + Mapping | Custom mapping |
| `config_slam.yaml` | Core + Mapping + SLAM | Best mapping |
| `config_full.yaml` | All services | Full navigation |

### Use Specific Config

```bash
python3 src/orchestrator/main.py -c src/orchestrator/config_slam.yaml
```

### List Available Configs

```bash
python3 src/orchestrator/main.py --list-configs
```

---

## Customization

### Create Custom Configuration

```bash
cd ~/dorabot_ws/src/orchestrator
cp config.yaml config_custom.yaml
nano config_custom.yaml
```

### Example Custom Config

```yaml
# config_custom.yaml
language: "en"  # English instead of Chinese
venv_path: "~/dorabot_ws/.venv"

services:
  ai_agent: true
  realsense_camera: true
  perception: true
  map_generator: true   # Enable
  map_manager: false    # Disable
  rtabmap_slam: false
  nav2_navigation: false

perception:
  debug_video_path: "/path/to/test/video.mp4"  # Test with video
  print_fps: true  # Show FPS
```

### Use Custom Config

```bash
python3 src/orchestrator/main.py -c src/orchestrator/config_custom.yaml
```

---

## Troubleshooting

### Virtual Environment Issues

**Problem:** Services fail to start
```bash
# Solution: Ensure venv is created and has dependencies
cd ~/dorabot_ws
uv venv .venv
source .venv/bin/activate
uv pip install pyyaml click uvicorn fastapi rclpy numpy opencv-python
```

### Camera Not Found

```bash
# Check camera connection
rs-enumerate-devices

# Restart udev
sudo udevadm control --reload-rules
sudo udevadm trigger
```

### ROS2 Package Not Found

```bash
# Build the package
cd ~/dorabot_ws
colcon build --packages-select nav --merge-install
source install/setup.bash
```

### Service Crashes

```bash
# Check logs
tail -50 ~/logs/<service_name>.log

# Verify configuration
python3 -c "import yaml; print(yaml.safe_load(open('src/orchestrator/config.yaml')))"
```

### YAML Syntax Error

```bash
# Validate all configs
./scripts/validate_configs.sh
```

---

## Useful Commands

### Orchestrator

```bash
# Help
python3 src/orchestrator/main.py --help

# List configs
python3 src/orchestrator/main.py --list-configs

# API server only (no services)
python3 src/orchestrator/main.py --skip-sub-services
```

### Mapping

```bash
# Reset current map
ros2 service call /map_generator/reset_map std_srvs/srv/Empty

# Check map topic
ros2 topic echo /map --once

# Monitor map updates
ros2 topic hz /map
```

### Diagnostics

```bash
# List nodes
ros2 node list

# Check node info
ros2 node info /map_generator

# View TF tree
ros2 run tf2_tools view_frames

# Check topics
ros2 topic list
ros2 topic info /map
```

---

## Documentation

- **CONFIG_BASED_ORCHESTRATOR.md** - Complete configuration guide
- **CONFIG_REFACTOR_COMPLETE.md** - Refactoring summary
- **MAPPING_QUICKSTART.md** - Detailed mapping guide
- **ORCHESTRATOR_NAVIGATION_INTEGRATION.md** - Integration details
- **README.md** - Workspace overview

---

## Examples by Use Case

### Development/Testing

```bash
# Use test video instead of camera
python3 src/orchestrator/main.py -c src/orchestrator/config_custom.yaml

# config_custom.yaml:
# perception:
#   debug_video_path: "/path/to/video.mp4"
```

### Mapping Session

```bash
# Start with SLAM for best results
./scripts/start_orchestrator_with_mapping.sh --slam

# Move robot/camera around room
# Then save map
ros2 service call /map_manager/save_map std_srvs/srv/Trigger
```

### Autonomous Navigation

```bash
# Start with saved map
./scripts/start_orchestrator_full.sh

# Load map
ros2 service call /map_manager/load_map std_srvs/srv/Trigger

# Set navigation goals via RViz
rviz2 -d src/nav/config/mapping.rviz
```

### Minimal Mode (Development)

```bash
# API server only, no sub-services
python3 src/orchestrator/main.py --skip-sub-services

# Then start services manually in other terminals
```

---

## Performance Tips

1. **Don't enable services you don't need**
   - Mapping only when exploring
   - SLAM for initial mapping, then use saved maps

2. **Adjust update rates**
   - Edit `src/nav/config/map_generator.yaml`
   - Lower `update_rate` if CPU limited

3. **Monitor resources**
   ```bash
   htop
   ros2 topic hz /map
   ```

4. **Close unnecessary services**
   - Disable AI agent if not needed
   - Use debug video instead of camera for testing

---

## Next Steps

1. **Test basic operation:**
   ```bash
   python3 src/orchestrator/main.py
   ```

2. **Create your first map:**
   ```bash
   ./scripts/start_orchestrator_with_mapping.sh --slam
   ```

3. **Customize for your needs:**
   - Copy a config file
   - Modify services
   - Test your changes

4. **Learn more:**
   - Read CONFIG_BASED_ORCHESTRATOR.md
   - Explore configuration options
   - Check navigation documentation

---

## Support

- **Logs**: Check `~/logs/` for service logs
- **ROS2**: Use `ros2 topic list` and `ros2 node list`
- **Documentation**: See markdown files in workspace root
- **Configuration**: Validate with `./scripts/validate_configs.sh`

---

## Summary

**Start quickly:**
```bash
cd ~/dorabot_ws
./scripts/start_orchestrator_with_mapping.sh --slam
```

**Create map:**
```bash
ros2 service call /map_manager/save_map std_srvs/srv/Trigger
```

**View map:**
```bash
rviz2 -d src/nav/config/mapping.rviz
```

**That's it!** 🎉
