#!/usr/bin/env bash
# =============================================================================
# Run ONCE after extracting dorabot_ws backup on a new Orange Pi 5.
# Restores ALSA config and mixer settings to match the backed-up state.
# =============================================================================
set -euo pipefail

echo "=== Restoring ALSA config (~/.asoundrc) ==="
cp "$(dirname "$0")/../asoundrc.backup" ~/.asoundrc

echo "=== Setting mixer levels for Yundea M1066 (card 3) ==="
amixer -c 3 sset Mic 147 2>/dev/null || echo "Mic not found"
amixer -c 3 sset PCM 147 2>/dev/null || echo "PCM not found"
amixer -c 3 sset 'Auto Gain Control' off 2>/dev/null || true

echo "=== Mixer state ==="
amixer -c 3 sget Mic 2>/dev/null
amixer -c 3 sget PCM 2>/dev/null

echo ""
echo "Done. Now run:"
echo "  bash ~/dorabot_ws/scripts/start_dorabot.sh"
echo "  bash ~/dorabot_ws/scripts/start-frontend-ssh.sh"
