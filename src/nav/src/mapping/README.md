# Dorabot Mapping Module

This module provides real-time 2D map generation from RealSense camera input for robot navigation.

## Features

- **Real-time Map Generation**: Convert RealSense depth and RGB data into 2D occupancy grids
- **Point Cloud Processing**: Filter, downsample, and process 3D point clouds
- **Map Persistence**: Save and load maps in ROS-compatible format (PGM/PNG + YAML)
- **Flexible Mapping**: Use RTAB-Map SLAM or custom map generator
- **Occupancy Grid Mapping**: Log-odds based occupancy grid with ray tracing for free space
- **Map Post-processing**: Morphological operations and obstacle inflation

## Architecture

```
mapping/
├── map_generator.py      # Real-time map generation from camera
├── map_processor.py      # Point cloud and grid processing utilities
├── map_manager.py        # Map saving, loading, and management
└── README.md            # This file
```

## Nodes

### 1. Map Generator Node

Generates 2D occupancy grids in real-time from RealSense camera data.

**Subscribed Topics:**
- `/camera/camera/color/image_raw` (sensor_msgs/Image) - RGB image
- `/camera/camera/aligned_depth_to_color/image_raw` (sensor_msgs/Image) - Depth image
- `/camera/camera/color/camera_info` (sensor_msgs/CameraInfo) - Camera intrinsics

**Published Topics:**
- `/map_generator/occupancy_grid` (nav_msgs/OccupancyGrid) - Generated occupancy grid
- `/map_generator/map_metadata` (nav_msgs/MapMetaData) - Map metadata

**Services:**
- `~/reset_map` (std_srvs/Empty) - Reset the map to empty state

**Parameters:**
- `map_resolution` (float, default: 0.05) - Grid resolution in meters/pixel
- `map_width` (float, default: 10.0) - Map width in meters
- `map_height` (float, default: 10.0) - Map height in meters
- `min_obstacle_height` (float, default: 0.1) - Minimum obstacle height in meters
- `max_obstacle_height` (float, default: 2.0) - Maximum obstacle height in meters
- `depth_max_range` (float, default: 5.0) - Maximum depth range in meters
- `depth_min_range` (float, default: 0.3) - Minimum depth range in meters
- `update_rate` (float, default: 2.0) - Map update frequency in Hz

### 2. Map Manager Node

Handles map persistence, loading, and management.

**Subscribed Topics:**
- `/rtabmap/map` (nav_msgs/OccupancyGrid) - Map from RTAB-Map
- `/map_generator/occupancy_grid` (nav_msgs/OccupancyGrid) - Map from generator

**Published Topics:**
- `/map` (nav_msgs/OccupancyGrid) - Current active map

**Services:**
- `~/save_map` (std_srvs/Trigger) - Save current map to disk
- `~/load_map` (std_srvs/Trigger) - Load default map from disk
- `~/get_map` (nav_msgs/GetMap) - Get current map
- `~/list_maps` (std_srvs/Trigger) - List all available maps

**Parameters:**
- `map_directory` (string, default: "~/dorabot_ws/maps") - Directory for map storage
- `default_map_name` (string, default: "home") - Default map name
- `enable_auto_save` (bool, default: false) - Enable automatic map saving
- `auto_save_interval` (float, default: 300.0) - Auto-save interval in seconds

## Usage

### Quick Start with RTAB-Map (Recommended)

Use the existing SLAM script for complete SLAM mapping:

```bash
cd ~/dorabot_ws
./scripts/start_slam.sh
```

This will start:
- RealSense camera
- RTAB-Map SLAM for mapping and localization
- RViz2 for visualization

To save the map:
```bash
ros2 run nav2_map_server map_saver_cli -f ~/dorabot_ws/maps/my_map --ros-args -r map:=/rtabmap/map
```

### Launch All Mapping Components

```bash
ros2 launch nav mapping_full.launch.py
```

Options:
- `launch_realsense:=true` - Launch RealSense camera
- `launch_rtabmap:=true` - Launch RTAB-Map SLAM
- `launch_map_generator:=false` - Launch custom map generator
- `launch_rviz:=true` - Launch RViz2 visualization

### Launch Individual Components

**Map Generator only:**
```bash
ros2 launch nav map_generator.launch.py
```

**Map Manager only:**
```bash
ros2 launch nav map_manager.launch.py
```

### Save and Load Maps

**Save current map:**
```bash
ros2 service call /map_manager/save_map std_srvs/srv/Trigger
```

**Load saved map:**
```bash
ros2 service call /map_manager/load_map std_srvs/srv/Trigger
```

