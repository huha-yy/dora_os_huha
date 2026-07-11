from body_tracking.health.config import HealthConfig, Gates


def test_default_config_is_sane():
    cfg = HealthConfig.default()
    assert cfg.enabled is True
    assert cfg.backend == "pos"
    assert cfg.ambient_window_s == 10.0
    assert cfg.scan_window_s == 30.0
    assert isinstance(cfg.gates, Gates)
    assert cfg.gates.min_fps == 15.0


def test_from_dict_overrides_and_ignores_unknown():
    cfg = HealthConfig.from_dict({
        "backend": "chrom",
        "gates": {"min_fps": 20.0},
        "bogus": 123,
    })
    assert cfg.backend == "chrom"
    assert cfg.gates.min_fps == 20.0
    assert cfg.gates.min_face_px == 120  # default preserved
