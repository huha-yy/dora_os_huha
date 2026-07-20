#!/usr/bin/env bash
# Launch the Dorabot unified UI (camera + chatbot) in Chromium kiosk mode on
# the robot's physical display. Intended to be run from a remote SSH session
# while the robot has no keyboard/mouse attached locally.
#
# Usage:
#   bash scripts/start-frontend-ssh.sh           # launch kiosk
#   bash scripts/start-frontend-ssh.sh --stop    # close kiosk
#
# Prerequisites:
#   - Backends running: bash scripts/start_dorabot.sh
#   - Robot desktop / X session active on DISPLAY :0
#
# Opens: http://localhost:8080/  (orchestrator UI with live camera + chat sidebar)

set -euo pipefail

URL="http://localhost:8080/"
DISPLAY_NUM=":0"
XAUTH="${HOME}/.Xauthority"
LOGFILE="/tmp/chromium-dorabot-ui.log"
PROFILE_DIR="${HOME}/.cache/chromium-dorabot-kiosk"
PATTERN="chromium.*localhost:8080"

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
    echo "       install it: sudo apt install -y chromium-browser" >&2
    exit 1
fi

if [[ ! -S "/tmp/.X11-unix/X${DISPLAY_NUM#:}" ]]; then
    echo "error: X server not found at DISPLAY=$DISPLAY_NUM." >&2
    echo "       Is the robot's desktop session running?" >&2
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

echo "Launching kiosk on display $DISPLAY_NUM ..."
mkdir -p "$PROFILE_DIR"
DISPLAY="$DISPLAY_NUM" \
XAUTHORITY="$XAUTH" \
nohup chromium-browser \
    --app="$URL" \
    --user-data-dir="$PROFILE_DIR" \
    --autoplay-policy=no-user-gesture-required \
    --use-fake-ui-for-media-stream \
    --no-sandbox \
    --enable-features=AllowSyncXHRInPageDismissal \
    --disable-features=MediaStreamVisibilityBrowsertest \
    --disable-infobars \
    --no-first-run \
    --no-default-browser-check \
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
