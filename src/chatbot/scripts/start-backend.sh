#!/usr/bin/env bash
# Start the chatbot WebSocket server in the foreground.
#
# Usage:
#   ./scripts/start-backend.sh                    # default: INFO logs
#   ./scripts/start-backend.sh --log-level DEBUG  # forwards args to main.py
#
# Stop with Ctrl+C.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHATBOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV="$CHATBOT_DIR/.venv"

if [[ ! -d "$VENV" ]]; then
    echo "error: virtualenv not found at $VENV" >&2
    echo "       create it first: cd $CHATBOT_DIR && uv venv .venv" >&2
    exit 1
fi

# shellcheck disable=SC1091
source "$VENV/bin/activate"

if [[ -z "${MINIMAX_API_KEY:-}" ]]; then
    echo "warning: MINIMAX_API_KEY is not set in this shell." >&2
    echo "         If it is also not set in config.json, the LLM will fail to init." >&2
fi

cd "$CHATBOT_DIR"

# Default to INFO if the caller passed no log-level flag.
if [[ "$*" != *"--log-level"* ]]; then
    set -- --log-level INFO "$@"
fi

echo "Starting chatbot backend (Ctrl+C to stop)..."
exec python main.py "$@"
