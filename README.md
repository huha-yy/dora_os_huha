# Dorabot Workspace

Complete autonomous navigation and assistance robot system.

## Overview

Dorabot is an intelligent robot with:
- **Vision & Perception**: Real-time object detection, fall detection, person tracking
- **Mapping & SLAM**: Real-time map generation with RTAB-Map and custom occupancy grid mapping
- **Navigation**: Autonomous path planning and obstacle avoidance (in development)
- **AI Integration**: Natural language understanding and task orchestration
- **User Tracking**: 3D person localization and following (in development)

## Quick Start

### 1. Basic Operation (AI + Perception)

```bash
cd ~/dorabot_ws
python3 src/orchestrator/main.py
```

This starts:
- AI Agent for natural language processing
- RealSense camera
- Perception system (fall detection, object detection)
- HTTP API server

### 2. With Mapping Capabilities

```bash
cd ~/dorabot_ws
./scripts/start_orchestrator_with_mapping.sh --with-rtabmap
```

This adds:
- RTAB-Map SLAM for robust mapping
- Map Generator for real-time 2D occupancy grids
- Map Manager for saving/loading maps

### 3. Full Navigation Suite

```bash
cd ~/dorabot_ws
./scripts/start_orchestrator_full.sh
```

This includes everything above plus Nav2 navigation stack.

## Architecture

```
dorabot_ws/
├── src/
│   ├── orchestrator/       # Central service orchestration
│   ├── ai_agent/          # Natural language AI
│   ├── perception/        # Vision and detection
│   ├── nav/              # Navigation and mapping
│   │   ├── mapping/      # Map generation module
│   │   ├── navigation/   # Path planning (coming soon)
│   │   └── behaviors/    # Navigation behaviors
│   └── ...
├── scripts/               # Convenience startup scripts
├── maps/                  # Saved navigation maps
└── logs/                  # Service logs
```

## Key Features

### ✅ Implemented

- **Orchestrated Services**: Single entry point for all components
- **Fall Detection**: Real-time fall event detection and alerting
- **Object Detection**: Vision-based object recognition
- **SLAM Mapping**: RTAB-Map integration for 3D SLAM
- **2D Mapping**: Custom occupancy grid generation
- **Map Persistence**: Save and load navigation maps
- **HTTP API**: RESTful API for control and events
- **Multi-language AI**: Chinese and English support

### 🚧 In Development

- **Autonomous Navigation**: Nav2-based path planning
- **User Tracking**: Person detection and following
- **Voice Control**: Natural language commands
- **Multi-room Navigation**: Semantic mapping

## Documentation

- **[docs/](docs/)** - Complete documentation directory ⭐
  - **[Quick Start Guide](docs/QUICK_START_GUIDE.md)** - Start here!
  - [Mapping Guide](docs/MAPPING_QUICKSTART.md) - How to create maps
  - [Configuration System](docs/CONFIG_BASED_ORCHESTRATOR.md) - YAML configs
  - [Service Integration](docs/ORCHESTRATOR_NAVIGATION_INTEGRATION.md) - How it works
  - [Config Repository](docs/CONFIGS_REPOSITORY_GUIDE.md) - Managing configs
  - [Workspace Git Guide](docs/WORKSPACE_GIT_GUIDE.md) - Git repository & submodules

- **[src/nav/](src/nav/)** - Module documentation
  - [Navigation Package](src/nav/README.md) - Package overview
  - [Mapping API](src/nav/src/mapping/README.md) - API reference

- **[configs/](configs/)** - Configuration files
  - [Configs Documentation](configs/README.md) - Config repository

- **[change_logs/](change_logs/)** - Development history
  - [Change Logs](change_logs/README.md) - Implementation details

## Command Reference

### Starting Services

```bash
# Basic mode
python3 src/orchestrator/main.py

# With mapping
python3 src/orchestrator/main.py --enable-mapping

# With SLAM
python3 src/orchestrator/main.py --enable-mapping --enable-rtabmap

# Full navigation
./scripts/start_orchestrator_full.sh

# Custom language
python3 src/orchestrator/main.py --lang en
```

### Map Management

```bash
# Save current map
ros2 service call /map_manager/save_map std_srvs/srv/Trigger

# Load saved map
ros2 service call /map_manager/load_map std_srvs/srv/Trigger

# List available maps
ros2 service call /map_manager/list_maps std_srvs/srv/Trigger

# Reset current map
ros2 service call /map_generator/reset_map std_srvs/srv/Empty
```

### Visualization

```bash
# Open RViz with mapping config
rviz2 -d src/nav/config/mapping.rviz

# View TF tree
ros2 run tf2_tools view_frames

# Monitor topics
ros2 topic list
ros2 topic echo /map
```

