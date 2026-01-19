# Map Management MVP - Single Area Continuous Updates

## 🎯 Overview

This MVP implements a simple, robust map management system for a single-area robot:

- ✅ **One active map** (`home.yaml`) that continuously updates
- ✅ **Time-based auto-save** every 10 minutes
- ✅ **Automatic backups** keeping last 5 versions
- ✅ **Simple and reliable** - no complex room detection needed

## 📋 How It Works

```
Robot Operating 
    ↓
Map Generator continuously builds map
    ↓
Every 10 minutes: Auto-save triggered
    ↓
Overwrites ~/dorabot_ws/maps/home.yaml
    ↓
Backup script preserves previous version
    ↓
Keeps last 5 versions in maps/backups/
```

## 🚀 Quick Start

### 1. Enable Auto-Save (Already Done!)

The configuration is already updated:

```yaml
# configs/nav/map_manager.yaml
enable_auto_save: true
auto_save_interval: 600.0  # 10 minutes
```

### 2. Start the Robot

```bash
# Start orchestrator with mapping
./scripts/start_orchestrator_with_mapping.sh
```

The robot will now:
- Build the map in real-time
- Auto-save to `home.yaml` every 10 minutes
- Continuously improve map quality

### 3. Setup Automatic Backups (Optional but Recommended)

```bash
# Setup cron job for backups
./scripts/setup_auto_backup.sh
```

This runs every 10 minutes (synchronized with auto-save) and keeps the last 5 versions safe.

### 4. Manual Operations

```bash
# Save map manually anytime
./scripts/save_map.sh

# View all maps (including backups)
./scripts/list_maps.sh

# Manually backup current map
./scripts/backup_current_map.sh

# Stop everything
./scripts/stop_orchestrator.sh
```

## 📁 File Structure

```
dorabot_ws/
├── maps/
│   ├── home.yaml           # Current active map (auto-updates)
│   ├── home.pgm
│   └── backups/
│       ├── home_backup_20260119_120530.yaml  # Version 1
│       ├── home_backup_20260119_121530.yaml  # Version 2
│       ├── home_backup_20260119_122530.yaml  # Version 3
│       ├── home_backup_20260119_123530.yaml  # Version 4
│       └── home_backup_20260119_124530.yaml  # Version 5 (latest)
```

## ⚙️ Configuration

### Change Auto-Save Interval

Edit `configs/nav/map_manager.yaml`:

```yaml
auto_save_interval: 300.0   # 5 minutes (more frequent)
auto_save_interval: 900.0   # 15 minutes (less frequent)
auto_save_interval: 1800.0  # 30 minutes (battery saving)
```

### Change Number of Backup Versions

Edit `scripts/backup_current_map.sh`:

```bash
KEEP_VERSIONS=10  # Keep more history
KEEP_VERSIONS=3   # Minimal backups
```

## 🔍 Monitoring

### Check if Auto-Save is Working

```bash
# Watch the map file modification time
watch -n 1 "ls -lh ~/dorabot_ws/maps/home.yaml"

# Check map_manager logs
tail -f ~/logs/map_manager.log | grep "Auto-saved"
```

### View Backup Status

```bash
# List backups
ls -lht ~/dorabot_ws/maps/backups/

# Check backup logs (if using cron)
tail -f /tmp/map_backup.log
```

### Verify Map is Updating

```bash
# Check map generation rate
ros2 topic hz /map_generator/occupancy_grid

# View map metadata
cat ~/dorabot_ws/maps/home.yaml
```

## 🛠️ Troubleshooting

### Problem: Map Not Auto-Saving

**Check:**
```bash
# 1. Is map_manager running?
ros2 node list | grep map_manager

# 2. Is auto-save enabled?
grep enable_auto_save configs/nav/map_manager.yaml

# 3. Check logs
tail -f ~/logs/map_manager.log
```

**Solution:**
```bash
# Restart orchestrator
./scripts/stop_orchestrator.sh
./scripts/start_orchestrator_with_mapping.sh
```

### Problem: Backups Not Creating

**Check:**
```bash
# 1. Is cron job active?
crontab -l | grep backup

# 2. Check backup logs
cat /tmp/map_backup.log

# 3. Test manually
./scripts/backup_current_map.sh
```

### Problem: Disk Space Running Low

```bash
# Check usage
du -sh ~/dorabot_ws/maps/

# Reduce backup versions (edit script)
nano scripts/backup_current_map.sh
# Change: KEEP_VERSIONS=3

# Or clean up manually
rm ~/dorabot_ws/maps/backups/home_backup_2026*.yaml
```

## 📊 Benefits of This Approach

✅ **Simple** - No room detection, no complex logic
✅ **Reliable** - One map file, always up-to-date
✅ **Safe** - Backups protect against errors
✅ **Efficient** - No duplicate maps, minimal storage
✅ **Maintenance-Free** - Auto-cleanup keeps backups lean
✅ **Production-Ready** - Works 24/7 without intervention

## 🎯 Use Cases

Perfect for:
- **Single-floor apartments/homes**
- **Office spaces (open plan)**
- **Warehouses (single zone)**
- **Retail stores**
- **Any robot operating in one continuous area**

## 📈 Future Enhancements

When you're ready to expand:

1. **Multi-room support** - Add room detection (see docs)
2. **Map quality metrics** - Only save if improved
3. **Cloud backup** - Sync to remote storage
4. **Version comparison** - Detect environment changes
5. **A/B testing** - Compare different mapping parameters

## 📚 Related Scripts

- `start_orchestrator_with_mapping.sh` - Start mapping services
- `stop_orchestrator.sh` - Stop all services
- `save_map.sh` - Manual map save
- `list_maps.sh` - View all saved maps
- `backup_current_map.sh` - Backup current map
- `setup_auto_backup.sh` - Enable automatic backups

## 📞 Need Help?

Check the logs:
```bash
# Map generator
tail -f ~/logs/map_generator.log

# Map manager  
tail -f ~/logs/map_manager.log

# Orchestrator
tail -f ~/logs/*.log
```

---

**Last Updated:** 2026-01-19  
**Version:** MVP 1.0

