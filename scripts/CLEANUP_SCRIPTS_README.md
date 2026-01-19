# Orchestrator Cleanup Scripts

This directory contains scripts to stop and clean up the Dorabot Orchestrator services.

## Available Scripts

### 1. `stop_orchestrator.sh` - Graceful Shutdown (Recommended)

**Usage:**
```bash
./scripts/stop_orchestrator.sh
```

**What it does:**
- Gracefully stops the orchestrator main process
- Terminates all child services (AI Agent, Perception, Camera, Mapping)
- Cleans up orphaned processes
- Checks for remaining nodes
- **Interactive**: Asks if you want to force-kill remaining nodes

**Use this when:**
- You want to cleanly stop the orchestrator
- After pressing Ctrl+C but some services are still running
- As your normal shutdown method

---

### 2. `force_stop_all.sh` - Nuclear Option ⚠️

**Usage:**
```bash
./scripts/force_stop_all.sh
```

**What it does:**
- **Force kills ALL** ROS2 and orchestrator processes (SIGKILL -9)
- Doesn't ask questions, just terminates everything
- Kills RViz2 as well
- **Requires confirmation** before proceeding

**Use this when:**
- Normal stop doesn't work
- Processes are stuck/unresponsive
- You need a clean slate quickly
- After system errors or crashes

---

## Comparison

| Feature | stop_orchestrator.sh | force_stop_all.sh |
|---------|---------------------|-------------------|
| **Method** | Graceful (SIGTERM → SIGKILL) | Force kill (SIGKILL -9) |
| **Safety** | ✅ Safe | ⚠️ Aggressive |
| **Interactive** | Yes (for remaining nodes) | Yes (confirmation only) |
| **Kills RViz2** | ❌ No | ✅ Yes |
| **Speed** | Slower (waits for processes) | Fast (immediate) |
| **Recommended** | ✅ Default choice | Emergency use |

---

## Common Workflows

### After Ctrl+C on Orchestrator
```bash
# First try graceful stop
./scripts/stop_orchestrator.sh

# If nodes still running, use force
./scripts/force_stop_all.sh
```

### Complete System Reset
```bash
# Stop everything
./scripts/force_stop_all.sh

# Restart ROS2 daemon
ros2 daemon stop && ros2 daemon start

# Start fresh
./scripts/start_orchestrator_with_mapping.sh
```

### Check What's Running
```bash
# List ROS2 nodes
ros2 node list

# List topics
ros2 topic list

# List services
ros2 service list

# Check processes
ps aux | grep -E "(orchestrator|map_generator|realsense)"
```

---

## What Gets Stopped

Both scripts stop:
- ✓ Orchestrator main process
- ✓ AI Agent
- ✓ Perception system
- ✓ RealSense camera node
- ✓ Map generator
- ✓ Map manager
- ✓ Static TF publisher
- ✓ RTAB-Map SLAM (if running)
- ✓ Nav2 navigation (if running)

Additionally, `force_stop_all.sh` stops:
- ✓ RViz2
- ✓ All ROS2 run/launch processes
- ✓ Body tracking

---

## Troubleshooting

### "Processes still running after stop"
→ Use `force_stop_all.sh`

### "Port 8000 already in use"
→ Run `stop_orchestrator.sh` first, then restart

### "Cannot connect to ROS2 nodes"
→ Restart ROS2 daemon:
```bash
ros2 daemon stop
ros2 daemon start
```

### "Script permission denied"
→ Make scripts executable:
```bash
chmod +x scripts/*.sh
```

---

## Notes

- Scripts use colors for better visibility (requires ANSI support)
- All scripts are safe to run multiple times
- No data or maps are deleted (only processes are stopped)
- Scripts check before killing to avoid errors

---

**Created:** 2026-01-19  
**Last Updated:** 2026-01-19

