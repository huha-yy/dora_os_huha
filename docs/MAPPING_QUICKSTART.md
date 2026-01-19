# Dorabot Mapping Quick Start Guide

This guide will help you get started with mapping your environment using the Dorabot navigation system.

## Prerequisites

- RealSense D435i camera connected
- ROS2 Humble installed
- Dorabot workspace built

## Setup

1. **Build the workspace:**
   ```bash
   cd ~/dorabot_ws
   colcon build --packages-select nav --merge-install
   source install/setup.bash
   ```

2. **Verify camera connection:**
   ```bash
   rs-enumerate-devices
   ```

## Method 1: Using Orchestrator with RTAB-Map (Recommended)

The integrated orchestrator launches all services together, preventing duplicate nodes.

### Start Mapping

**Option A: Using convenience script**
```bash
cd ~/dorabot_ws
./scripts/start_orchestrator_with_mapping.sh --with-rtabmap
```

**Option B: Direct command**
```bash
cd ~/dorabot_ws
python3 src/orchestrator/main.py --enable-mapping --enable-rtabmap
```

This launches:
- AI Agent
- RealSense camera with depth alignment
- Perception system
- RTAB-Map SLAM node
- Map Generator and Manager
- HTTP orchestrator server

### Alternative: Standalone SLAM (Legacy)

If you prefer the old method without the orchestrator:
```bash
cd ~/dorabot_ws
./scripts/start_slam.sh
```

**Note**: Don't run both methods simultaneously as they will conflict!

### Mapping Tips

1. **Move slowly** - Better feature tracking
2. **Good lighting** - Improves visual features
3. **Rich textures** - Avoid blank walls
4. **Overlap** - Ensure 30-40% overlap between views
5. **Loop closures** - Revisit starting point to close loops

### Save Your Map

Once you're satisfied with the map:

```bash
# Save RTAB-Map's occupancy grid
ros2 run nav2_map_server map_saver_cli -f ~/dorabot_ws/maps/my_room --ros-args -r map:=/rtabmap/map

# Or use the map manager service
ros2 service call /map_manager/save_map std_srvs/srv/Trigger
```

### View Map Files

```bash
ls ~/dorabot_ws/maps/
# You should see: my_room.pgm, my_room.yaml
```

### Stop SLAM

```bash
cd ~/dorabot_ws
./scripts/stop_slam.sh
```

## Method 2: Using Custom Map Generator Only

For lightweight, quick 2D mapping without full SLAM.

**Orchestrator method (recommended)**:
```bash
python3 src/orchestrator/main.py --enable-mapping
```

**Standalone method**:
```bash
ros2 launch nav mapping_full.launch.py \
  launch_rtabmap:=false \
  launch_map_generator:=true
```

### Adjust Parameters

Edit `src/nav/config/map_generator.yaml` to customize:
- Map size and resolution
- Obstacle height detection range
- Update frequency

## Method 3: Full Navigation Suite

Launch everything including Nav2:

**Orchestrator method (recommended)**:
```bash
./scripts/start_orchestrator_full.sh
```

**Standalone method**:
```bash
ros2 launch nav mapping_full.launch.py
```

**Note**: The orchestrator method is preferred as it prevents duplicate launches and provides unified service management.

## Useful Commands

### Check Topics

```bash
# List all topics
ros2 topic list

# View map
ros2 topic echo /map --once

# Monitor camera
ros2 topic hz /camera/camera/color/image_raw
ros2 topic hz /camera/camera/aligned_depth_to_color/image_raw
```

### Check Nodes

```bash
ros2 node list
```

### View TF Tree

```bash
ros2 run tf2_tools view_frames
```

### Check Map Manager Services

```bash
# List available services
ros2 service list | grep map_manager

# Save map
ros2 service call /map_manager/save_map std_srvs/srv/Trigger

# Load map
ros2 service call /map_manager/load_map std_srvs/srv/Trigger

# List saved maps
ros2 service call /map_manager/list_maps std_srvs/srv/Trigger
```

## Visualization in RViz2

### Open RViz with Mapping Config

```bash
rviz2 -d ~/dorabot_ws/src/nav/config/mapping.rviz
```

### What to Look For

1. **Occupancy Grid** - Black = occupied, white = free, gray = unknown
2. **Point Cloud** - 3D representation of the environment
3. **Camera Feed** - RGB and depth images
4. **TF Frames** - Coordinate frame relationships

### RViz Tips

- Use **Orbit view** for 3D visualization
- Toggle displays on/off to reduce clutter
- Adjust topic reliability if data is choppy
- Save your custom RViz config

## Troubleshooting

### Camera not working

```bash
# Check USB connection
lsusb | grep Intel

# Check RealSense
rs-enumerate-devices

# Restart udev rules
sudo udevadm control --reload-rules
sudo udevadm trigger
```

### No map appearing in RViz

1. Check topic: `ros2 topic info /map`
2. Verify frame_id: `ros2 topic echo /map --once | grep frame_id`
3. Set Fixed Frame in RViz to `map`
4. Check QoS settings match (Reliability, Durability)

### Poor map quality

1. **Slow down** - Move camera more slowly
2. **Better lighting** - Add light sources
3. **Adjust parameters** - Edit config files:
   - Increase `depth_max_range` for larger rooms
   - Adjust `min_obstacle_height` and `max_obstacle_height`
   - Increase `map_resolution` for finer detail

### RTAB-Map memory errors

```bash
# Clear RTAB-Map database
rm ~/.ros/rtabmap.db

# Or specify new database location
ros2 launch rtabmap_launch rtabmap.launch.py database_path:=/tmp/rtabmap.db
```

### Build errors

```bash
# Clean and rebuild
cd ~/dorabot_ws
rm -rf build/ install/ log/
colcon build --packages-select nav --merge-install
source install/setup.bash
```

## Next Steps

After creating a map:

1. **Test Navigation** - Use Nav2 for autonomous navigation
2. **Localization** - Use AMCL for robot localization
3. **User Tracking** - Implement person detection and following
4. **Multi-room** - Map multiple rooms and merge

## Configuration Files

- `src/nav/config/map_generator.yaml` - Map generator parameters
- `src/nav/config/map_manager.yaml` - Map persistence settings
- `src/nav/params/mapping_params.yaml` - Advanced mapping parameters
- `src/nav/config/mapping.rviz` - RViz visualization config

## Map File Format

Maps are saved in ROS standard format:

**YAML file** (`my_map.yaml`):
```yaml
image: my_map.pgm
resolution: 0.05          # meters/pixel
origin: [-5.0, -5.0, 0.0] # [x, y, theta]
negate: 0
occupied_thresh: 0.65
free_thresh: 0.196
```

**Image file** (`my_map.pgm`):
- White (254) = Free space
- Black (0) = Occupied
- Gray (205) = Unknown

## Performance Tips

1. **Reduce update rate** if CPU is overloaded
2. **Limit depth range** to reduce point cloud size
3. **Use voxel downsampling** for large point clouds
4. **Disable auto-save** during active mapping
5. **Close unnecessary RViz displays**

## Support

For issues or questions:
- Check logs: `~/dorabot_ws/logs/`
- Review documentation: `src/nav/README.md`
- Module docs: `src/nav/src/mapping/README.md`

## Resources

- [ROS2 Navigation](https://navigation.ros.org/)
- [RTAB-Map](http://introlab.github.io/rtabmap/)
- [RealSense SDK](https://github.com/IntelRealSense/librealsense)
- [Nav2 Map Server](https://navigation.ros.org/configuration/packages/configuring-map-server.html)

Happy Mapping! 🗺️🤖
