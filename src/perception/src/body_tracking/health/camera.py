"""Locking the colour sensor's auto-exposure and auto-white-balance.

Measured on the real D415 (2026-07-14), static scene, 640x480@30:

    window       illum_delta    B/G chrominance CoV
    AUTO  0-10s     0.1168          7.484%      <- AE/AWB adapting
    AUTO  2-12s     0.0031          0.983%
    AUTO  5-15s     0.0004          0.105%      <- settled
    LOCKED any      0.0005          0.089%      <- clean from frame zero

Two things follow, and both matter.

1. Auto-exposure and auto-white-balance are ON by default, and after any event that
   makes them re-adapt -- the subject shifts, a light changes, someone walks past --
   the chrominance takes about FIVE SECONDS to settle. During that time B/G drifts by
   up to 7.5%, against a real pulse that modulates the channels by ~1%. The camera's
   own regulation is then several times larger than the signal we are trying to read.
   The analysis window is 10s, so a single AE/AWB event contaminates an entire window.

2. `illum_delta` DOES NOT CATCH THIS. It peaked at 0.1168, under its 0.15 gate, so the
   window passes. Auto-white-balance re-mixes R/G/B while holding overall brightness
   roughly constant, so a *luminance* metric is blind to it by construction -- and
   POS/CHROM consume precisely the ratios that AWB is scrambling. This is why
   `exposure_stable` cannot be assumed True: no other gate covers it.

So the lock is a prerequisite for the feature, not a refinement.

Pure Python. The sensor is duck-typed (`supports` / `set_option` / `get_option`), so
this is unit-testable without a camera and without importing pyrealsense2 or ROS.
"""

from dataclasses import dataclass
from typing import Any, List, Optional, Protocol


class Option(Protocol):
    """Stand-in for `rs.option.*` -- an opaque handle the sensor understands."""


class ColorSensor(Protocol):
    def supports(self, option: Any) -> bool: ...
    def set_option(self, option: Any, value: float) -> None: ...
    def get_option(self, option: Any) -> float: ...


@dataclass(frozen=True)
class LockResult:
    """What actually happened. `locked` is the only thing the gate should trust."""

    locked: bool
    auto_exposure_off: bool
    auto_white_balance_off: bool
    failures: List[str]

    def as_dict(self) -> dict:
        return {
            "locked": self.locked,
            "auto_exposure_off": self.auto_exposure_off,
            "auto_white_balance_off": self.auto_white_balance_off,
            "failures": list(self.failures),
        }


def lock_color_sensor(
    sensor: ColorSensor,
    ae_option: Any,
    awb_option: Any,
) -> LockResult:
    """Turn off auto-exposure and auto-white-balance, then VERIFY by reading back.

    Verification is not paranoia. `set_option` can be accepted and silently ignored
    (unsupported control, firmware quirk, another process owning the device), and a
    lock we believe in but do not have is worse than no lock at all: it would mark
    `exposure_stable=True` while the camera keeps hunting, and the whole point of that
    gate is to stop exactly that.

    Fails CLOSED: any doubt and `locked` is False, which withholds readings rather
    than publishing ones the camera is corrupting.
    """
    failures: List[str] = []

    ae_off = _disable(sensor, ae_option, "auto_exposure", failures)
    awb_off = _disable(sensor, awb_option, "auto_white_balance", failures)

    return LockResult(
        locked=ae_off and awb_off,
        auto_exposure_off=ae_off,
        auto_white_balance_off=awb_off,
        failures=failures,
    )


def exposure_stable_for(scan_active: bool, camera_locked: bool) -> bool:
    """Value for the `exposure_stable` quality-gate component.

    The camera lock is SCAN-SCOPED, because the colour stream is shared with
    safety-critical fall detection and a permanent auto-exposure lock would leave it
    working on an under-exposed image if the lighting changed. So the two modes differ:

    - Ambient (no scan): the camera runs on auto. We do not lock, and delegate
      drift-rejection to the measured `chroma_drift` / `illum_delta` gates, which reject
      a corrupted window whether the camera is locked or not. `exposure_stable` must
      therefore NOT block the best-effort live overlay -> True.

    - Scan: a scan PROMISES a locked camera. `exposure_stable` is True only with a
      verified lock. A lock that is still pending, failed, or unreported (the owning
      process is silent) is False, so the scan withholds and accrues no clean seconds
      until the camera is actually locked -- or the scan times out and fails loudly.
      Never trust an unconfirmed lock.
    """
    return (not scan_active) or camera_locked


