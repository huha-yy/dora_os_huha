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
