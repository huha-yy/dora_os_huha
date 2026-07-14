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
