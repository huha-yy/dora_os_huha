import threading
import uuid
from typing import Optional


class HealthBus:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._metrics: Optional[dict] = None
        self._cmd: Optional[dict] = None

    def set_metrics(self, d: dict) -> None:
        with self._lock:
            self._metrics = d

    def get_metrics(self) -> Optional[dict]:
        with self._lock:
            return self._metrics

    def request_scan(self, window_s: float) -> str:
        mid = str(uuid.uuid4())
        with self._lock:
            self._cmd = {"action": "start", "measurement_id": mid, "window_s": window_s}
        return mid

    def request_cancel(self) -> None:
        with self._lock:
            self._cmd = {"action": "cancel"}

    def take_cmd(self) -> Optional[dict]:
        with self._lock:
            cmd, self._cmd = self._cmd, None
            return cmd


health_bus = HealthBus()
