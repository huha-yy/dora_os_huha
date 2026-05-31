#!/usr/bin/env bash
# Open the Dorabot unified UI in a normal Chromium window on the robot.
# Run this from a terminal on the robot itself (desktop session) when a
# keyboard is connected — not from SSH.
#
# Usage:
#   bash scripts/start-frontend-local.sh
#
# The browser runs in the foreground; close the window or press Ctrl+C in
# the terminal to exit.
#
# Prerequisites:
#   - Backends running: bash scripts/start_dorabot.sh
#   - Local desktop session (keyboard + display attached to the robot)
#
# Opens: http://localhost:8080/  (orchestrator UI with live camera + chat sidebar)

set -euo pipefail

URL="http://localhost:8080/"
PROFILE_DIR="${HOME}/.cache/chromium-dorabot-local"

if [[ "${1:-}" == "--stop" || "${1:-}" == "stop" ]]; then
    if pgrep -f "chromium.*localhost:8080" >/dev/null; then
        pkill -f "chromium.*localhost:8080" || true
        echo "Browser closed."
    else
        echo "No Dorabot UI browser window is running."
    fi
    exit 0
fi

if [[ -n "${SSH_CONNECTION:-}" || -n "${SSH_CLIENT:-}" ]]; then
    echo "error: this script is for use on the robot with a keyboard attached." >&2
    echo "       From SSH, use: bash scripts/start-frontend-ssh.sh" >&2
    exit 1
fi

if ! command -v chromium-browser >/dev/null 2>&1; then
    echo "error: chromium-browser not installed." >&2
    echo "       install it: sudo apt install -y chromium-browser" >&2
    exit 1
fi

export DISPLAY="${DISPLAY:-:0}"

if [[ ! -S "/tmp/.X11-unix/X${DISPLAY#:}" ]]; then
    echo "error: no X server at DISPLAY=$DISPLAY." >&2
    echo "       log in to the robot desktop first." >&2
    exit 1
fi

echo -n "Waiting for orchestrator at $URL ..."
for _ in $(seq 1 30); do
    if curl -sf -o /dev/null "$URL"; then
        echo " ready."
        break
    fi
    echo -n "."
    sleep 1
done

if ! curl -sf -o /dev/null "$URL"; then
    echo
    echo "error: orchestrator did not respond at $URL after 30s." >&2
    echo "       start backends first: bash scripts/start_dorabot.sh" >&2
    exit 1
fi

echo "Opening Dorabot UI (close the browser window or Ctrl+C to exit)..."
mkdir -p "$PROFILE_DIR"
exec chromium-browser \
    "$URL" \
    --new-window \
    --start-maximized \
    --user-data-dir="$PROFILE_DIR" \
    --autoplay-policy=no-user-gesture-required \
    --disable-infobars \
    --no-first-run \
    --no-default-browser-check