**List available maps:**
```bash
ros2 service call /map_manager/list_maps std_srvs/srv/Trigger
```

## Configuration

### Map Generator Configuration

Edit `config/map_generator.yaml`:

```yaml
map_generator:
  ros__parameters:
    map_resolution: 0.05      # 5cm per pixel
    map_width: 10.0           # 10 meters wide
    map_height: 10.0          # 10 meters deep
    min_obstacle_height: 0.1  # Detect obstacles above 10cm
    max_obstacle_height: 2.0  # Detect obstacles below 2m
    update_rate: 2.0          # Update at 2 Hz
```

### Map Manager Configuration

Edit `config/map_manager.yaml`:

```yaml
map_manager:
  ros__parameters:
    map_directory: '~/dorabot_ws/maps'
    default_map_name: 'home'
    enable_auto_save: false
    auto_save_interval: 300.0  # 5 minutes
```

## Map Processing Utilities

The `map_processor.py` module provides utilities for:

### Point Cloud Processing

```python
from mapping.map_processor import PointCloudProcessor, CameraIntrinsics

intrinsics = CameraIntrinsics(fx=614.0, fy=614.0, cx=320.0, cy=240.0, width=640, height=480)
processor = PointCloudProcessor(intrinsics)

# Convert depth image to point cloud
points, colors = processor.depth_to_pointcloud(depth_image, color_image)

# Filter by depth range
filtered_points, mask = processor.filter_by_depth(points, min_depth=0.3, max_depth=5.0)

# Remove outliers
clean_points, mask = processor.remove_outliers(points)

# Downsample
downsampled = processor.downsample_voxel(points, voxel_size=0.05)
```

### Occupancy Grid Mapping

```python
from mapping.map_processor import OccupancyGridMapper

mapper = OccupancyGridMapper(resolution=0.05, width=10.0, height=10.0)

# Update map from point cloud
mapper.update_from_points(points, sensor_position=(0.0, 0.0))

# Get occupancy grid
occupancy = mapper.get_occupancy_grid()

# Apply post-processing
cleaned = mapper.apply_morphology(kernel_size=3, operation='closing')
inflated = mapper.inflate_obstacles(inflation_radius=0.3)
```

## Visualization

Open RViz2 with the mapping configuration:

```bash
rviz2 -d ~/dorabot_ws/src/nav/config/mapping.rviz
```

The configuration includes:
- RTAB-Map occupancy grid
- Generated map (from map_generator)
- Published map (from map_manager)
- RGB and depth camera images
- 3D point cloud
- TF frames
- Navigation path

## Troubleshooting

### No map is being generated

1. Check camera topics:
   ```bash
   ros2 topic list | grep camera
   ros2 topic echo /camera/camera/color/camera_info --once
   ```

2. Check if map_generator is running:
   ```bash
   ros2 node list | grep map_generator
   ```

3. Verify topic connections:
   ```bash
   ros2 topic info /map_generator/occupancy_grid
   ```

### Map quality is poor

1. Adjust obstacle height range in config
2. Increase update rate for faster mapping
3. Ensure proper camera calibration
4. Check depth alignment is enabled
5. Reduce depth noise by moving slowly

### Cannot save map

1. Check map directory exists and is writable:
   ```bash
   ls -ld ~/dorabot_ws/maps
   ```

2. Verify map_manager is receiving map data:
   ```bash
   ros2 topic echo /map --once
   ```

## Integration with Navigation

The mapping module integrates with the navigation stack:

1. **SLAM Mode**: Use RTAB-Map for simultaneous localization and mapping
2. **Localization Mode**: Load a saved map and use it for navigation
3. **Hybrid Mode**: Use map_generator for quick 2D mapping while navigating

Next steps:
- See `../navigation/` for path planning and obstacle avoidance
- See `../localization/` for robot localization on the map
- See `../orchestrator/` for high-level autonomous behavior

## Dependencies

Required ROS2 packages:
- `realsense2_camera` - RealSense camera driver
- `rtabmap_ros` - RTAB-Map SLAM (optional but recommended)
- `nav2_map_server` - Map server for navigation
- `rviz2` - Visualization
- `cv_bridge` - OpenCV-ROS bridge

Python dependencies:
- `numpy`
- `opencv-python` (cv2)
- `pyyaml`

## Future Enhancements

- [ ] Multi-floor mapping support
- [ ] 3D occupancy grid (OctoMap integration)
- [ ] Dynamic obstacle tracking
- [ ] Map merging from multiple sources
- [ ] Semantic mapping (object detection integration)
- [ ] Loop closure detection in custom generator
- [ ] GPU acceleration for point cloud processing
