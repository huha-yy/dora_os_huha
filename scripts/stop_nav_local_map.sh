#!/usr/bin/env bash
set -euo pipefail

ROOT="$HOME/dorabot_ws"
PIDDIR="$ROOT/.pids_nav"

set +u
source /opt/ros/humble/setup.bash
set -u

export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
unset CYCLONEDDS_URI

stop_one () {
  local name="$1"
  local pidfile="$PIDDIR/$name.pid"
  if [[ -f "$pidfile" ]]; then
    local pid
    pid="$(cat "$pidfile" || true)"
    if [[ -n "${pid:-}" ]] && kill -0 "$pid" >/dev/null 2>&1; then
      echo "[stop_nav] Stopping $name (pid=$pid) ..."
      kill "$pid" || true
      sleep 1
      if kill -0 "$pid" >/dev/null 2>&1; then
        echo "[stop_nav]  -> Force killing $name (pid=$pid) ..."
        kill -9 "$pid" || true
      fi
    else
      echo "[stop_nav] $name pidfile exists but process not running."
    fi
    rm -f "$pidfile"
  else
    echo "[stop_nav] No pidfile for $name (already stopped?)."
  fi
}

# Stop in reverse order
stop_one rviz2
stop_one nav2
stop_one map_server
stop_one tf_odom_base
stop_one tf_map_odom

# Extra cleanup (in case anything was launched outside the script)
pkill -f "nav2_" || true
pkill -f "map_server" || true
pkill -f "static_transform_publisher" || true
pkill -f "rviz2" || true

ros2 daemon stop >/dev/null 2>&1 || true
ros2 daemon start >/dev/null 2>&1 || true

echo "[stop_nav] Done."
