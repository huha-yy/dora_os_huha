from typing import Optional, Tuple

import numpy as np
from scipy import signal as sp_signal

# Half-width (Hz) of the neighbourhood around the spectral peak used to
# compute peak_dominance. Chosen to be invariant to zero-padding: widening
# the FFT (n_fft) redistributes a sinusoid's energy across more, narrower
# bins, but the total power within a fixed +/-Hz window around the peak
# frequency stays stable.
PEAK_NEIGHBOURHOOD_HZ = 0.2

# Minimum sample count for a stable filtfilt band-pass. scipy.signal.filtfilt
# requires the signal length to exceed its default padlen (roughly
# 3 * max(len(a), len(b)), which is 21 samples for our order-3 Butterworth
# band filter); this threshold adds a small margin above that minimum.
# Below this we skip filtering and just return the detrended signal.
MIN_SAMPLES_FOR_FILTFILT = 27


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
    if sig.size < MIN_SAMPLES_FOR_FILTFILT or hi_hz >= nyq:
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
    peak_freq = float(band_freqs[peak_idx])
    total = float(band_power.sum())
    median = float(np.median(band_power)) or 1e-12
    hr_bpm = float(band_freqs[peak_idx] * 60.0)
    # peak_dominance = fraction of in-band power concentrated in a narrow
    # neighbourhood around the peak frequency. Unlike peak_power / total
    # (a single FFT bin vs. the whole band), this is invariant to the
    # zero-padding factor used above: a clean sinusoid's energy spreads
    # across more bins as n_fft grows, but the power within a fixed
    # +/-PEAK_NEIGHBOURHOOD_HZ window around the peak stays essentially
    # constant.
    neighbourhood = np.abs(band_freqs - peak_freq) <= PEAK_NEIGHBOURHOOD_HZ
    neighbourhood_power = float(band_power[neighbourhood].sum())
    dominance = neighbourhood_power / total if total > 0 else 0.0
    snr = peak_power / median
    return hr_bpm, snr, dominance
