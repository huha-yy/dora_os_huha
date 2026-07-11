import numpy as np
import pytest

from body_tracking.health.backends import make_backend, POSBackend, CHROMBackend


def _pulsatile_rgb(fps=30.0, secs=15.0, hr_hz=1.2):
    t = np.arange(0, secs, 1 / fps)
    pulse = 0.02 * np.sin(2 * np.pi * hr_hz * t)
    # Skin-like base with the pulse modulating green strongest.
    r = 0.6 + 0.3 * pulse + 0.001 * np.random.RandomState(0).randn(t.size)
    g = 0.5 + 1.0 * pulse + 0.001 * np.random.RandomState(1).randn(t.size)
    b = 0.4 + 0.2 * pulse + 0.001 * np.random.RandomState(2).randn(t.size)
    return t, np.stack([r, g, b], axis=1)


@pytest.mark.parametrize("backend_cls", [POSBackend, CHROMBackend])
def test_backend_recovers_heart_rate(backend_cls):
    t, rgb = _pulsatile_rgb()
    est = backend_cls().estimate(rgb, t)
    assert est.hr_bpm is not None
    assert abs(est.hr_bpm - 72.0) < 5.0
    assert 0.0 <= est.confidence <= 1.0


def test_make_backend_selects_and_rejects():
    assert isinstance(make_backend("pos"), POSBackend)
    assert isinstance(make_backend("chrom"), CHROMBackend)
    with pytest.raises(ValueError):
        make_backend("deep")
