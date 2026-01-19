#!/usr/bin/env bash
set -euo pipefail

ROOT="$HOME/dorabot_ws"
MAP_YAML="$ROOT/maps/living_room.yaml"
LOGDIR="$ROOT/logs"
PIDDIR="$ROOT/.pids_nav"
mkdir -p "$LOGDIR" "$PIDDIR"

# --- ROS environment (disable nounset while sourcing) ---
set +u
source /opt/ros/humble/setup.bash
set -u

# Keep FastDDS (as you decided)
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
unset CYCLONEDDS_URI

echo "[start_nav] Using map: $MAP_YAML"
echo "[start_nav] Logs: $LOGDIR"
echo "[start_nav] PIDs: $PIDDIR"

start_bg () {
  local name="$1"; shift
  local logfile="$LOGDIR/$name.log"
  echo "[start_nav] Starting $name ..."
  nohup "$@" >"$logfile" 2>&1 &
  echo $! > "$PIDDIR/$name.pid"
  echo "[start_nav]  -> $name pid=$(cat "$PIDDIR/$name.pid") log=$logfile"
}

# 0) Reset ROS daemon (helps if you had lots of previous nodes)
ros2 daemon stop >/dev/null 2>&1 || true
ros2 daemon start >/dev/null 2>&1 || true

# 1) Minimal TF chain for planning-only:
#    map -> odom -> base_link
# NOTE: These are TEMPORARY (no real odom yet). Later you'll remove them once you have wheel odom + AMCL.
start_bg tf_map_odom  ros2 run tf2_ros static_transform_publisher 0 0 0 0 0 0 map odom
start_bg tf_odom_base ros2 run tf2_ros static_transform_publisher 0 0 0 0 0 0 odom base_link

# 2) Start map_server
start_bg map_server ros2 run nav2_map_server map_server --ros-args -p yaml_filename:="$MAP_YAML"

# 3) Activate map_server lifecycle
# Give map_server a moment to appear
sleep 1
echo "[start_nav] Activating map_server lifecycle..."
ros2 lifecycle set /map_server configure >/dev/null
ros2 lifecycle set /map_server activate  >/dev/null

# 4) Start Nav2 (planner/controller/bt)
start_bg nav2 ros2 launch nav2_bringup navigation_launch.py use_sim_time:=false

# 5) Optional RViz2 (uncomment if you want auto-launch)
start_bg rviz2 rviz2

echo
echo "[start_nav] Started. Quick checks:"
echo "  ros2 topic echo /map --once"
echo "  ros2 node list | egrep 'planner_server|controller_server|bt_navigator|map_server'"
echo
echo "[start_nav] RViz tips:"
echo "  - Fixed Frame = map"
echo "  - Add Map display, Topic=/map"
echo "  - If it says 'No map received': Map display QoS Durability = Transient Local"
echo "  - Use 'Nav2 Goal' to click a goal and see a path"
