# Orchestrator + Navigation Integration Guide

## Overview

The Dorabot orchestrator now supports integrated launching of navigation services, eliminating the need for separate launch commands and preventing duplicate node instances.

## Architecture

```
Orchestrator (main.py)
├── Core Services (always running)
│   ├── AI Agent
│   ├── RealSense Camera
│   └── Perception System
│
├── Navigation Services (optional)
│   ├── Map Generator (--enable-mapping)
│   ├── Map Manager (--enable-mapping)
│   ├── RTAB-Map SLAM (--enable-rtabmap)
│   └── Nav2 Navigation (--enable-navigation)
│
└── HTTP Server (FastAPI)
    └── ROS2 Node (DorabotOrchestratorNode)
```

## Quick Start

### 1. Basic Mode (No Navigation)

```bash
cd ~/dorabot_ws
python3 src/orchestrator/main.py
```

This starts:
- AI Agent
- RealSense Camera
- Perception System
- HTTP orchestrator server

### 2. With Custom Mapping

```bash
cd ~/dorabot_ws
./scripts/start_orchestrator_with_mapping.sh
```

Or directly:
```bash
python3 src/orchestrator/main.py --enable-mapping
```

This adds:
- Map Generator (real-time 2D occupancy grid)
- Map Manager (save/load maps)

### 3. With RTAB-Map SLAM (Recommended)

```bash
cd ~/dorabot_ws
./scripts/start_orchestrator_with_mapping.sh --with-rtabmap
```

Or directly:
```bash
python3 src/orchestrator/main.py --enable-mapping --enable-rtabmap
```

This adds:
- Map Generator
- Map Manager
- RTAB-Map SLAM (robust mapping and localization)

### 4. Full Navigation Suite

```bash
cd ~/dorabot_ws
./scripts/start_orchestrator_full.sh
```

Or directly:
```bash
python3 src/orchestrator/main.py \
    --enable-mapping \
    --enable-rtabmap \
    --enable-navigation
```

This includes everything above plus Nav2 navigation stack.

## Command Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `--lang <zh\|en>` | Language for AI agent | zh |
| `--debug-video-path <path>` | Debug video for testing | None |
| `--print-fps` | Print FPS for perception | False |
| `--skip-sub-services` | Skip all sub-services (minimal mode) | False |
| `--enable-mapping` | Enable map generator and manager | False |
| `--enable-rtabmap` | Enable RTAB-Map SLAM | False |
| `--enable-navigation` | Enable Nav2 navigation stack | False |

## Examples

### Example 1: Development Mode (Chinese UI)
```bash
python3 src/orchestrator/main.py --lang zh
```

### Example 2: Mapping with English UI
```bash
python3 src/orchestrator/main.py \
    --enable-mapping \
    --enable-rtabmap \
    --lang en
```

### Example 3: Testing with Debug Video
```bash
python3 src/orchestrator/main.py \
    --debug-video-path /path/to/video.mp4 \
    --print-fps \
    --enable-mapping
```

### Example 4: Full System with Navigation
```bash
python3 src/orchestrator/main.py \
    --enable-mapping \
    --enable-rtabmap \
    --enable-navigation \
    --lang zh
```

## Service Management

### All services are managed by the orchestrator:

1. **Automatic Startup**: All enabled services start together
2. **Unified Logging**: Logs go to `~/logs/<service_name>.log`
3. **Graceful Shutdown**: Ctrl+C stops all services cleanly
4. **Health Monitoring**: Orchestrator monitors all services
5. **Auto-Restart**: If any service crashes, all services stop (prevents inconsistent state)

### Check Service Status

```bash
# View logs
tail -f ~/logs/map_generator.log
tail -f ~/logs/map_manager.log
tail -f ~/logs/rtabmap_slam.log

# List ROS2 nodes
ros2 node list

# Check topics
ros2 topic list
```

## Integration Benefits

### ✅ No Duplicate Launches
- Camera launches only once
- No conflicting node names
- Single source of truth for system state

### ✅ Unified Management
- Start/stop everything with one command
- Centralized logging
- Consistent environment

### ✅ Flexible Configuration
- Enable only what you need
- Easy to extend with new services
- CLI-driven configuration

