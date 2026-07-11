from typing import Optional

from .types import ScanState


class ScanController:
    def __init__(self, target_clean_s: float, timeout_s: float, warmup_s: float = 2.0) -> None:
        self._target = float(target_clean_s)
        self._timeout = float(timeout_s)
        self._warmup = float(warmup_s)
        self._state = ScanState.IDLE
        self._clean = 0.0
        self._mid: Optional[str] = None
        self._start_t = 0.0
        self._last_t = 0.0

    @property
    def state(self) -> ScanState:
        return self._state

    @property
    def progress_clean_s(self) -> float:
        return self._clean

    @property
    def measurement_id(self) -> Optional[str]:
        return self._mid

    def start(self, measurement_id: str, now: float) -> None:
        self._state = ScanState.WARMING
        self._clean = 0.0
        self._mid = measurement_id
        self._start_t = now
        self._last_t = now

    def cancel(self, now: float) -> None:
        if self._state in (ScanState.WARMING, ScanState.COLLECTING, ScanState.INSUFFICIENT_QUALITY):
            self._state = ScanState.CANCELLED

    def update(self, now: float, gate_ok: bool) -> None:
        if self._state not in (ScanState.WARMING, ScanState.COLLECTING, ScanState.INSUFFICIENT_QUALITY):
            return
        dt = max(0.0, now - self._last_t)
        self._last_t = now

        if now - self._start_t > self._timeout:
            self._state = ScanState.FAILED
            return

        if gate_ok:
            self._clean += dt
            self._state = ScanState.COLLECTING
            if self._clean >= self._target:
                self._state = ScanState.COMPLETE
            return

        # gate not ok
        if self._state == ScanState.COLLECTING:
            self._state = ScanState.INSUFFICIENT_QUALITY
        elif self._state == ScanState.WARMING and (now - self._start_t) > self._warmup:
            self._state = ScanState.INSUFFICIENT_QUALITY
