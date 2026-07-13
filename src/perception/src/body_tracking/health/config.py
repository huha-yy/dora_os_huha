"""Health-metrics configuration.

The gates in here decide whether a heart rate is shown to a user or withheld, so a
mistake in this file is a safety problem, not a convenience problem. `from_dict`
therefore REJECTS unknown keys and out-of-range values rather than quietly falling
back to a default: someone who tightened `min_confidence` to 0.9 and typo'd the key
would otherwise be running 0.70 with no way to find out.
"""

import math
from dataclasses import dataclass, field, fields
from difflib import get_close_matches
from typing import Any, Mapping

BACKENDS = ("pos", "chrom")


def _reject_unknown(d: Mapping[str, Any], known: set, where: str) -> None:
    for key in d:
        if key in known:
            continue
        hint = get_close_matches(key, sorted(known), n=1)
        suggestion = f" Did you mean {hint[0]!r}?" if hint else ""
        raise ValueError(
            f"Unknown {where} key {key!r}.{suggestion} "
            f"Valid keys: {', '.join(sorted(known))}"
        )


def _check(name: str, value: float, lo: float, hi: float, *, lo_open: bool = False) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be a number, got {value!r}")

    # Non-finite FIRST: a range check cannot catch NaN, because every comparison
    # against it is False. A NaN threshold silently DISABLES its gate -- `motion > nan`
    # never trips -- which would quietly reopen the phantom-heart-rate hole that
    # min_confidence and test_noise_rejection.py exist to close. Infinity does the
    # same. This is the exact failure mode the gates are here to prevent, so it must
    # be rejected loudly rather than range-checked.
    if not math.isfinite(v):
        raise ValueError(f"{name} must be finite, got {v}")

    below = v <= lo if lo_open else v < lo
    if below or v > hi:
        bound = f"({lo}, {hi}]" if lo_open else f"[{lo}, {hi}]"
        raise ValueError(f"{name} must be in {bound}, got {v}")
    return v


@dataclass(frozen=True)
class Gates:
    min_fps: float = 15.0
    max_drop_ratio: float = 0.2
    min_face_px: int = 120
    min_roi_px: int = 3000
    max_jitter_ms: float = 20.0
    max_motion: float = 0.05
    max_illum_delta: float = 0.15
    # Do NOT lower this without rerunning tests/health/test_noise_rejection.py.
    #
    # Confidence does not go to zero for noise: `0.5*snr/(snr+4) + 0.5*dominance` has
    # a floor around 0.44 and a p99 of ~0.64, because a random spectrum still has some
    # peak in the 0.7-4 Hz band and dominance rewards it. At the original 0.5 the gate
    # sat INSIDE the noise distribution and pure noise published a heart rate in ~17%
    # of windows. 0.70 sits in the gap between noise (p99 ~0.64) and a real pulse
    # (p01 ~0.85 at 1% modulation): phantom rate 0.25%, and a weak 0.5% pulse still
    # gets through 89% (POS) / 99% (CHROM) of the time.
    min_confidence: float = 0.70

    @classmethod
    def from_dict(cls, d: dict) -> "Gates":
        d = dict(d or {})
        known = {f.name for f in fields(cls)}
        _reject_unknown(d, known, "gate")

        if "min_confidence" in d:
            _check("min_confidence", d["min_confidence"], 0.0, 1.0)
        if "max_drop_ratio" in d:
            _check("max_drop_ratio", d["max_drop_ratio"], 0.0, 1.0)
        for key in ("min_fps", "max_jitter_ms", "max_motion", "max_illum_delta"):
            if key in d:
                _check(key, d[key], 0.0, float("inf"))
        for key in ("min_face_px", "min_roi_px"):
            if key in d:
                _check(key, d[key], 0, float("inf"))

        return cls(**d)


@dataclass(frozen=True)
class HealthConfig:
    enabled: bool = True
    backend: str = "pos"
    detector: str = "mediapipe_face"   # or "pose_fallback"
    ambient_window_s: float = 10.0
    scan_window_s: float = 30.0        # target CLEAN seconds
    scan_timeout_s: float = 90.0       # wall-clock guard
    lock_camera_on_scan: bool = True
    complexion_enabled: bool = True
    gates: Gates = field(default_factory=Gates)

    @classmethod
    def default(cls) -> "HealthConfig":
        return cls()

    @classmethod
    def from_dict(cls, d: dict) -> "HealthConfig":
        d = dict(d or {})
        gates = Gates.from_dict(d.pop("gates", {}) or {})

        known = {f.name for f in fields(cls)} - {"gates"}
        _reject_unknown(d, known, "config")

        if "backend" in d and str(d["backend"]).lower() not in BACKENDS:
            raise ValueError(
                f"Unknown backend {d['backend']!r}. Valid backends: {', '.join(BACKENDS)}"
            )
        # A non-positive window would make the estimator silently useless rather than
        # loudly broken -- reject it here, at the boundary.
        for key in ("ambient_window_s", "scan_window_s", "scan_timeout_s"):
            if key in d:
                _check(key, d[key], 0.0, float("inf"), lo_open=True)

        return cls(gates=gates, **d)
