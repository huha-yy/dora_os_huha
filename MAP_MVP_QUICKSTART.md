# 🗺️ Map Management MVP - Quick Start

## ✅ What's Configured

Your robot now has **automatic continuous map updating** enabled!

### Auto-Save: **ENABLED** ✓
- **Interval:** Every 10 minutes
- **Map file:** `~/dorabot_ws/maps/home.yaml`
- **Behavior:** Continuously updates the same map file

### Backups: **READY** ✓
- **Location:** `~/dorabot_ws/maps/backups/`
- **Keeps:** Last 5 versions
- **Script:** `./scripts/backup_current_map.sh`

---

## 🚀 How to Use

### Start Robot with Mapping

```bash
./scripts/start_orchestrator_with_mapping.sh
```

That's it! The robot will now:
- ✅ Build map in real-time
- ✅ Auto-save every 10 minutes to `home.yaml`
- ✅ Keep improving map quality automatically

### Optional: Enable Automatic Backups

```bash
./scripts/setup_auto_backup.sh
```

This creates a cron job that backs up the map every 10 minutes (before auto-save overwrites it).

---

## 📊 What Happens

```
Time    | Event
--------|------------------------------------------
00:00   | Robot starts, begins mapping
00:10   | Auto-save #1 → home.yaml updated
00:20   | Auto-save #2 → home.yaml updated
00:30   | Auto-save #3 → home.yaml updated
...     | (continues as long as robot runs)
```

**Result:** You always have the **latest and best** map in `home.yaml`!

---

## 💾 Backup System

If backups are enabled:

```
Before each auto-save:
1. Copy current home.yaml → backups/home_backup_[timestamp].yaml
2. Keep last 5 versions
3. Delete older backups automatically
```

**Safety net:** If something goes wrong, you have up to 5 previous versions!

---

## 📁 File Locations

```
~/dorabot_ws/maps/
├── home.yaml              ← CURRENT MAP (auto-updates)
├── home.pgm
└── backups/
    ├── home_backup_20260119_140000.yaml  ← 50 min ago
    ├── home_backup_20260119_141000.yaml  ← 40 min ago
    ├── home_backup_20260119_142000.yaml  ← 30 min ago
    ├── home_backup_20260119_143000.yaml  ← 20 min ago
    └── home_backup_20260119_144000.yaml  ← 10 min ago
```

---

## 🎯 Common Tasks

### View Current Map
```bash
cat ~/dorabot_ws/maps/home.yaml
```

### See All Maps (including backups)
```bash
./scripts/list_maps.sh
```

### Force Save Now (don't wait 10 min)
```bash
./scripts/save_map.sh
```

### Restore from Backup
```bash
# List backups
ls -lht ~/dorabot_ws/maps/backups/

# Copy backup to current
cp ~/dorabot_ws/maps/backups/home_backup_TIMESTAMP.yaml ~/dorabot_ws/maps/home.yaml
cp ~/dorabot_ws/maps/backups/home_backup_TIMESTAMP.pgm ~/dorabot_ws/maps/home.pgm
```

### Stop Robot
```bash
./scripts/stop_orchestrator.sh
```

---

## 🔍 Monitor Status

### Check Auto-Save is Working
```bash
# Watch map file update times
watch -n 1 "ls -lh ~/dorabot_ws/maps/home.yaml"

# View logs
tail -f ~/logs/map_manager.log | grep "Auto-saved"
```

### Verify Map is Improving
```bash
# Check map generation rate
ros2 topic hz /map_generator/occupancy_grid

# View in RViz2
rviz2 -d src/nav/config/mapping.rviz
```

---

## ⚙️ Adjust Settings

### Change Save Frequency

Edit: `configs/nav/map_manager.yaml`

```yaml
auto_save_interval: 300.0   # 5 minutes (faster updates)
auto_save_interval: 900.0   # 15 minutes (less frequent)
auto_save_interval: 1800.0  # 30 minutes (battery saving)
```

Then restart:
```bash
./scripts/stop_orchestrator.sh
./scripts/start_orchestrator_with_mapping.sh
```

### Change Backup Retention

Edit: `scripts/backup_current_map.sh`

```bash
KEEP_VERSIONS=10  # Keep more history
KEEP_VERSIONS=3   # Minimal backups
```

---

## 📚 Documentation

- **Full Guide:** `docs/MAP_MANAGEMENT_MVP.md`
- **All Scripts:** `scripts/CLEANUP_SCRIPTS_README.md`

---

## 💡 Tips

1. **Let it run!** The longer the robot operates, the better the map becomes
2. **Check backups occasionally** to ensure they're working
3. **Monitor disk space** if running for weeks (backups are small but add up)
4. **Use RViz2** to visualize map quality in real-time

---

**Status:** ✅ READY TO RUN  
**Setup Time:** Complete  
**Maintenance:** Automatic

