from body_tracking.health.ring_buffer import RgbRingBuffer
from body_tracking.health.types import RgbSample


def _fill(buf, start, n, dt, g=128.0):
    for i in range(n):
        buf.append(RgbSample(t=start + i * dt, r=100.0, g=g, b=90.0))


def test_window_returns_recent_samples_only():
    buf = RgbRingBuffer(max_seconds=10.0)
    _fill(buf, start=0.0, n=100, dt=0.1)  # 10s at 10 fps, last t = 9.9
    win = buf.window(now=9.9, seconds=3.0)
    assert all(s.t > 9.9 - 3.0 for s in win)
    assert win == sorted(win, key=lambda s: s.t)
    assert 29 <= len(win) <= 31


def test_effective_fps_reflects_sample_spacing():
    buf = RgbRingBuffer(max_seconds=10.0)
    _fill(buf, start=0.0, n=60, dt=1 / 30.0)  # 30 fps
    fps = buf.effective_fps(now=60 / 30.0, seconds=2.0)
    assert 28.0 <= fps <= 32.0


def test_effective_fps_zero_with_insufficient_samples():
    buf = RgbRingBuffer(max_seconds=10.0)
    buf.append(RgbSample(t=1.0, r=1, g=1, b=1))
    assert buf.effective_fps(now=1.0, seconds=2.0) == 0.0


def test_max_seconds_evicts_old_samples():
    buf = RgbRingBuffer(max_seconds=2.0)
    _fill(buf, start=0.0, n=100, dt=0.1)  # spans 10s but keeps ~2s
    assert len(buf) <= 25
