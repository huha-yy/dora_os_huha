from body_tracking.health.quality import evaluate_gates
from body_tracking.health.config import Gates


def _good():
    return {
        "face_present": True, "single_target": True, "roi_in_bounds": True,
        "face_px": 180, "roi_px": 6000, "effective_fps": 25.0, "drop_ratio": 0.02,
        "jitter_ms": 5.0, "motion": 0.01, "illum_delta": 0.05, "exposure_stable": True,
    }


def test_all_gates_pass():
    res = evaluate_gates(_good(), Gates())
    assert res.ok and res.reason is None


def test_low_fps_fails_with_reason():
    c = _good(); c["effective_fps"] = 5.0
    res = evaluate_gates(c, Gates())
    assert not res.ok and res.reason == "low_fps"


def test_no_face_fails_first():
    c = _good(); c["face_present"] = False; c["effective_fps"] = 5.0
    res = evaluate_gates(c, Gates())
    assert res.reason == "no_face"  # face checked before fps


def test_components_are_echoed():
    res = evaluate_gates(_good(), Gates())
    assert res.components["face_px"] == 180
