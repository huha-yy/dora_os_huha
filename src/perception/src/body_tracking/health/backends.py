from typing import Protocol

import numpy as np

from .types import PulseEstimate
from .signal_utils import resample_uniform, hr_from_signal


def _confidence(snr: float, dominance: float) -> float:
    # Squash SNR to 0..1 and blend with peak dominance.
    snr_term = snr / (snr + 4.0)
    return float(max(0.0, min(1.0, 0.5 * snr_term + 0.5 * dominance)))


def _estimate_from_signal(sig: np.ndarray, ts: np.ndarray) -> PulseEstimate:
    if ts.size < 2:
        return PulseEstimate(None, 0.0, 0.0, 0.0)
    fps = (ts.size - 1) / (ts[-1] - ts[0]) if ts[-1] > ts[0] else 0.0
    if fps <= 0:
        return PulseEstimate(None, 0.0, 0.0, 0.0)
    uniform = resample_uniform(ts, sig, fps)
    hr, snr, dominance = hr_from_signal(uniform, fps)
    conf = _confidence(snr, dominance) if hr is not None else 0.0
    return PulseEstimate(hr, conf, snr, dominance)


class RPPGBackend(Protocol):
    def estimate(self, rgb: np.ndarray, ts: np.ndarray) -> PulseEstimate: ...


class POSBackend:
    """Plane-Orthogonal-to-Skin (Wang et al., 2017)."""

    def estimate(self, rgb: np.ndarray, ts: np.ndarray) -> PulseEstimate:
        rgb = np.asarray(rgb, dtype=float)
        ts = np.asarray(ts, dtype=float)
        if rgb.shape[0] < 3:
            return PulseEstimate(None, 0.0, 0.0, 0.0)
        mean = rgb.mean(axis=0)
        mean[mean == 0] = 1e-8
        normed = rgb / mean                      # temporal normalization
        s1 = normed[:, 1] - normed[:, 2]         # G - B
        s2 = normed[:, 1] + normed[:, 2] - 2 * normed[:, 0]  # G + B - 2R
        alpha = np.std(s1) / (np.std(s2) + 1e-8)
        pulse = s1 + alpha * s2
        return _estimate_from_signal(pulse, ts)


class CHROMBackend:
    """Chrominance-based rPPG (de Haan & Jeanne, 2013)."""

    def estimate(self, rgb: np.ndarray, ts: np.ndarray) -> PulseEstimate:
        rgb = np.asarray(rgb, dtype=float)
        ts = np.asarray(ts, dtype=float)
        if rgb.shape[0] < 3:
            return PulseEstimate(None, 0.0, 0.0, 0.0)
        mean = rgb.mean(axis=0)
        mean[mean == 0] = 1e-8
        r, g, b = (rgb / mean).T
        x = 3 * r - 2 * g
        y = 1.5 * r + g - 1.5 * b
        alpha = np.std(x) / (np.std(y) + 1e-8)
        pulse = x - alpha * y
        return _estimate_from_signal(pulse, ts)


def make_backend(name: str) -> RPPGBackend:
    key = (name or "").lower()
    if key == "pos":
        return POSBackend()
    if key == "chrom":
        return CHROMBackend()
    raise ValueError(f"Unknown rPPG backend: {name!r} (expected 'pos' or 'chrom')")
