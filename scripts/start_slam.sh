#!/usr/bin/env bash
set -euo pipefail

ROOT="$HOME/dorabot_ws"
LOGDIR="$ROOT/logs"
PIDDIR="$ROOT/.pids"
mkdir -p "$LOGDIR" "$PIDDIR"

# --- ROS environment ---
set +u
source /opt/ros/humble/setup.bash
set -u

# Keep FastDDS (as you decided)
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
unset CYCLONEDDS_URI

# Optional: set a domain if you want (leave commented if you don't use it)
# export ROS_DOMAIN_ID=0

echo "[start_slam] Using RMW_IMPLEMENTATION=$RMW_IMPLEMENTATION"
echo "[start_slam] Logs: $LOGDIR"
echo "[start_slam] PIDs: $PIDDIR"

# Helper to start a command in background with logging + PID file
start_bg () {
  local name="$1"; shift
  local logfile="$LOGDIR/$name.log"
  echo "[start_slam] Starting $name ..."
  nohup "$@" >"$logfile" 2>&1 &
  echo $! > "$PIDDIR/$name.pid"
  echo "[start_slam]  -> $name pid=$(cat "$PIDDIR/$name.pid") log=$logfile"
}

# Start RealSense (aligned depth is important for RGB-D SLAM)
start_bg realsense \
  ros2 launch realsense2_camera rs_launch.py \
    align_depth.enable:=true

# Give the camera time to publish topics
sleep 2

# Start RTAB-Map SLAM (RGB-D)
# NOTE: we set frame_id:=camera_link to match your current setup.
# Later, when you have a robot base, you should use frame_id:=base_link with a proper base_link->camera_link TF.
start_bg rtabmap \
  ros2 launch rtabmap_launch rtabmap.launch.py \
    rgb_topic:=/camera/camera/color/image_raw \
    depth_topic:=/camera/camera/aligned_depth_to_color/image_raw \
    camera_info_topic:=/camera/camera/color/camera_info \
    approx_sync:=true \
    frame_id:=camera_link

# Optional: start RViz2 for visualization
# Comment out if you're running headless or don't want RViz.
start_bg rviz2 \
  rviz2

echo "[start_slam] Done."
echo
echo "[start_slam] Tips:"
echo "  - Live 2D grid map topic is usually: /rtabmap/map"
echo "  - Live 3D cloud topic is usually:    /rtabmap/cloud_map"
echo "  - After you're happy with the map, save it with:"
echo "      ros2 run nav2_map_server map_saver_cli -f $ROOT/maps/home --ros-args -r map:=/rtabmap/map"
