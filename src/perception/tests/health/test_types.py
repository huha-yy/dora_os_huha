from body_tracking.health.types import RgbSample, PulseEstimate, ScanState, GateResult


def test_rgb_sample_is_immutable_and_carries_time():
    s = RgbSample(t=1.5, r=10.0, g=20.0, b=30.0)
    assert (s.t, s.r, s.g, s.b) == (1.5, 10.0, 20.0, 30.0)


def test_scan_state_values_are_lowercase_strings():
    assert ScanState.COLLECTING.value == "collecting"
    assert ScanState.INSUFFICIENT_QUALITY.value == "insufficient_quality"


def test_gate_result_defaults():
    g = GateResult(ok=True, reason=None, components={"face_px": 180})
    assert g.ok and g.reason is None and g.components["face_px"] == 180
