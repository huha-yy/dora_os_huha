import pytest
from body_tracking.health.quality import evaluate_gates
from body_tracking.health.config import Gates


def _good():
    return {
        "face_present": True, "single_target": True, "roi_in_bounds": True,
        "face_px": 180, "roi_px": 6000, "effective_fps": 25.0, "drop_ratio": 0.02,
        "jitter_ms": 5.0, "motion": 0.01, "illum_delta": 0.05, "chroma_drift": 0.002,
        "exposure_stable": True,
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


# Test missing-key fail-safe defaults: omitting any key causes the reading to be withheld.
# This is critical for safety — the perception node builds components by hand,
# so omission is the most plausible real-world failure. Each default is deliberately
# chosen on the "reject" side (e.g., False for bools, 1e9 for distances).
@pytest.mark.parametrize("key_to_omit,expected_reason", [
    ("face_present", "no_face"),
    ("single_target", "multiple_targets"),
    ("roi_in_bounds", "roi_out_of_bounds"),
    ("face_px", "face_too_small"),
    ("roi_px", "roi_too_small"),
    ("effective_fps", "low_fps"),
    ("drop_ratio", "dropped_frames"),
    ("jitter_ms", "timestamp_jitter"),
    ("motion", "head_motion"),
    ("illum_delta", "illumination_change"),
    ("chroma_drift", "white_balance_drift"),
    ("exposure_stable", "exposure_unstable"),
])
def test_omitted_key_causes_rejection(key_to_omit: str, expected_reason: str):
    """Verify that omitting any required component key causes the reading to be withheld.

    This test enforces the fail-safe contract: a missing key in the components dict
    should never cause a reading to be accepted; instead, the reading is rejected with
    the appropriate reason.
    """
    c = _good()
    del c[key_to_omit]
    res = evaluate_gates(c, Gates())
    assert not res.ok, f"Omitting {key_to_omit} should cause rejection"
    assert res.reason == expected_reason, f"Omitting {key_to_omit} should return reason={expected_reason}"
