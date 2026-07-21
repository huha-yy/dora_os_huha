from typing import Any, Optional

import numpy as np

from .types import PulseEstimate, ScanState

SCHEMA_VERSION = 1


def _coerce(obj: Any) -> Any:
    """Recursively convert numpy scalars to native Python types.

    Returns a deep copy of *obj* with every ``numpy.generic`` leaf replaced
    by its native ``.item()`` equivalent.  ``None`` passes through unchanged.
    Unknown non-dict, non-list types are left untouched so that a downstream
    ``json.dumps`` will still fail loudly on truly broken data.
    """
    if obj is None:
        return None
    if isinstance(obj, np.generic):
        return obj.item()
    if isinstance(obj, dict):
        return {k: _coerce(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_coerce(v) for v in obj]
    return obj


def build_metrics(
    ts: float,
    mode: str,
    state: ScanState,
    effective_fps: float,
    window_s: float,
    estimate: Optional[PulseEstimate],
    quality_components: dict,
    complexion: Optional[dict],
    reason: Optional[str],
    scan_progress_s: float,
    scan_target_s: float,
) -> dict:
    hr = estimate.hr_bpm if estimate is not None else None
    conf = estimate.confidence if (estimate is not None and hr is not None) else None
    return _coerce({
        "schema_version": SCHEMA_VERSION,
        "ts": ts,
        "mode": mode,
        "state": state.value,
        "reason": reason,
        "effective_fps": round(effective_fps, 2),
        "window_s": window_s,
        "hr_bpm": round(hr, 1) if hr is not None else None,
        "hr_confidence": round(conf, 2) if conf is not None else None,
        "quality_components": quality_components,
        "complexion": complexion,
        "resp_bpm": None,     # not_supported in v1
        "hrv_sdnn_ms": None,  # not_supported in v1
        "spo2_pct": None,     # not_supported in v1
        "scan": {"progress_clean_s": round(scan_progress_s, 1), "target_s": scan_target_s},
    })
