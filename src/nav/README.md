# Dorabot Navigation Package

Complete navigation system for the Dorabot robot with mapping, localization, and path planning capabilities.

## Overview

The `nav` package provides comprehensive navigation functionality for Dorabot:

1. **Mapping**: Real-time 2D map generation from RealSense camera
2. **Navigation**: Path planning and obstacle avoidance (coming soon)
3. **User Tracking**: 3D localization and following (coming soon)

## Package Structure

```
nav/
├── src/
│   ├── mapping/              # Map generation module
│   │   ├── map_generator.py  # Real-time map generation
│   │   ├── map_processor.py  # Point cloud processing utilities
│   │   ├── map_manager.py    # Map persistence
│   │   └── README.md         # Mapping documentation
│   ├── navigation/           # Navigation module (coming soon)
│   ├── behaviors/            # Behavior primitives
│   ├── core/                 # Core utilities
│   ├── orchestrator/         # High-level autonomy
│   └── utils/               # Helper utilities
├── launch/                   # Launch files
├── config/                   # Configuration files
├── params/                   # Parameter files
└── README.md                # This file
```

## Quick Start

### 1. Build the Package

```bash
cd ~/dorabot_ws
colcon build --packages-select nav
source install/setup.bash
```

### 2. Run SLAM Mapping

```bash
# Using the convenience script
./scripts/start_slam.sh

# Or launch directly
ros2 launch nav mapping_full.launch.py
```

### 3. Save Your Map

After mapping your environment:

```bash
ros2 service call /map_manager/save_map std_srvs/srv/Trigger
```

## Features

### Mapping Module ✅

- **Real-time map generation** from RealSense D435i camera
- **RTAB-Map SLAM** integration for robust mapping and localization
- **Custom map generator** for lightweight 2D mapping
- **Map persistence** in ROS-compatible format (PGM/YAML)
- **Point cloud processing** utilities
- **Occupancy grid mapping** with ray tracing

See [src/mapping/README.md](src/mapping/README.md) for detailed documentation.

### Navigation Module 🚧 (Coming Soon)

- Path planning with Nav2 integration
- Dynamic obstacle avoidance
- Goal-based navigation
- Waypoint following

### User Tracking Module 🚧 (Coming Soon)

- 3D person detection and tracking
- Follow-me behavior
- Safe approach and distance keeping
- Multi-person tracking

## Available Launch Files

### Mapping

- `mapping_full.launch.py` - Complete mapping system (camera + SLAM + manager)
- `map_generator.launch.py` - Custom map generator only
- `map_manager.launch.py` - Map persistence service only

### Navigation (Coming Soon)

- `navigation.launch.py` - Full navigation stack
- `local_navigation.launch.py` - Local planning only

## Configuration

### Mapping Parameters

Edit `config/map_generator.yaml` or `config/map_manager.yaml`:

```yaml
map_generator:
  ros__parameters:
    map_resolution: 0.05      # Grid resolution (meters/pixel)
    map_width: 10.0           # Map width (meters)
    map_height: 10.0          # Map height (meters)
    update_rate: 2.0          # Update frequency (Hz)
```

### Navigation Parameters (Coming Soon)

Edit `config/navigation.yaml` for path planning and control parameters.

## Services

### Mapping Services

```bash
# Save current map
ros2 service call /map_manager/save_map std_srvs/srv/Trigger

# Load saved map
ros2 service call /map_manager/load_map std_srvs/srv/Trigger

# List available maps
ros2 service call /map_manager/list_maps std_srvs/srv/Trigger

# Reset map
ros2 service call /map_generator/reset_map std_srvs/srv/Empty
```

## Topics

### Subscribed Topics

- `/camera/camera/color/image_raw` (sensor_msgs/Image) - RGB image
- `/camera/camera/aligned_depth_to_color/image_raw` (sensor_msgs/Image) - Depth image
- `/camera/camera/color/camera_info` (sensor_msgs/CameraInfo) - Camera info

### Published Topics

- `/map` (nav_msgs/OccupancyGrid) - Current navigation map
- `/map_generator/occupancy_grid` (nav_msgs/OccupancyGrid) - Generated map
- `/rtabmap/map` (nav_msgs/OccupancyGrid) - RTAB-Map SLAM map

## Development

### Adding New Modules

1. Create module directory under `src/`
2. Add entry point in `setup.py`
3. Create launch file in `launch/`
4. Add configuration in `config/`
5. Update this README

### Running Tests

```bash
cd ~/dorabot_ws
colcon test --packages-select nav
```

## Dependencies

### ROS2 Packages

- `rclpy` - ROS2 Python client library
- `realsense2_camera` - RealSense camera driver
- `rtabmap_ros` - RTAB-Map SLAM
- `nav2_map_server` - Map server
- `cv_bridge` - OpenCV-ROS bridge

### Python Packages

- `numpy` - Numerical computing
- `opencv-python` - Computer vision
- `pyyaml` - YAML parsing

### Installation

```bash
# ROS2 packages
sudo apt install ros-humble-realsense2-camera
sudo apt install ros-humble-rtabmap-ros
sudo apt install ros-humble-nav2-map-server

# Python packages
pip3 install numpy opencv-python pyyaml
```

## Troubleshooting

### Camera not detected

```bash
# Check camera connection
rs-enumerate-devices

# Check ROS topics
ros2 topic list | grep camera
```

### SLAM not working

1. Ensure depth alignment is enabled
2. Check TF frames: `ros2 run tf2_tools view_frames`
3. Verify camera topics are publishing
4. Move camera slowly for better feature tracking

### Build errors

```bash
# Clean build
cd ~/dorabot_ws
rm -rf build/ install/ log/
colcon build --packages-select nav
```

## Scripts

Convenience scripts in `~/dorabot_ws/scripts/`:

- `start_slam.sh` - Start SLAM mapping
- `stop_slam.sh` - Stop SLAM
- `start_nav_local_map.sh` - Start navigation with local mapping
- `stop_nav_local_map.sh` - Stop navigation

## Roadmap

- [x] Mapping module with RealSense integration
- [x] Map saving and loading
- [x] RTAB-Map SLAM integration
- [ ] Navigation module with Nav2
- [ ] Local path planning
- [ ] Dynamic obstacle avoidance
- [ ] User detection and tracking
- [ ] Follow-me behavior
- [ ] Multi-room navigation
- [ ] Semantic mapping
- [ ] Voice command integration

## Contributing

1. Create feature branch
2. Implement changes
3. Test thoroughly
4. Submit for review

## License

Proprietary - Dorabot Project

## Contact

Maintainer: frank (frank123111@gmail.com)
