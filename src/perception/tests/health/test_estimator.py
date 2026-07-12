import numpy as np

from body_tracking.health.estimator import RPPGEstimator
from body_tracking.health.config import HealthConfig
from body_tracking.health.types import RgbSample


def _feed_pulse(est, fps=30.0, secs=15.0, hr_hz=1.2, t_offset=0.0):
    t = t_offset + np.arange(0, secs, 1 / fps)
    pulse = 0.02 * np.sin(2 * np.pi * hr_hz * (t - t_offset))
    for i, ti in enumerate(t):
        est.add_sample(RgbSample(
            t=float(ti),
            r=0.6 + 0.3 * pulse[i],
            g=0.5 + 1.0 * pulse[i],
            b=0.4 + 0.2 * pulse[i],
        ))
    return float(t[-1])


def test_estimator_recovers_hr_from_stream():
    est = RPPGEstimator(HealthConfig.default())
    now = _feed_pulse(est)
    out = est.estimate(now=now, window_s=10.0)
    assert out.hr_bpm is not None
    assert abs(out.hr_bpm - 72.0) < 6.0


def test_effective_fps_tracks_stream():
    est = RPPGEstimator(HealthConfig.default())
    now = _feed_pulse(est, fps=30.0)
    assert 27.0 <= est.effective_fps(now=now, window_s=5.0) <= 33.0


def test_estimate_returns_none_when_buffer_empty():
    est = RPPGEstimator(HealthConfig.default())
    out = est.estimate(now=100.0, window_s=10.0)
    assert out.hr_bpm is None


def test_hysteresis_limits_hr_jump():
    est = RPPGEstimator(HealthConfig.default())
    now_a = _feed_pulse(est, fps=30.0, secs=15.0, hr_hz=1.2)
    out_a = est.estimate(now=now_a, window_s=10.0)
    assert out_a.hr_bpm is not None

    # Feed a completely different frequency — the estimate should be clamped
    now_b = _feed_pulse(est, fps=30.0, secs=15.0, hr_hz=2.5, t_offset=now_a + 0.1)
    out_b = est.estimate(now=now_b, window_s=10.0)
    assert out_b.hr_bpm is not None
    jump = abs(out_b.hr_bpm - out_a.hr_bpm)
    assert jump <= 12.0 + 1.0  # MAX_HR_JUMP_BPM + tolerance for rounding
