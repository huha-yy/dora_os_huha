import json

import numpy as np

from body_tracking.health.messages import build_metrics, SCHEMA_VERSION
from body_tracking.health.types import PulseEstimate, ScanState


def test_message_has_schema_and_null_unsupported():
    est = PulseEstimate(hr_bpm=72.0, confidence=0.8, spectral_snr=6.0, peak_dominance=0.7)
    msg = build_metrics(
        ts=123.0, mode="ambient", state=ScanState.IDLE, effective_fps=25.0,
        window_s=10.0, estimate=est, quality_components={"face_px": 180},
        complexion=None, reason=None, scan_progress_s=0.0, scan_target_s=30.0,
    )
    assert msg["schema_version"] == SCHEMA_VERSION
    assert msg["hr_bpm"] == 72.0 and msg["hr_confidence"] == 0.8
    assert msg["resp_bpm"] is None and msg["hrv_sdnn_ms"] is None and msg["spo2_pct"] is None
    assert msg["state"] == "idle"


def test_hr_null_when_no_estimate():
    msg = build_metrics(
        ts=1.0, mode="ambient", state=ScanState.IDLE, effective_fps=0.0,
        window_s=10.0, estimate=None, quality_components={}, complexion=None,
        reason="no_face", scan_progress_s=0.0, scan_target_s=30.0,
    )
    assert msg["hr_bpm"] is None and msg["hr_confidence"] is None
    assert msg["reason"] == "no_face"


def test_numpy_scalars_are_coerced_to_native_types():
    qc = {
        "face_px": np.int64(180),
        "roi_px": np.int32(6000),
        "effective_fps": np.float32(25.0),
        "drop_ratio": np.float64(0.02),
        "exposure_stable": np.bool_(True),
        "jitter_ms": 5.0,
    }
    est = PulseEstimate(hr_bpm=72.0, confidence=0.8, spectral_snr=6.0, peak_dominance=0.7)
    msg = build_metrics(
        ts=123.0, mode="ambient", state=ScanState.IDLE, effective_fps=25.0,
        window_s=10.0, estimate=est, quality_components=qc,
        complexion={"appearance_zh": np.str_("面色红润")},
        reason=None, scan_progress_s=0.0, scan_target_s=30.0,
    )
    assert type(msg["quality_components"]["face_px"]) is int
    assert type(msg["quality_components"]["drop_ratio"]) is float
    assert type(msg["quality_components"]["exposure_stable"]) is bool
    assert type(msg["complexion"]["appearance_zh"]) is str
    dump = json.dumps(msg)
    parsed = json.loads(dump)
    assert parsed["hr_bpm"] == 72.0
    assert parsed["quality_components"]["face_px"] == 180


def test_hr_null_when_estimate_has_none_hr():
    est = PulseEstimate(hr_bpm=None, confidence=0.8, spectral_snr=6.0, peak_dominance=0.7)
    msg = build_metrics(
        ts=1.0, mode="ambient", state=ScanState.IDLE, effective_fps=0.0,
        window_s=10.0, estimate=est, quality_components={}, complexion=None,
        reason="low_confidence", scan_progress_s=0.0, scan_target_s=30.0,
    )
    assert msg["hr_bpm"] is None
    assert msg["hr_confidence"] is None


def test_message_has_exact_key_set():
    est = PulseEstimate(hr_bpm=72.0, confidence=0.8, spectral_snr=6.0, peak_dominance=0.7)
    msg = build_metrics(
        ts=1.0, mode="ambient", state=ScanState.IDLE, effective_fps=25.0,
        window_s=10.0, estimate=est, quality_components={"face_px": 180},
        complexion=None, reason="test", scan_progress_s=0.0, scan_target_s=30.0,
    )
    expected_keys = {
        "schema_version", "ts", "mode", "state", "reason", "effective_fps",
        "window_s", "hr_bpm", "hr_confidence", "quality_components",
        "complexion", "resp_bpm", "hrv_sdnn_ms", "spo2_pct", "scan",
    }
    assert set(msg.keys()) == expected_keys
