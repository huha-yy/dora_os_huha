import sys
from pathlib import Path

# Make `body_tracking` importable as a top-level package in tests, matching
# the way the node runs (cwd = src/perception, package root = src/perception/src).
SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