### Diagnostics

```bash
# Check running nodes
ros2 node list

# View service logs
tail -f ~/logs/map_generator.log
tail -f ~/logs/rtabmap_slam.log

# Test mapping module
./scripts/test_mapping.sh
```

## Building the Workspace

```bash
cd ~/dorabot_ws
colcon build --merge-install
source install/setup.bash
```

To build specific packages:
```bash
colcon build --packages-select nav --merge-install
```

## Configuration

### Mapping Parameters

Edit `src/nav/config/map_generator.yaml`:
```yaml
map_generator:
  ros__parameters:
    map_resolution: 0.05      # 5cm per pixel
    map_width: 10.0           # 10 meters
    update_rate: 2.0          # 2 Hz
```

### Orchestrator Options

See all options:
```bash
python3 src/orchestrator/main.py --help
```

Key options:
- `--lang <zh|en>` - Language selection
- `--enable-mapping` - Enable map generation
- `--enable-rtabmap` - Enable RTAB-Map SLAM
- `--enable-navigation` - Enable Nav2 navigation
- `--skip-sub-services` - Minimal mode

## System Requirements

### Hardware
- Intel RealSense D435i camera
- 4GB+ RAM (8GB recommended with SLAM)
- Quad-core CPU (or better)
- Ubuntu 22.04 LTS

### Software
- ROS2 Humble
- Python 3.10+
- OpenCV 4.x
- RTAB-Map (optional, for SLAM)
- Nav2 (optional, for navigation)

### Dependencies

```bash
# ROS2 packages
sudo apt install ros-humble-realsense2-camera
sudo apt install ros-humble-rtabmap-ros
sudo apt install ros-humble-nav2-bringup

# Python packages
pip3 install numpy opencv-python pyyaml click uvicorn fastapi
```

## Project Structure

```
dorabot_ws/
├── src/
│   ├── orchestrator/          # Service orchestration
│   │   ├── main.py           # Entry point
│   │   ├── ros_node.py       # ROS2 node
│   │   └── services/         # Service management
│   ├── ai_agent/             # AI assistant
│   ├── perception/           # Vision system
│   └── nav/                  # Navigation module
│       ├── src/mapping/      # Mapping implementation
│       ├── launch/           # Launch files
│       ├── config/           # Configuration
│       └── params/           # Parameters
├── scripts/                   # Convenience scripts
│   ├── start_orchestrator_with_mapping.sh
│   ├── start_orchestrator_full.sh
│   ├── start_slam.sh         # Legacy standalone
│   └── test_mapping.sh
├── maps/                      # Saved maps
├── logs/                      # Service logs
└── docs/                      # Documentation
```

## Troubleshooting

### Camera not detected
```bash
# Check camera
rs-enumerate-devices

# Restart udev
sudo udevadm control --reload-rules
sudo udevadm trigger
```

### Services won't start
```bash
# Check logs
ls -lh ~/logs/
cat ~/logs/<service_name>.log

# Verify workspace is sourced
source ~/dorabot_ws/install/setup.bash

# Kill existing processes
pkill -f orchestrator
pkill -f realsense
```

### Build errors
```bash
# Clean build
rm -rf build/ install/ log/
colcon build --merge-install
```

### Map quality issues
- Move camera slowly
- Ensure good lighting
- Adjust parameters in config files
- See [MAPPING_QUICKSTART.md](MAPPING_QUICKSTART.md)

## Development

### Adding New Features

1. Implement in appropriate module (`src/nav/`, `src/perception/`, etc.)
2. Add service definition to `src/orchestrator/services/specs.py`
3. Add CLI option to `src/orchestrator/main.py`
4. Update documentation
5. Test thoroughly

### Running Tests

```bash
# Test mapping module
./scripts/test_mapping.sh

# Run ROS2 tests
colcon test --packages-select nav
```

## Contributing

1. Create feature branch
2. Implement changes
3. Test thoroughly
4. Update documentation
5. Submit for review

## Roadmap

- [x] Service orchestration
- [x] Fall detection
- [x] SLAM integration
- [x] 2D map generation
- [x] Map persistence
- [ ] Autonomous navigation
- [ ] User tracking and following
- [ ] Voice commands
- [ ] Multi-room navigation
- [ ] Semantic mapping
- [ ] Task scheduling
- [ ] Remote monitoring

## Support

- Documentation: Check the docs in this repository
- Logs: `~/logs/`
- ROS2 topics: `ros2 topic list`
- Service status: `ros2 node list`

## License

Proprietary - Dorabot Project

## Contact

Maintainer: frank (frank123111@gmail.com)

---

**Status**: Active Development  
**Version**: 0.1.0  
**Last Updated**: January 2026
