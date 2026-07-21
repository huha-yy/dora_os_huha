from typing import Optional

from .types import ScanState


_ACTIVE_STATES = (ScanState.WARMING, ScanState.COLLECTING, ScanState.INSUFFICIENT_QUALITY)


class ScanController:
    """State machine for an on-demand ~30s camera health scan.

    Progress accrues in CLEAN seconds only: elapsed time counts toward
    ``target_clean_s`` only while the quality gate passes (``gate_ok=True``
    on ``update()``). The controller is pure — time is always supplied via
    the ``now`` argument; the system clock is never read internally.

    Per-update credit is capped at ``max_dt_s`` (default 2.0s). The node
    driving this controller calls ``update()`` from a ~1 Hz ROS timer, so
    ~1s between calls is expected; 2.0s tolerates normal jitter while
    guaranteeing that a long gap between calls (process stall, node hang,
    camera dropout, or a large jump in ``now``) can credit at most one
    update's worth of clean time — never the full elapsed gap. Without this
    cap, a single good frame arriving after a long stall would instantly
    "complete" the scan on time that was never actually validated
    frame-by-frame.

    A backwards ``now`` (i.e. ``now < `` the timestamp of the previous
    ``update()``/``start()`` call — clock skew or a stale/replayed
    timestamp) is ignored entirely: it neither accrues progress nor
    advances the internal time baseline. Only rewinding the baseline
    would allow a later, normal call to compute an inflated ``dt`` against
    the stale baseline and over-credit progress.

    Calling ``start()`` while a scan is already in progress (WARMING,
    COLLECTING, or INSUFFICIENT_QUALITY) is treated as an explicit restart:
    it discards the in-flight scan's progress, resets
    ``progress_clean_s`` to 0.0, and adopts the new ``measurement_id``. This
    is intentional — e.g. the user pressed "Scan" again — not a bug.

    Recovering from INSUFFICIENT_QUALITY back to COLLECTING resumes accrual
    from the previously accumulated ``progress_clean_s`` rather than
    resetting it; a transient occlusion or lighting blip should not force
    the user to restart the whole scan.

    If a timeout and a would-be completion are both satisfied within the
    same ``update()`` call, FAILED takes precedence over COMPLETE.
    """

    def __init__(
        self,
        target_clean_s: float,
        timeout_s: float,
        warmup_s: float = 2.0,
        max_dt_s: float = 2.0,
    ) -> None:
        self._default_target = float(target_clean_s)
        self._target = self._default_target
        self._timeout = float(timeout_s)
        self._warmup = float(warmup_s)
        self._max_dt = float(max_dt_s)
        self._state = ScanState.IDLE
        self._clean = 0.0
        self._mid: Optional[str] = None
        self._start_t = 0.0
        self._last_t = 0.0

    @property
    def state(self) -> ScanState:
        return self._state

    @property
    def is_active(self) -> bool:
        """A scan is in progress. Drives the scan-scoped camera lock (Task 16c): the
        lock is requested while this is True and released when it goes False."""
        return self._state in _ACTIVE_STATES

    @property
    def progress_clean_s(self) -> float:
        return self._clean

    @property
    def measurement_id(self) -> Optional[str]:
        return self._mid

    def start(
        self,
        measurement_id: str,
        now: float,
        target_clean_s: Optional[float] = None,
    ) -> None:
        """Begin a scan.

        `target_clean_s` overrides the configured target for THIS scan only. The HTTP
        API lets the caller ask for a window, and that request used to be plumbed all
        the way to this class and then dropped -- so a 60s scan silently ran for the
        configured 30s. Resetting it on every start keeps the override per-scan and
        stops one scan's window leaking into the next.
        """
        self._state = ScanState.WARMING
        self._clean = 0.0
        self._mid = measurement_id
        self._start_t = now
        self._last_t = now
        self._target = float(target_clean_s) if target_clean_s else self._default_target

    def cancel(self, now: float) -> None:
        if self._state in _ACTIVE_STATES:
            self._state = ScanState.CANCELLED

    def update(self, now: float, gate_ok: bool) -> None:
        if self._state not in _ACTIVE_STATES:
            return

        if now < self._last_t:
            # Stale/out-of-order timestamp (clock skew, replay, etc.). Ignore
            # entirely: do not accrue and do not rewind the time baseline.
            return

        dt = min(now - self._last_t, self._max_dt)
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
