from body_tracking.health.config import HealthConfig, Gates


def test_default_config_is_sane():
    cfg = HealthConfig.default()
    assert cfg.enabled is True
    assert cfg.backend == "pos"
    assert cfg.ambient_window_s == 10.0
    assert cfg.scan_window_s == 30.0
    assert isinstance(cfg.gates, Gates)
    assert cfg.gates.min_fps == 15.0


def test_from_dict_applies_overrides_and_keeps_other_defaults():
    cfg = HealthConfig.from_dict({
        "backend": "chrom",
        "gates": {"min_fps": 20.0},
    })
    assert cfg.backend == "chrom"
    assert cfg.gates.min_fps == 20.0
    assert cfg.gates.min_face_px == 120  # default preserved


# --------------------------------------------------------------------------
# T5: config is safety-critical -- it carries the quality gates. A typo must be
# loud. Silently falling back to a default means someone who tightened
# min_confidence to 0.9 is actually running 0.70 and has no way to find out.
# --------------------------------------------------------------------------

import pytest


def test_unknown_gate_key_raises():
    with pytest.raises(ValueError, match="min_confidenc"):
        Gates.from_dict({"min_confidenc": 0.9})     # typo: missing 'e'


def test_unknown_config_key_raises():
    with pytest.raises(ValueError, match="ambient_windo"):
        HealthConfig.from_dict({"ambient_windo": 10.0})


def test_error_names_the_offending_key_and_suggests_the_real_ones():
    with pytest.raises(ValueError) as e:
        Gates.from_dict({"max_moton": 0.05})
    msg = str(e.value)
    assert "max_moton" in msg
    assert "max_motion" in msg, "the message should point at the key they meant"


def test_backend_must_be_a_known_estimator():
    with pytest.raises(ValueError, match="nonsense"):
        HealthConfig.from_dict({"backend": "nonsense"})


@pytest.mark.parametrize("bad", [
    {"min_confidence": 5.0},    # impossible -- the gate could never pass
    {"min_confidence": -0.1},
    {"max_motion": -1.0},
    {"min_fps": -30.0},
    {"max_drop_ratio": 1.5},
])
def test_out_of_range_gate_values_raise(bad):
    with pytest.raises(ValueError):
        Gates.from_dict(bad)


@pytest.mark.parametrize("bad", [
    {"ambient_window_s": -5.0},
    {"ambient_window_s": 0.0},
    {"scan_window_s": -1.0},
    {"scan_timeout_s": 0.0},
])
def test_non_positive_windows_raise(bad):
    with pytest.raises(ValueError):
        HealthConfig.from_dict(bad)


def test_valid_config_still_round_trips():
    c = HealthConfig.from_dict({
        "enabled": False,
        "backend": "chrom",
        "ambient_window_s": 12.0,
        "gates": {"min_confidence": 0.8, "max_motion": 0.03},
    })
    assert c.enabled is False
    assert c.backend == "chrom"
    assert c.ambient_window_s == 12.0
    assert c.gates.min_confidence == 0.8
    assert c.gates.max_motion == 0.03
    assert c.gates.min_fps == Gates().min_fps, "unspecified gates keep their defaults"


def test_empty_dict_gives_defaults():
    assert HealthConfig.from_dict({}) == HealthConfig.default()


@pytest.mark.parametrize("bad", [
    {"max_motion": float("nan")},
    {"max_illum_delta": float("inf")},
    {"min_confidence": float("nan")},
    {"min_fps": float("nan")},
])
def test_non_finite_gate_values_raise(bad):
    """NaN defeats a gate silently: `motion > nan` is False, so the gate NEVER fires.
    Infinity does the same. Either would reopen the phantom-heart-rate hole that
    test_noise_rejection.py exists to close -- range checks alone do not catch them,
    because every comparison against NaN is False."""
    with pytest.raises(ValueError):
        Gates.from_dict(bad)


@pytest.mark.parametrize("bad", [
    {"ambient_window_s": float("nan")},
    {"scan_window_s": float("inf")},
])
def test_non_finite_windows_raise(bad):
    with pytest.raises(ValueError):
        HealthConfig.from_dict(bad)


def test_detector_must_be_known():
    with pytest.raises(ValueError, match="detector"):
        HealthConfig.from_dict({"detector": "nonsense"})


@pytest.mark.parametrize("d", ["mediapipe_face", "pose_fallback"])
def test_valid_detectors_accepted(d):
    assert HealthConfig.from_dict({"detector": d}).detector == d