def restore_auto_on_sensor(sensor: ColorSensor, ae_option: Any, awb_option: Any) -> dict:
    """Re-enable auto-exposure and auto-white-balance, VERIFYING by read-back.

    Symmetric with lock_color_sensor, and for the same reason: a `set_option` can be
    accepted and silently ignored, so reporting "auto restored" without reading it back
    can leave the shared colour stream locked while claiming it is free -- a
    safety-relevant lie, since fall detection would then run on a frozen exposure and
    `lock_satisfied` would stop retrying the release.

    Returns a dict with `auto` True only when BOTH controls are verified back on auto,
    `locked` True while either remains forced off, and any `failures`.
    """
    failures: List[str] = []
    ae_auto = _enable(sensor, ae_option, "auto_exposure", failures)
    awb_auto = _enable(sensor, awb_option, "auto_white_balance", failures)
    return {
        "locked": not (ae_auto and awb_auto),  # still forced off on either control
        "auto": ae_auto and awb_auto and not failures,
        "failures": failures,
    }


def _enable(sensor: ColorSensor, option: Any, name: str, failures: List[str]) -> bool:
    try:
        if not sensor.supports(option):
            failures.append(f"{name}: not supported by this sensor")
            return False
        sensor.set_option(option, 1.0)
        if sensor.get_option(option) != 1.0:
            failures.append(f"{name}: auto-restore did not take effect")
            return False
        return True
    except Exception as exc:  # noqa: BLE001
        failures.append(f"{name}: {type(exc).__name__}: {exc}")
        return False


def is_scan_locked(state: Optional[dict]) -> bool:
    """Is the camera VERIFIED locked for a scan: BOTH auto controls off, no failures.

    This is the ONLY trustworthy "locked for rPPG" signal, and the single source of
    truth for both the publisher (whether to re-apply a lock) and the perception node
    (whether a scan may pass `exposure_stable`).

    It deliberately does NOT read the `locked` field, which is overloaded: a lock report
    sets `locked = ae_off and awb_off`, but a PARTIAL auto-restore (say AE back on auto,
    AWB stuck off) also sets `locked = True` meaning only "not fully auto". Keying off
    that field would let a scan pass while auto-exposure was still running -- exactly the
    silent bad reading this gate exists to prevent. The lock-path readbacks
    (`auto_exposure_off` / `auto_white_balance_off`) are present only after an actual
    lock attempt, so a restore state fails this by construction.
    """
    st = state or {}
    return (
        bool(st.get("auto_exposure_off"))
        and bool(st.get("auto_white_balance_off"))
        and not st.get("failures")
    )


def lock_satisfied(want_locked: bool, state: Optional[dict]) -> bool:
    """Does the sensor's last VERIFIED state already match the request?

    Decides whether a repeated lock/unlock request needs a (re)apply. It deliberately
    checks the achieved physical state, NOT whether the request equals the last request:
    a request-equals-request check latches a transient failure forever. If a lock or an
    auto-restore fails once, every later identical request would be skipped, leaving a
    scan unable to lock (it times out) or the camera stuck locked while idle (fall
    detection runs on a frozen exposure). Returning False here on a missing, failed, or
    partial previous attempt makes the caller retry on the next 1 Hz request.
    """
    st = state or {}
    if want_locked:
        return is_scan_locked(st)
    # Unlock/auto is satisfied only when auto was actually restored with no failures.
    return st.get("auto") is True and not st.get("failures")


def window_captured_under_lock(
    locked_now: bool,
    lock_since: Optional[float],
    now: float,
    window_s: float,
) -> bool:
    """Was the ENTIRE current analysis window captured with the camera verified-locked?

    A per-instant lock check is not enough for a scan. The estimator transforms a
    `window_s`-long window of samples, and for the first `window_s` after a scan locks
    (or relocks after a drop) that window still contains frames sampled while AE/AWB were
    auto -- which contaminate the reading. A short scan (the API allows a target below
    the analysis window) would otherwise complete on a window that is mostly pre-lock.

    So a scan window is trustworthy only once the lock has held continuously for at least
    `window_s`. `lock_since` is when the current unbroken lock began (None if not
    locked); it resets on any drop, which correctly forces another full window before the
    reading is trusted again.
    """
    if not locked_now or lock_since is None:
        return False
    return (now - lock_since) >= window_s


def _disable(sensor: ColorSensor, option: Any, name: str, failures: List[str]) -> bool:
    try:
        if not sensor.supports(option):
            failures.append(f"{name}: not supported by this sensor")
            return False
        sensor.set_option(option, 0.0)
        # Read back -- a write that was accepted and ignored must not count as a lock.
        if sensor.get_option(option) != 0.0:
            failures.append(f"{name}: set_option was accepted but did not take effect")
            return False
        return True
    except Exception as exc:  # noqa: BLE001 -- any driver error means "not locked"
        failures.append(f"{name}: {type(exc).__name__}: {exc}")
        return False
