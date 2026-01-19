#!/usr/bin/env bash
set -euo pipefail

ROOT="$HOME/dorabot_ws"
PIDDIR="$ROOT/.pids"

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
      echo "[stop_slam] Stopping $name (pid=$pid) ..."
      kill "$pid" || true
      # Give it a moment to exit gracefully
      sleep 1
      if kill -0 "$pid" >/dev/null 2>&1; then
        echo "[stop_slam]  -> Force killing $name (pid=$pid) ..."
        kill -9 "$pid" || true
      fi
    else
      echo "[stop_slam] $name pidfile exists but process not running."
    fi
    rm -f "$pidfile"
  else
    echo "[stop_slam] No pidfile for $name (already stopped?)."
  fi
}

# Stop in reverse order (rviz -> rtabmap -> realsense)
stop_one rviz2
stop_one rtabmap
stop_one realsense

# Also restart daemon to clear stale graph cache (optional but helps)
ros2 daemon stop || true
ros2 daemon start || true

echo "[stop_slam] Done."
