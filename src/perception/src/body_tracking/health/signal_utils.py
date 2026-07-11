from typing import Optional, Tuple

import numpy as np
from scipy import signal as sp_signal


def resample_uniform(ts: np.ndarray, values: np.ndarray, fps: float) -> np.ndarray:
    ts = np.asarray(ts, dtype=float)
    values = np.asarray(values, dtype=float)
    if ts.size < 2:
        return values.copy()
    t0, t1 = ts[0], ts[-1]
    n = int(round((t1 - t0) * fps)) + 1
    if n < 2:
        return values.copy()
    grid = np.linspace(t0, t1, n)
    return np.interp(grid, ts, values)


def bandpass(sig: np.ndarray, fps: float, lo_hz: float = 0.7, hi_hz: float = 4.0) -> np.ndarray:
    sig = np.asarray(sig, dtype=float)
    sig = sig - sig.mean()
    nyq = fps / 2.0
    # Need enough samples for filtfilt padding; else just return detrended.
    if sig.size < 27 or hi_hz >= nyq:
        return sig
    lo = max(lo_hz / nyq, 1e-3)
    hi = min(hi_hz / nyq, 0.99)
    b, a = sp_signal.butter(3, [lo, hi], btype="band")
    filtered = sp_signal.filtfilt(b, a, sig)
    # Remove residual mean from filtfilt edge effects to ensure DC removal
    return filtered - filtered.mean()


def hr_from_signal(
    sig: np.ndarray, fps: float, lo_hz: float = 0.7, hi_hz: float = 4.0
) -> Tuple[Optional[float], float, float]:
    sig = np.asarray(sig, dtype=float)
    if sig.size < int(fps * 2):
        return None, 0.0, 0.0
    filtered = bandpass(sig, fps, lo_hz, hi_hz)
    windowed = filtered * np.hanning(filtered.size)
    n_fft = int(2 ** np.ceil(np.log2(filtered.size * 4)))  # zero-pad for resolution
    spectrum = np.abs(np.fft.rfft(windowed, n=n_fft)) ** 2
    freqs = np.fft.rfftfreq(n_fft, d=1.0 / fps)
    band = (freqs >= lo_hz) & (freqs <= hi_hz)
    if not band.any():
        return None, 0.0, 0.0
    band_power = spectrum[band]
    band_freqs = freqs[band]
    peak_idx = int(np.argmax(band_power))
    peak_power = float(band_power[peak_idx])
    total = float(band_power.sum())
    median = float(np.median(band_power)) or 1e-12
    hr_bpm = float(band_freqs[peak_idx] * 60.0)
    dominance = peak_power / total if total > 0 else 0.0
    snr = peak_power / median
    return hr_bpm, snr, dominance
