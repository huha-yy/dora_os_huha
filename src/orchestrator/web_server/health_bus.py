import threading
import time
import uuid
from typing import Callable, Optional

# How long a metrics payload stays servable after it arrives.
#
# Perception publishes at 1 Hz, so anything older than this means it has stopped
# talking to us -- crashed, ROS disconnected, camera unplugged. The bus MUST stop
# serving in that case: it is the only thing standing between a dead perception node
# and a heart rate rendered in the UI as if it were live. The node's own 5s
# frame-staleness guard does not cover this, because it only runs while the node is
# alive and publishing.
#
# A stale vital sign shown as current is the plausible-but-wrong number AGENTS.md
# section 5 forbids. Withhold it instead.
METRICS_TTL_S = 5.0


class HealthBus:
    """Thread-safe hand-off between the ROS executor thread and FastAPI's workers.

    Metrics expire (see METRICS_TTL_S). Commands are consume-once.
    """

    def __init__(
        self,
        ttl_s: float = METRICS_TTL_S,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._lock = threading.Lock()
        self._metrics: Optional[dict] = None
        self._metrics_at: float = 0.0
        self._cmd: Optional[dict] = None
        self._ttl_s = float(ttl_s)
        # Monotonic, not wall-clock: an NTP step must not make a fresh reading look
        # stale (or, worse, a stale one look fresh).
        self._clock = clock

    def set_metrics(self, d: dict) -> None:
        with self._lock:
            self._metrics = dict(d)  # copy: the caller keeps its reference
            self._metrics_at = self._clock()

    def get_metrics(self) -> Optional[dict]:
        """The last metrics, or None if perception has gone quiet."""
        with self._lock:
            if self._metrics is None:
                return None
            if self._clock() - self._metrics_at > self._ttl_s:
                return None
            return dict(self._metrics)  # copy: a reader must not mutate the cache

    def request_scan(self, window_s: float) -> str:
        mid = str(uuid.uuid4())
        with self._lock:
            self._cmd = {"action": "start", "measurement_id": mid, "window_s": float(window_s)}
        return mid

    def request_cancel(self) -> None:
        with self._lock:
            self._cmd = {"action": "cancel"}

    def take_cmd(self) -> Optional[dict]:
        with self._lock:
            cmd, self._cmd = self._cmd, None
            return cmd

    def reset(self) -> None:
        """Drop all state. For tests -- this object is a module-level singleton."""
        with self._lock:
            self._metrics = None
            self._metrics_at = 0.0
            self._cmd = None


health_bus = HealthBus()
