#!/usr/bin/env bash
# Launch the chatbot frontend in Chromium kiosk mode on the robot's
# physical display. Intended to be run from an SSH session on the robot
# (the robot itself has no keyboard/mouse).
#
# Usage:
#   ./scripts/start-frontend.sh           # launch kiosk
#   ./scripts/start-frontend.sh --stop    # close kiosk
#
# Notes:
#   - The backend must already be running (see start-backend.sh).
#   - Mic permission is auto-granted via --use-fake-ui-for-media-stream
#     so no click is needed.

set -euo pipefail

URL="http://localhost:8000/"
DISPLAY_NUM=":0"
XAUTH="/home/orangepi/.Xauthority"
LOGFILE="/tmp/chromium-chatbot.log"
PATTERN="chromium.*localhost:8000"

stop_kiosk() {
    if pgrep -f "$PATTERN" >/dev/null; then
        pkill -f "$PATTERN" || true
        sleep 1
        if pgrep -f "$PATTERN" >/dev/null; then
            echo "Chromium did not exit cleanly; forcing..." >&2
            pkill -9 -f "$PATTERN" || true
        fi
        echo "Kiosk stopped."
    else
        echo "Kiosk is not running."
    fi
}

if [[ "${1:-}" == "--stop" || "${1:-}" == "stop" ]]; then
    stop_kiosk
    exit 0
fi

if ! command -v chromium-browser >/dev/null 2>&1; then
    echo "error: chromium-browser not installed." >&2
    echo "       install it: sudo apt install -y chromium" >&2
    exit 1
fi

if [[ ! -S /tmp/.X11-unix/X${DISPLAY_NUM#:} ]]; then
    echo "error: X server not found at DISPLAY=$DISPLAY_NUM." >&2
    echo "       is the robot's desktop session running?" >&2
    exit 1
fi

if [[ ! -f "$XAUTH" ]]; then
    echo "error: Xauthority not found at $XAUTH." >&2
    exit 1
fi

if pgrep -f "$PATTERN" >/dev/null; then
    echo "Kiosk already running. Restarting it..."
    stop_kiosk
fi

echo -n "Waiting for backend at $URL ..."
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
    echo "error: backend did not respond at $URL after 30s." >&2
    echo "       start it first: ./scripts/start-backend.sh" >&2
    exit 1
fi

echo "Launching kiosk on display $DISPLAY_NUM ..."
DISPLAY="$DISPLAY_NUM" \
XAUTHORITY="$XAUTH" \
nohup chromium-browser \
    --app="$URL" \
    --autoplay-policy=no-user-gesture-required \
    --use-fake-ui-for-media-stream \
    > "$LOGFILE" 2>&1 &
disown

sleep 1
if pgrep -f "$PATTERN" >/dev/null; then
    echo "Kiosk started. Log: $LOGFILE"
    echo "Stop with: $0 --stop"
else
    echo "error: chromium failed to start. Tail of $LOGFILE:" >&2
    tail -n 20 "$LOGFILE" >&2 || true
    exit 1
fi
