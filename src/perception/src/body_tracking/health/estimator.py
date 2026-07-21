from typing import List, Optional

import numpy as np

from .backends import RPPGBackend, make_backend
from .config import HealthConfig
from .ring_buffer import RgbRingBuffer
from .types import PulseEstimate, RgbSample

MAX_HR_JUMP_BPM = 12.0


class RPPGEstimator:
    def __init__(self, config: HealthConfig, backend: Optional[RPPGBackend] = None) -> None:
        self._config = config
        self._backend = backend or make_backend(config.backend)
        self._buffer = RgbRingBuffer(max_seconds=max(config.ambient_window_s, config.scan_window_s) + 5.0)
        self._last_hr: Optional[float] = None

    def add_sample(self, sample: RgbSample) -> None:
        self._buffer.append(sample)

    def effective_fps(self, now: float, window_s: float) -> float:
        return self._buffer.effective_fps(now, window_s)

    def window(self, now: float, window_s: float) -> List[RgbSample]:
        """The samples the next estimate would use. Callers need these for the
        quality gates (drop, jitter, motion, illumination) and must not reach
        into the private buffer to get them."""
        return self._buffer.window(now, window_s)

    def estimate(self, now: float, window_s: float, gate_ok: bool) -> PulseEstimate:
        """Estimate the pulse over the window.

        `gate_ok` is REQUIRED and has no default: this method is stateful, and a
        caller that forgot it would silently reintroduce a real bug.

        `_last_hr` anchors the +/-MAX_HR_JUMP_BPM hysteresis clamp. A window the
        quality gates rejected (head motion, lighting change) must therefore not
        be allowed to commit it -- otherwise the artifact drags the next
        *accepted* reading toward itself, and the gate ends up rejecting the bad
        window for publication while still leaking it into the good one that
        follows. Rejecting resets the hysteresis so the next clean reading is
        free to be correct.
        """
        if not gate_ok:
            self._last_hr = None
            return PulseEstimate(None, 0.0, 0.0, 0.0)
        win = self._buffer.window(now, window_s)
        if len(win) < 3:
            self._last_hr = None
            return PulseEstimate(None, 0.0, 0.0, 0.0)
        ts = np.array([s.t for s in win])
        rgb = np.array([[s.r, s.g, s.b] for s in win])
        est = self._backend.estimate(rgb, ts)
        if est.hr_bpm is None or est.confidence < self._config.gates.min_confidence:
            self._last_hr = None
            return PulseEstimate(None, est.confidence, est.spectral_snr, est.peak_dominance)
        if self._last_hr is not None and abs(est.hr_bpm - self._last_hr) > MAX_HR_JUMP_BPM:
            clamped = self._last_hr + np.sign(est.hr_bpm - self._last_hr) * MAX_HR_JUMP_BPM
            est = PulseEstimate(float(clamped), est.confidence, est.spectral_snr, est.peak_dominance)
        self._last_hr = est.hr_bpm
        return est
