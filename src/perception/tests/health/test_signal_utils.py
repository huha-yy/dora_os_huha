import numpy as np

from body_tracking.health.signal_utils import resample_uniform, bandpass, hr_from_signal


def test_resample_uniform_preserves_endpoints():
    ts = np.array([0.0, 0.1, 0.35, 0.4])
    vals = np.array([0.0, 1.0, 2.0, 3.0])
    out = resample_uniform(ts, vals, fps=20.0)
    assert out.shape[0] == int(round((0.4 - 0.0) * 20.0)) + 1
    assert np.isclose(out[0], 0.0) and np.isclose(out[-1], 3.0)


def test_bandpass_removes_dc_offset():
    fps = 30.0
    t = np.arange(0, 10, 1 / fps)
    sig = 100.0 + np.sin(2 * np.pi * 1.2 * t)  # 72 bpm on a big DC offset
    out = bandpass(sig, fps)
    assert abs(out.mean()) < 1e-6
    assert out.std() > 0.1


def test_hr_from_signal_recovers_injected_frequency():
    fps = 30.0
    t = np.arange(0, 15, 1 / fps)
    sig = np.sin(2 * np.pi * 1.2 * t)  # exactly 72 bpm
    hr, snr, dominance = hr_from_signal(sig, fps)
    assert hr is not None
    assert abs(hr - 72.0) < 3.0
    assert dominance > 0.5
    assert snr > 3.0


def test_hr_from_signal_none_when_too_short():
    fps = 30.0
    sig = np.sin(np.arange(0, 1.0, 1 / fps))  # 1s < 2s minimum
    hr, snr, dominance = hr_from_signal(sig, fps)
    assert hr is None