### ✅ Better Debugging
- All logs in one place
- Clear service startup order
- Easy to isolate issues

## Migrating from Standalone Scripts

### Old Way (Separate Scripts)
```bash
# Terminal 1
./scripts/start_slam.sh

# Terminal 2
python3 src/orchestrator/main.py

# Risk: Camera launched twice, duplicate topics
```

### New Way (Integrated)
```bash
# Single terminal
python3 src/orchestrator/main.py --enable-rtabmap
```

## Configuration Files

Navigation services use the same configuration files as before:

- `src/nav/config/map_generator.yaml` - Map generator parameters
- `src/nav/config/map_manager.yaml` - Map manager settings
- `src/nav/params/mapping_params.yaml` - Advanced mapping parameters

Edit these files to customize behavior.

## Service Interaction

### Map Management Services

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
```

## Troubleshooting

### Services not starting

1. **Check workspace is sourced**:
   ```bash
   source ~/dorabot_ws/install/setup.bash
   ```

2. **Check logs**:
   ```bash
   ls -lh ~/logs/
   cat ~/logs/map_generator.log
   ```

3. **Verify ROS2 packages**:
   ```bash
   ros2 pkg list | grep nav
   ros2 pkg list | grep rtabmap
   ```

### Camera conflicts

If you get camera errors:
```bash
# Kill existing camera processes
pkill -f realsense
pkill -f rs_launch

# Restart orchestrator
python3 src/orchestrator/main.py --enable-mapping
```

### Service crashed

The orchestrator will stop all services if one crashes. Check logs:
```bash
tail -50 ~/logs/<service_name>.log
```

## Performance Considerations

### Resource Usage by Configuration

| Configuration | CPU | Memory | Notes |
|--------------|-----|--------|-------|
| Basic | ~30% | ~500MB | AI + Camera + Perception |
| + Mapping | ~40% | ~700MB | Adds map generation |
| + RTAB-Map | ~60% | ~1.5GB | SLAM is CPU/memory intensive |
| Full Suite | ~80% | ~2GB | All navigation features |

### Optimization Tips

1. **Don't enable what you don't need**
   - Mapping only during exploration
   - RTAB-Map for initial mapping, then use saved maps

2. **Adjust update rates**
   - Lower map_generator update_rate if CPU limited
   - Reduce camera resolution if needed

3. **Monitor resources**
   ```bash
   htop
   ros2 topic hz /map
   ```

## Adding New Services

To add new navigation services, edit `src/orchestrator/services/specs.py`:

```python
if enable_your_feature:
    services.append(
        Service(
            name="your_service",
            command=["ros2", "run", "package", "node"],
            use_process_group=True,
        )
    )
```

Then add CLI option in `src/orchestrator/main.py`:
```python
@click.option("--enable-your-feature", is_flag=True, help="...")
```

## Best Practices

### For Development
```bash
# Start with only what you need
python3 src/orchestrator/main.py --enable-mapping
```

### For Mapping Sessions
```bash
# Use RTAB-Map for best results
./scripts/start_orchestrator_with_mapping.sh --with-rtabmap
```

### For Autonomous Operation
```bash
# Full suite with saved maps
./scripts/start_orchestrator_full.sh
```

### For Testing
```bash
# Minimal mode, start services manually
python3 src/orchestrator/main.py --skip-sub-services
```

## Future Enhancements

- [ ] Dynamic service enable/disable via API
- [ ] Service health monitoring with auto-restart
- [ ] Resource usage monitoring
- [ ] Configuration profiles (dev, prod, demo)
- [ ] Web UI for service management
- [ ] Log aggregation and viewing

## Support

For issues:
1. Check logs in `~/logs/`
2. Review this documentation
3. See `MAPPING_QUICKSTART.md` for mapping-specific help
4. Check ROS2 topics: `ros2 topic list`

## Summary

The integrated orchestrator provides:
- ✅ Single entry point for all services
- ✅ No duplicate launches
- ✅ Flexible configuration
- ✅ Unified logging
- ✅ Graceful shutdown
- ✅ Easy to extend

Use the convenience scripts or call `main.py` directly with the options you need.
