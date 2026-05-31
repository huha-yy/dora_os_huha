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

WS_SCRIPTS="$(cd "$SCRIPT_DIR/../../.." && pwd)/scripts"
# shellcheck disable=SC1091
source "${WS_SCRIPTS}/load_minimax_env.sh"

if [[ -z "${MINIMAX_API_KEY:-}" ]]; then
    echo "warning: MINIMAX_API_KEY not set (expected in ~/.bashrc)." >&2
    echo "         The LLM will fail to init without it." >&2
fi

cd "$CHATBOT_DIR"

# Default to INFO if the caller passed no log-level flag.
if [[ "$*" != *"--log-level"* ]]; then
    set -- --log-level INFO "$@"
fi

echo "Starting chatbot backend (Ctrl+C to stop)..."
exec python main.py "$@"
