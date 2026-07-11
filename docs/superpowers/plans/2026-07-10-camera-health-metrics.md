# Camera-Based Health Metrics (rPPG) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a non-medical camera heart-rate readout (rPPG) plus a fun complexion-appearance card to the Dorabot stack, shown as a live overlay and an on-demand scan in the monitor UI.

**Architecture:** A pure-Python `health/` package inside the perception node computes rPPG from face-ROI color samples. The image callback only samples ROI color (cheap); a ROS timer runs POS/CHROM estimation and publishes a versioned JSON `/health/metrics` topic; a `/health/scan_cmd` topic controls an on-demand scan state machine. The orchestrator subscribes, holds the latest snapshot in a `HealthBus`, and exposes HTTP endpoints the UI and chatbot call.

**Tech Stack:** Python 3.10, numpy 1.26.4, scipy, OpenCV, MediaPipe (Face Detection), ROS 2 Humble (`rclpy`, `std_msgs/String`), FastAPI (orchestrator), vanilla JS UI.

## Global Constraints

- Python `>=3.10`; **numpy pinned `==1.26.4`** (MediaPipe/cv_bridge ABI). No new heavy deps; **no PyTorch, no JAX**.
- The `health/` core package (everything except `node_integration.py`) MUST NOT import `rclpy`, `cv_bridge`, or any ROS module, so it is unit-testable off-robot.
- The image callback MUST NOT run FFT/estimation. It may only extract ROI + append one RGB sample. All estimation runs on a ROS timer.
- Fall detection is safety-critical: the feature must be toggleable off via config and must not reduce pose FPS beyond budget (verified in Task 16).
- Non-medical: no health/vitality/diagnostic labels anywhere. Complexion is "appearance only". RR/HRV/SpO2 are `not_supported` in v1 and always serialized as `null`.
- Message contract carries `schema_version: 1`. Unsupported metric fields are always present and `null`.
- Bilingual UI copy (zh + en), matching existing `index.html`.
- Follow existing repo import style: within `body_tracking`, use relative imports (`from .health.x import Y`).
- Commit after each task with conventional-commit messages (`feat:`, `test:`, `chore:`).
- **Canonical test command** (use this everywhere a task says "run pytest"):
  ```bash
  cd src/perception && PYTHONPATH= /extra_space/dorabot_ws/.venv/bin/python -m pytest tests/health -v
  ```
  `PYTHONPATH=` is required: the shell profile puts `/opt/ros/humble` on `PYTHONPATH`, whose
  `launch_testing` pytest plugins fail to load (missing `lark`) and abort collection. Clearing it
  also enforces the "health core imports no ROS" constraint above. Test deps live in the repo venv
  (`/extra_space/dorabot_ws/.venv`); install with `uv pip install --python /extra_space/dorabot_ws/.venv/bin/python <pkg>`.
  The orchestrator tests (Task 14) DO need ROS-free FastAPI only, so the same command shape applies there.

## File Structure

**New — perception health core (pure Python, no ROS):**
- `src/perception/src/body_tracking/health/__init__.py` — package exports
- `src/perception/src/body_tracking/health/types.py` — dataclasses + enums
- `src/perception/src/body_tracking/health/ring_buffer.py` — timestamped RGB ring buffer
- `src/perception/src/body_tracking/health/signal_utils.py` — resample, bandpass, HR-from-signal
- `src/perception/src/body_tracking/health/backends.py` — `RPPGBackend`, `POSBackend`, `CHROMBackend`
- `src/perception/src/body_tracking/health/quality.py` — quality gates + confidence
- `src/perception/src/body_tracking/health/complexion.py` — 面色 appearance-only reading
- `src/perception/src/body_tracking/health/roi.py` — face ROI geometry + mean-RGB sampling
- `src/perception/src/body_tracking/health/estimator.py` — orchestrates buffer→PulseEstimate
- `src/perception/src/body_tracking/health/scan.py` — scan state machine
- `src/perception/src/body_tracking/health/messages.py` — versioned message builder
- `src/perception/src/body_tracking/health/config.py` — `HealthConfig` dataclass + defaults

**New — perception ROS glue (imports ROS; thin):**
- `src/perception/src/body_tracking/health/roi_detector.py` — MediaPipe Face Detection wrapper (no rclpy, but heavy dep)
- (modify) `src/perception/src/body_tracking/body_tracking_node.py` — sample ROI, timer, scan_cmd sub, publish

**New — orchestrator:**
- `src/orchestrator/web_server/health_bus.py` — latest-snapshot holder
- `src/orchestrator/routers/health.py` — `/health/*` HTTP endpoints
- (modify) `src/orchestrator/web_server/app.py` — mount router
- (modify) `src/orchestrator/ros_node.py` — subscribe `/health/metrics`, publish `/health/scan_cmd`
- (modify) `src/orchestrator/web_server/ui/index.html` — HR chip + scan card

**New — tests + tooling:**
- `src/perception/tests/conftest.py` — path setup
- `src/perception/tests/health/test_*.py` — unit tests
- (modify) `src/perception/pyproject.toml` — add `[project.optional-dependencies] test` (pytest, scipy)

---

### Task 1: Test scaffolding + core types

**Files:**
- Create: `src/perception/tests/conftest.py`
- Create: `src/perception/tests/health/__init__.py`
- Create: `src/perception/src/body_tracking/health/__init__.py`
- Create: `src/perception/src/body_tracking/health/types.py`
- Create: `src/perception/tests/health/test_types.py`
- Modify: `src/perception/pyproject.toml`

**Interfaces:**
- Produces: `RgbSample(t: float, r: float, g: float, b: float)`;
  `PulseEstimate(hr_bpm: float | None, confidence: float, spectral_snr: float, peak_dominance: float)`;
  `ScanState` enum (`IDLE, WARMING, COLLECTING, INSUFFICIENT_QUALITY, COMPLETE, FAILED, CANCELLED`, values are the lowercase strings);
  `GateResult(ok: bool, reason: str | None, components: dict)`.

- [ ] **Step 1: Add test deps to pyproject**

Append to `src/perception/pyproject.toml`:

```toml
[project.optional-dependencies]
test = [
    "pytest>=8.0",
    "scipy>=1.10",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 2: Write conftest for import path**

`src/perception/tests/conftest.py`:

```python
import sys
from pathlib import Path

# Make `body_tracking` importable as a top-level package in tests, matching
# the way the node runs (cwd = src/perception, package root = src/perception/src).
SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
```

- [ ] **Step 3: Write the failing test**

`src/perception/tests/health/test_types.py`:

```python
from body_tracking.health.types import RgbSample, PulseEstimate, ScanState, GateResult


def test_rgb_sample_is_immutable_and_carries_time():
    s = RgbSample(t=1.5, r=10.0, g=20.0, b=30.0)
    assert (s.t, s.r, s.g, s.b) == (1.5, 10.0, 20.0, 30.0)


def test_scan_state_values_are_lowercase_strings():
    assert ScanState.COLLECTING.value == "collecting"
    assert ScanState.INSUFFICIENT_QUALITY.value == "insufficient_quality"


def test_gate_result_defaults():
    g = GateResult(ok=True, reason=None, components={"face_px": 180})
    assert g.ok and g.reason is None and g.components["face_px"] == 180
```

- [ ] **Step 4: Run test to verify it fails**

Run: `cd src/perception && python -m pytest tests/health/test_types.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'body_tracking.health'`

- [ ] **Step 5: Create the package + types**

`src/perception/src/body_tracking/health/__init__.py`:

```python
"""Camera health-metrics (rPPG) core. Pure Python, no ROS imports."""
```

`src/perception/src/body_tracking/health/types.py`:

```python
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


@dataclass(frozen=True)
class RgbSample:
    t: float  # seconds, real frame timestamp
    r: float
    g: float
    b: float


@dataclass(frozen=True)
class PulseEstimate:
    hr_bpm: Optional[float]
    confidence: float          # 0..1
    spectral_snr: float
    peak_dominance: float


class ScanState(str, Enum):
    IDLE = "idle"
    WARMING = "warming"
    COLLECTING = "collecting"
    INSUFFICIENT_QUALITY = "insufficient_quality"
    COMPLETE = "complete"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class GateResult:
    ok: bool
    reason: Optional[str]
    components: dict = field(default_factory=dict)
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd src/perception && python -m pytest tests/health/test_types.py -v`
Expected: PASS (3 passed)

- [ ] **Step 7: Commit**

```bash
git add src/perception/pyproject.toml src/perception/tests src/perception/src/body_tracking/health/__init__.py src/perception/src/body_tracking/health/types.py
git commit -m "test: scaffold health package tests and core types"
```

---

### Task 2: RGB ring buffer

**Files:**
- Create: `src/perception/src/body_tracking/health/ring_buffer.py`
- Test: `src/perception/tests/health/test_ring_buffer.py`

**Interfaces:**
- Consumes: `RgbSample` (Task 1).
- Produces: `RgbRingBuffer(max_seconds: float)` with
  `append(sample: RgbSample) -> None`,
  `window(now: float, seconds: float) -> list[RgbSample]` (samples with `t > now - seconds`, time-ordered),
  `effective_fps(now: float, seconds: float) -> float` (count-1 over span, 0.0 if <2 samples),
  `__len__`.

- [ ] **Step 1: Write the failing test**

`src/perception/tests/health/test_ring_buffer.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd src/perception && python -m pytest tests/health/test_ring_buffer.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement**

`src/perception/src/body_tracking/health/ring_buffer.py`:

```python
from collections import deque
from typing import Deque, List

from .types import RgbSample


class RgbRingBuffer:
    """Time-ordered buffer of RGB samples, evicting anything older than
    `max_seconds` behind the newest sample."""

    def __init__(self, max_seconds: float) -> None:
        self._max_seconds = float(max_seconds)
        self._samples: Deque[RgbSample] = deque()

    def append(self, sample: RgbSample) -> None:
        self._samples.append(sample)
        newest = sample.t
        cutoff = newest - self._max_seconds
        while self._samples and self._samples[0].t < cutoff:
            self._samples.popleft()

    def window(self, now: float, seconds: float) -> List[RgbSample]:
        cutoff = now - seconds
        return [s for s in self._samples if s.t > cutoff]

    def effective_fps(self, now: float, seconds: float) -> float:
        win = self.window(now, seconds)
        if len(win) < 2:
            return 0.0
        span = win[-1].t - win[0].t
        if span <= 0:
            return 0.0
        return (len(win) - 1) / span

    def __len__(self) -> int:
        return len(self._samples)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd src/perception && python -m pytest tests/health/test_ring_buffer.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add src/perception/src/body_tracking/health/ring_buffer.py src/perception/tests/health/test_ring_buffer.py
git commit -m "feat: add timestamped RGB ring buffer for rPPG"
```

---

### Task 3: Signal utilities (resample, bandpass, HR-from-signal)

**Files:**
- Create: `src/perception/src/body_tracking/health/signal_utils.py`
- Test: `src/perception/tests/health/test_signal_utils.py`

**Interfaces:**
- Produces:
  `resample_uniform(ts: np.ndarray, values: np.ndarray, fps: float) -> np.ndarray` (linear interp onto uniform grid at `fps` spanning ts range);
  `bandpass(sig: np.ndarray, fps: float, lo_hz: float = 0.7, hi_hz: float = 4.0) -> np.ndarray` (zero-phase Butterworth; returns detrended input if too short);
  `hr_from_signal(sig: np.ndarray, fps: float, lo_hz: float = 0.7, hi_hz: float = 4.0) -> tuple[float | None, float, float]` returning `(hr_bpm, spectral_snr, peak_dominance)`. `hr_bpm` is `None` if `sig` shorter than `int(fps * 2)` samples. `peak_dominance` is the fraction of in-band power concentrated within `PEAK_NEIGHBOURHOOD_HZ` (0.2 Hz) of the peak frequency, over total-in-band-power, in `[0,1]` — i.e. `sum(band_power[|band_freqs - peak_freq| <= 0.2]) / sum(band_power)`. This neighbourhood-sum form is invariant to the FFT zero-padding factor, unlike a naive single-bin `peak_power / total` ratio (which is not: it shrinks as `n_fft` grows because a pure tone's energy is spread across more, narrower bins). `spectral_snr` is peak-power (single bin) / median-in-band-power.

- [ ] **Step 1: Write the failing test**

`src/perception/tests/health/test_signal_utils.py`:

```python
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


def test_peak_dominance_discriminates_noise_from_clean_tone():
    fps = 30.0
    t = np.arange(0, 15, 1 / fps)
    clean_sig = np.sin(2 * np.pi * 1.2 * t)  # exactly 72 bpm, noiseless
    _, _, clean_dominance = hr_from_signal(clean_sig, fps)

    rng = np.random.RandomState(0)
    noise_sig = rng.randn(t.size)  # pure broadband noise, no dominant tone
    _, _, noise_dominance = hr_from_signal(noise_sig, fps)

    assert noise_dominance < 0.5
    assert noise_dominance < clean_dominance
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd src/perception && python -m pytest tests/health/test_signal_utils.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement**

`src/perception/src/body_tracking/health/signal_utils.py`:

```python
from typing import Optional, Tuple

import numpy as np
from scipy import signal as sp_signal

# Half-width (Hz) of the neighbourhood around the spectral peak used to
# compute peak_dominance. Chosen to be invariant to zero-padding: widening
# the FFT (n_fft) redistributes a sinusoid's energy across more, narrower
# bins, but the total power within a fixed +/-Hz window around the peak
# frequency stays stable.
PEAK_NEIGHBOURHOOD_HZ = 0.2


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
    peak_freq = float(band_freqs[peak_idx])
    total = float(band_power.sum())
    median = float(np.median(band_power)) or 1e-12
    hr_bpm = float(band_freqs[peak_idx] * 60.0)
    # peak_dominance = fraction of in-band power concentrated in a narrow
    # neighbourhood around the peak frequency (invariant to zero-padding),
    # NOT a single-bin peak_power / total ratio (which shrinks as n_fft grows).
    neighbourhood = np.abs(band_freqs - peak_freq) <= PEAK_NEIGHBOURHOOD_HZ
    neighbourhood_power = float(band_power[neighbourhood].sum())
    dominance = neighbourhood_power / total if total > 0 else 0.0
    snr = peak_power / median
    return hr_bpm, snr, dominance
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd src/perception && python -m pytest tests/health/test_signal_utils.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add src/perception/src/body_tracking/health/signal_utils.py src/perception/tests/health/test_signal_utils.py
git commit -m "feat: add rPPG signal utilities (resample, bandpass, HR extraction)"
```

---

### Task 4: POS/CHROM backends

**Files:**
- Create: `src/perception/src/body_tracking/health/backends.py`
- Test: `src/perception/tests/health/test_backends.py`

**Interfaces:**
- Consumes: `PulseEstimate` (Task 1), `resample_uniform`, `hr_from_signal` (Task 3).
- Produces:
  `RPPGBackend` Protocol with `estimate(rgb: np.ndarray, ts: np.ndarray) -> PulseEstimate` where `rgb` is shape `(N, 3)` in R,G,B order;
  `POSBackend` (Wang 2017 projection) and `CHROMBackend` (de Haan 2013);
  `make_backend(name: str) -> RPPGBackend` (`"pos"` | `"chrom"`, else ValueError).

- [ ] **Step 1: Write the failing test**

`src/perception/tests/health/test_backends.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd src/perception && python -m pytest tests/health/test_backends.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement**

`src/perception/src/body_tracking/health/backends.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd src/perception && python -m pytest tests/health/test_backends.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/perception/src/body_tracking/health/backends.py src/perception/tests/health/test_backends.py
git commit -m "feat: add POS and CHROM rPPG backends"
```

---

### Task 5: Health config

**Files:**
- Create: `src/perception/src/body_tracking/health/config.py`
- Test: `src/perception/tests/health/test_config.py`

**Interfaces:**
- Produces: `Gates` dataclass (`min_fps, max_drop_ratio, min_face_px, min_roi_px, max_jitter_ms, max_motion, max_illum_delta, min_confidence`); `HealthConfig` dataclass (`enabled, backend, detector, ambient_window_s, scan_window_s, scan_timeout_s, lock_camera_on_scan, complexion_enabled, gates`) with `HealthConfig.default()` and `HealthConfig.from_dict(d: dict)` (unknown keys ignored, missing keys use defaults).

- [ ] **Step 1: Write the failing test**

`src/perception/tests/health/test_config.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd src/perception && python -m pytest tests/health/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement**

`src/perception/src/body_tracking/health/config.py`:

```python
from dataclasses import dataclass, field, fields


@dataclass(frozen=True)
class Gates:
    min_fps: float = 15.0
    max_drop_ratio: float = 0.2
    min_face_px: int = 120
    min_roi_px: int = 3000
    max_jitter_ms: float = 20.0
    max_motion: float = 0.05
    max_illum_delta: float = 0.15
    min_confidence: float = 0.5

    @classmethod
    def from_dict(cls, d: dict) -> "Gates":
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in (d or {}).items() if k in known})


@dataclass(frozen=True)
class HealthConfig:
    enabled: bool = True
    backend: str = "pos"
    detector: str = "mediapipe_face"   # or "pose_fallback"
    ambient_window_s: float = 10.0
    scan_window_s: float = 30.0        # target CLEAN seconds
    scan_timeout_s: float = 90.0       # wall-clock guard
    lock_camera_on_scan: bool = True
    complexion_enabled: bool = True
    gates: Gates = field(default_factory=Gates)

    @classmethod
    def default(cls) -> "HealthConfig":
        return cls()

    @classmethod
    def from_dict(cls, d: dict) -> "HealthConfig":
        d = dict(d or {})
        gates = Gates.from_dict(d.pop("gates", {}) or {})
        known = {f.name for f in fields(cls)} - {"gates"}
        kwargs = {k: v for k, v in d.items() if k in known}
        return cls(gates=gates, **kwargs)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd src/perception && python -m pytest tests/health/test_config.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add src/perception/src/body_tracking/health/config.py src/perception/tests/health/test_config.py
git commit -m "feat: add HealthConfig with gates and defaults"
```

---

### Task 6: Quality gates

**Files:**
- Create: `src/perception/src/body_tracking/health/quality.py`
- Test: `src/perception/tests/health/test_quality.py`

**Interfaces:**
- Consumes: `Gates` (Task 5), `GateResult` (Task 1).
- Produces: `evaluate_gates(components: dict, gates: Gates) -> GateResult`. `components` keys: `face_present: bool, single_target: bool, roi_in_bounds: bool, face_px: int, roi_px: int, effective_fps: float, drop_ratio: float, jitter_ms: float, motion: float, illum_delta: float, exposure_stable: bool`. Returns `ok=False` with the first failing `reason` (stable check order), and always echoes `components`.

- [ ] **Step 1: Write the failing test**

`src/perception/tests/health/test_quality.py`:

```python
from body_tracking.health.quality import evaluate_gates
from body_tracking.health.config import Gates


def _good():
    return {
        "face_present": True, "single_target": True, "roi_in_bounds": True,
        "face_px": 180, "roi_px": 6000, "effective_fps": 25.0, "drop_ratio": 0.02,
        "jitter_ms": 5.0, "motion": 0.01, "illum_delta": 0.05, "exposure_stable": True,
    }


def test_all_gates_pass():
    res = evaluate_gates(_good(), Gates())
    assert res.ok and res.reason is None


def test_low_fps_fails_with_reason():
    c = _good(); c["effective_fps"] = 5.0
    res = evaluate_gates(c, Gates())
    assert not res.ok and res.reason == "low_fps"


def test_no_face_fails_first():
    c = _good(); c["face_present"] = False; c["effective_fps"] = 5.0
    res = evaluate_gates(c, Gates())
    assert res.reason == "no_face"  # face checked before fps


def test_components_are_echoed():
    res = evaluate_gates(_good(), Gates())
    assert res.components["face_px"] == 180
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd src/perception && python -m pytest tests/health/test_quality.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement**

`src/perception/src/body_tracking/health/quality.py`:

```python
from .config import Gates
from .types import GateResult


def evaluate_gates(components: dict, gates: Gates) -> GateResult:
    c = components
    checks = [
        (not c.get("face_present", False), "no_face"),
        (not c.get("single_target", False), "multiple_targets"),
        (not c.get("roi_in_bounds", False), "roi_out_of_bounds"),
        (c.get("face_px", 0) < gates.min_face_px, "face_too_small"),
        (c.get("roi_px", 0) < gates.min_roi_px, "roi_too_small"),
        (c.get("effective_fps", 0.0) < gates.min_fps, "low_fps"),
        (c.get("drop_ratio", 1.0) > gates.max_drop_ratio, "dropped_frames"),
        (c.get("jitter_ms", 1e9) > gates.max_jitter_ms, "timestamp_jitter"),
        (c.get("motion", 1e9) > gates.max_motion, "head_motion"),
        (c.get("illum_delta", 1e9) > gates.max_illum_delta, "illumination_change"),
        (not c.get("exposure_stable", False), "exposure_unstable"),
    ]
    for failed, reason in checks:
        if failed:
            return GateResult(ok=False, reason=reason, components=dict(c))
    return GateResult(ok=True, reason=None, components=dict(c))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd src/perception && python -m pytest tests/health/test_quality.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add src/perception/src/body_tracking/health/quality.py src/perception/tests/health/test_quality.py
git commit -m "feat: add rPPG quality gate evaluation"
```

---

### Task 7: Complexion (面色) appearance reading

**Files:**
- Create: `src/perception/src/body_tracking/health/complexion.py`
- Test: `src/perception/tests/health/test_complexion.py`

**Interfaces:**
- Produces: `describe_complexion(mean_rgb: tuple[float, float, float]) -> dict` returning
  `{"appearance_zh": str, "appearance_en": str, "caveat": str}`. Input channels are 0..255.
  Logic (appearance only, no health words): brightness = mean of channels; ruddiness = R - G.
  Dark → 面色偏暗 / dim appearance; high ruddiness → 面色红润 / rosy appearance; low ruddiness →
  面色偏白 / pale appearance; else 面色均匀 / even appearance. Caveat is fixed bilingual text.

- [ ] **Step 1: Write the failing test**

`src/perception/tests/health/test_complexion.py`:

```python
from body_tracking.health.complexion import describe_complexion


def test_rosy_when_red_dominant():
    d = describe_complexion((200.0, 150.0, 150.0))
    assert d["appearance_zh"] == "面色红润"
    assert d["appearance_en"] == "rosy appearance"


def test_pale_when_low_ruddiness_and_bright():
    d = describe_complexion((190.0, 195.0, 195.0))
    assert d["appearance_zh"] == "面色偏白"


def test_dim_when_dark():
    d = describe_complexion((40.0, 38.0, 36.0))
    assert d["appearance_zh"] == "面色偏暗"


def test_caveat_is_non_medical():
    d = describe_complexion((150.0, 140.0, 140.0))
    assert "not a health" in d["caveat"].lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd src/perception && python -m pytest tests/health/test_complexion.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement**

`src/perception/src/body_tracking/health/complexion.py`:

```python
_CAVEAT = "外观描述，受光线与白平衡影响，非健康指标 / appearance only, lighting-dependent, not a health indicator"

_DIM_BRIGHTNESS = 70.0
_RUDDY_HIGH = 25.0
_RUDDY_LOW = 8.0


def describe_complexion(mean_rgb):
    r, g, b = (float(mean_rgb[0]), float(mean_rgb[1]), float(mean_rgb[2]))
    brightness = (r + g + b) / 3.0
    ruddiness = r - g
    if brightness < _DIM_BRIGHTNESS:
        zh, en = "面色偏暗", "dim appearance"
    elif ruddiness >= _RUDDY_HIGH:
        zh, en = "面色红润", "rosy appearance"
    elif ruddiness <= _RUDDY_LOW:
        zh, en = "面色偏白", "pale appearance"
    else:
        zh, en = "面色均匀", "even appearance"
    return {"appearance_zh": zh, "appearance_en": en, "caveat": _CAVEAT}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd src/perception && python -m pytest tests/health/test_complexion.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add src/perception/src/body_tracking/health/complexion.py src/perception/tests/health/test_complexion.py
git commit -m "feat: add appearance-only complexion (mian se) reading"
```

---

### Task 8: Face ROI geometry + mean-RGB sampling

**Files:**
- Create: `src/perception/src/body_tracking/health/roi.py`
- Test: `src/perception/tests/health/test_roi.py`

**Interfaces:**
- Produces:
  `FaceRoi(patches: list[tuple[int,int,int,int]], face_px: int)` (patches are `(x, y, w, h)` in full-frame pixels);
  `roi_from_pose(nose_xy: tuple[float,float], left_eye_xy, right_eye_xy, frame_w: int, frame_h: int) -> FaceRoi | None` (builds forehead + two cheek patches from eye spacing; None if degenerate/out of bounds);
  `sample_mean_rgb(frame_bgr: np.ndarray, roi: FaceRoi) -> tuple[float,float,float] | None` returns R,G,B means (0..255) across all in-bounds patch pixels, or `None` if no patch has valid (non-negative-origin, in-bounds) pixels -- `None` is an explicit failure sentinel, distinct from a legitimately dark all-zero sample; `roi_pixel_count(frame_bgr: np.ndarray, roi: FaceRoi) -> int` counts pixels from the same validated patches as `sample_mean_rgb` (shared in-bounds filter), so the count and the sample never disagree. A patch is valid only if `x >= 0`, `y >= 0`, `w > 0`, `h > 0`, and it does not extend past the frame edges -- negative-origin patches are rejected outright rather than clipped, since a numpy slice with a negative start index silently wraps to the opposite edge of the frame instead of raising.

- [ ] **Step 1: Write the failing test**

`src/perception/tests/health/test_roi.py`:

```python
import numpy as np

from body_tracking.health.roi import roi_from_pose, sample_mean_rgb, roi_pixel_count, FaceRoi


def test_roi_from_pose_builds_patches_in_bounds():
    roi = roi_from_pose(
        nose_xy=(320, 250), left_eye_xy=(300, 235), right_eye_xy=(340, 235),
        frame_w=640, frame_h=480,
    )
    assert roi is not None
    assert len(roi.patches) >= 2
    for (x, y, w, h) in roi.patches:
        assert x >= 0 and y >= 0 and x + w <= 640 and y + h <= 480 and w > 0 and h > 0
    assert roi.face_px > 0


def test_roi_from_pose_none_when_eyes_coincide():
    roi = roi_from_pose((10, 10), (10, 10), (10, 10), 640, 480)
    assert roi is None


def test_sample_mean_rgb_reads_bgr_frame_as_rgb():
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    frame[:, :, 2] = 200  # red channel (BGR index 2)
    frame[:, :, 1] = 100  # green
    frame[:, :, 0] = 50   # blue
    roi = FaceRoi(patches=[(100, 100, 20, 20)], face_px=40)
    r, g, b = sample_mean_rgb(frame, roi)
    assert (round(r), round(g), round(b)) == (200, 100, 50)
    assert roi_pixel_count(roi) == 400
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd src/perception && python -m pytest tests/health/test_roi.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement**

`src/perception/src/body_tracking/health/roi.py`:

```python
from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np


@dataclass(frozen=True)
class FaceRoi:
    patches: List[Tuple[int, int, int, int]]  # (x, y, w, h) full-frame pixels
    face_px: int


def _clip_patch(x, y, w, h, frame_w, frame_h):
    x = int(max(0, min(x, frame_w - 1)))
    y = int(max(0, min(y, frame_h - 1)))
    w = int(max(0, min(w, frame_w - x)))
    h = int(max(0, min(h, frame_h - y)))
    return (x, y, w, h)


def roi_from_pose(nose_xy, left_eye_xy, right_eye_xy, frame_w, frame_h) -> Optional[FaceRoi]:
    (nx, ny) = nose_xy
    (lx, ly) = left_eye_xy
    (rx, ry) = right_eye_xy
    eye_dx = abs(rx - lx)
    eye_dy = abs(ry - ly)
    eye_dist = (eye_dx ** 2 + eye_dy ** 2) ** 0.5
    if eye_dist < 5.0:
        return None
    face_px = int(eye_dist * 2.2)  # rough face width from eye spacing
    patch = max(6, int(eye_dist * 0.5))
    eye_cx = (lx + rx) / 2.0
    eye_cy = (ly + ry) / 2.0
    forehead = _clip_patch(eye_cx - patch / 2, eye_cy - eye_dist * 1.1, patch, patch, frame_w, frame_h)
    left_cheek = _clip_patch(lx - patch, ny - patch / 2, patch, patch, frame_w, frame_h)
    right_cheek = _clip_patch(rx, ny - patch / 2, patch, patch, frame_w, frame_h)
    patches = [p for p in (forehead, left_cheek, right_cheek) if p[2] > 0 and p[3] > 0]
    if len(patches) < 2:
        return None
    return FaceRoi(patches=patches, face_px=face_px)


def sample_mean_rgb(frame_bgr: np.ndarray, roi: FaceRoi) -> Tuple[float, float, float]:
    b_vals, g_vals, r_vals = [], [], []
    h_frame, w_frame = frame_bgr.shape[:2]
    for (x, y, w, h) in roi.patches:
        if w <= 0 or h <= 0 or x + w > w_frame or y + h > h_frame:
            continue
        crop = frame_bgr[y:y + h, x:x + w].reshape(-1, 3).astype(float)
        b_vals.append(crop[:, 0])
        g_vals.append(crop[:, 1])
        r_vals.append(crop[:, 2])
    if not r_vals:
        return (0.0, 0.0, 0.0)
    r = float(np.concatenate(r_vals).mean())
    g = float(np.concatenate(g_vals).mean())
    b = float(np.concatenate(b_vals).mean())
    return (r, g, b)


def roi_pixel_count(roi: FaceRoi) -> int:
    return int(sum(w * h for (_, _, w, h) in roi.patches))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd src/perception && python -m pytest tests/health/test_roi.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/perception/src/body_tracking/health/roi.py src/perception/tests/health/test_roi.py
git commit -m "feat: add face ROI geometry and mean-RGB sampling"
```

---

### Task 9: Scan state machine

**Files:**
- Create: `src/perception/src/body_tracking/health/scan.py`
- Test: `src/perception/tests/health/test_scan.py`

**Interfaces:**
- Consumes: `ScanState` (Task 1).
- Produces: `ScanController(target_clean_s: float, timeout_s: float, warmup_s: float = 2.0)` with:
  `start(measurement_id: str, now: float) -> None`,
  `cancel(now: float) -> None`,
  `update(now: float, gate_ok: bool) -> None` (accumulates clean seconds only while gate_ok; enters `INSUFFICIENT_QUALITY` if no clean second accepted within `warmup_s` grace after start and not yet collecting; `COMPLETE` when clean seconds ≥ target; `FAILED` on timeout),
  properties `state: ScanState`, `progress_clean_s: float`, `measurement_id: str | None`.
  Clean-second accrual uses the delta between consecutive `update` calls while `gate_ok` is True.

- [ ] **Step 1: Write the failing test**

`src/perception/tests/health/test_scan.py`:

```python
from body_tracking.health.scan import ScanController
from body_tracking.health.types import ScanState


def test_completes_after_enough_clean_seconds():
    sc = ScanController(target_clean_s=3.0, timeout_s=30.0)
    sc.start("m1", now=0.0)
    t = 0.0
    while sc.state not in (ScanState.COMPLETE, ScanState.FAILED):
        t += 0.5
        sc.update(now=t, gate_ok=True)
    assert sc.state == ScanState.COMPLETE
    assert sc.progress_clean_s >= 3.0
    assert sc.measurement_id == "m1"


def test_bad_quality_does_not_accrue_progress():
    sc = ScanController(target_clean_s=3.0, timeout_s=30.0)
    sc.start("m2", now=0.0)
    for i in range(1, 11):
        sc.update(now=i * 0.5, gate_ok=False)
    assert sc.progress_clean_s == 0.0
    assert sc.state in (ScanState.WARMING, ScanState.INSUFFICIENT_QUALITY)


def test_timeout_fails_the_scan():
    sc = ScanController(target_clean_s=30.0, timeout_s=5.0)
    sc.start("m3", now=0.0)
    sc.update(now=6.0, gate_ok=True)
    assert sc.state == ScanState.FAILED


def test_cancel_sets_state():
    sc = ScanController(target_clean_s=30.0, timeout_s=30.0)
    sc.start("m4", now=0.0)
    sc.cancel(now=1.0)
    assert sc.state == ScanState.CANCELLED
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd src/perception && python -m pytest tests/health/test_scan.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement**

`src/perception/src/body_tracking/health/scan.py`:

```python
from typing import Optional

from .types import ScanState


class ScanController:
    def __init__(self, target_clean_s: float, timeout_s: float, warmup_s: float = 2.0) -> None:
        self._target = float(target_clean_s)
        self._timeout = float(timeout_s)
        self._warmup = float(warmup_s)
        self._state = ScanState.IDLE
        self._clean = 0.0
        self._mid: Optional[str] = None
        self._start_t = 0.0
        self._last_t = 0.0

    @property
    def state(self) -> ScanState:
        return self._state

    @property
    def progress_clean_s(self) -> float:
        return self._clean

    @property
    def measurement_id(self) -> Optional[str]:
        return self._mid

    def start(self, measurement_id: str, now: float) -> None:
        self._state = ScanState.WARMING
        self._clean = 0.0
        self._mid = measurement_id
        self._start_t = now
        self._last_t = now

    def cancel(self, now: float) -> None:
        if self._state in (ScanState.WARMING, ScanState.COLLECTING, ScanState.INSUFFICIENT_QUALITY):
            self._state = ScanState.CANCELLED

    def update(self, now: float, gate_ok: bool) -> None:
        if self._state not in (ScanState.WARMING, ScanState.COLLECTING, ScanState.INSUFFICIENT_QUALITY):
            return
        dt = max(0.0, now - self._last_t)
        self._last_t = now

        if now - self._start_t > self._timeout:
            self._state = ScanState.FAILED
            return

        if gate_ok:
            self._clean += dt
            self._state = ScanState.COLLECTING
            if self._clean >= self._target:
                self._state = ScanState.COMPLETE
            return

        # gate not ok
        if self._state == ScanState.COLLECTING:
            self._state = ScanState.INSUFFICIENT_QUALITY
        elif self._state == ScanState.WARMING and (now - self._start_t) > self._warmup:
            self._state = ScanState.INSUFFICIENT_QUALITY
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd src/perception && python -m pytest tests/health/test_scan.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add src/perception/src/body_tracking/health/scan.py src/perception/tests/health/test_scan.py
git commit -m "feat: add on-demand scan state machine"
```

---

### Task 10: Versioned message builder

**Files:**
- Create: `src/perception/src/body_tracking/health/messages.py`
- Test: `src/perception/tests/health/test_messages.py`

**Interfaces:**
- Consumes: `PulseEstimate` (Task 1), `ScanState` (Task 1).
- Produces: `SCHEMA_VERSION = 1`;
  `build_metrics(ts: float, mode: str, state: ScanState, effective_fps: float, window_s: float, estimate: PulseEstimate | None, quality_components: dict, complexion: dict | None, reason: str | None, scan_progress_s: float, scan_target_s: float) -> dict`.
  Output always includes `schema_version`, nulls for `resp_bpm`/`hrv_sdnn_ms`/`spo2_pct`, and `hr_bpm`/`hr_confidence` null when `estimate` is None or `estimate.hr_bpm` is None.

- [ ] **Step 1: Write the failing test**

`src/perception/tests/health/test_messages.py`:

```python
from body_tracking.health.messages import build_metrics, SCHEMA_VERSION
from body_tracking.health.types import PulseEstimate, ScanState


def test_message_has_schema_and_null_unsupported():
    est = PulseEstimate(hr_bpm=72.0, confidence=0.8, spectral_snr=6.0, peak_dominance=0.7)
    msg = build_metrics(
        ts=123.0, mode="ambient", state=ScanState.IDLE, effective_fps=25.0,
        window_s=10.0, estimate=est, quality_components={"face_px": 180},
        complexion=None, reason=None, scan_progress_s=0.0, scan_target_s=30.0,
    )
    assert msg["schema_version"] == SCHEMA_VERSION
    assert msg["hr_bpm"] == 72.0 and msg["hr_confidence"] == 0.8
    assert msg["resp_bpm"] is None and msg["hrv_sdnn_ms"] is None and msg["spo2_pct"] is None
    assert msg["state"] == "idle"


def test_hr_null_when_no_estimate():
    msg = build_metrics(
        ts=1.0, mode="ambient", state=ScanState.IDLE, effective_fps=0.0,
        window_s=10.0, estimate=None, quality_components={}, complexion=None,
        reason="no_face", scan_progress_s=0.0, scan_target_s=30.0,
    )
    assert msg["hr_bpm"] is None and msg["hr_confidence"] is None
    assert msg["reason"] == "no_face"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd src/perception && python -m pytest tests/health/test_messages.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement**

`src/perception/src/body_tracking/health/messages.py`:

```python
from typing import Optional

from .types import PulseEstimate, ScanState

SCHEMA_VERSION = 1


def build_metrics(
    ts: float,
    mode: str,
    state: ScanState,
    effective_fps: float,
    window_s: float,
    estimate: Optional[PulseEstimate],
    quality_components: dict,
    complexion: Optional[dict],
    reason: Optional[str],
    scan_progress_s: float,
    scan_target_s: float,
) -> dict:
    hr = estimate.hr_bpm if estimate is not None else None
    conf = estimate.confidence if (estimate is not None and hr is not None) else None
    return {
        "schema_version": SCHEMA_VERSION,
        "ts": ts,
        "mode": mode,
        "state": state.value,
        "reason": reason,
        "effective_fps": round(effective_fps, 2),
        "window_s": window_s,
        "hr_bpm": round(hr, 1) if hr is not None else None,
        "hr_confidence": round(conf, 2) if conf is not None else None,
        "quality_components": quality_components,
        "complexion": complexion,
        "resp_bpm": None,     # not_supported in v1
        "hrv_sdnn_ms": None,  # not_supported in v1
        "spo2_pct": None,     # not_supported in v1
        "scan": {"progress_clean_s": round(scan_progress_s, 1), "target_s": scan_target_s},
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd src/perception && python -m pytest tests/health/test_messages.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add src/perception/src/body_tracking/health/messages.py src/perception/tests/health/test_messages.py
git commit -m "feat: add versioned health metrics message builder"
```

---

### Task 11: Estimator (buffer → ambient PulseEstimate + hysteresis)

**Files:**
- Create: `src/perception/src/body_tracking/health/estimator.py`
- Test: `src/perception/tests/health/test_estimator.py`

**Interfaces:**
- Consumes: `RgbRingBuffer` (Task 2), `RPPGBackend`/`make_backend` (Task 4), `HealthConfig` (Task 5), `PulseEstimate` (Task 1).
- Produces: `RPPGEstimator(config: HealthConfig, backend: RPPGBackend | None = None)` with
  `add_sample(sample: RgbSample) -> None`,
  `estimate(now: float, window_s: float) -> PulseEstimate` (pulls window from buffer, runs backend, applies max-jump hysteresis limiting HR change to ≤12 bpm vs last accepted when confidence ≥ min_confidence),
  `effective_fps(now: float, window_s: float) -> float`.

- [ ] **Step 1: Write the failing test**

`src/perception/tests/health/test_estimator.py`:

```python
import numpy as np

from body_tracking.health.estimator import RPPGEstimator
from body_tracking.health.config import HealthConfig
from body_tracking.health.types import RgbSample


def _feed_pulse(est, fps=30.0, secs=15.0, hr_hz=1.2):
    t = np.arange(0, secs, 1 / fps)
    pulse = 0.02 * np.sin(2 * np.pi * hr_hz * t)
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd src/perception && python -m pytest tests/health/test_estimator.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement**

`src/perception/src/body_tracking/health/estimator.py`:

```python
from typing import Optional

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

    def estimate(self, now: float, window_s: float) -> PulseEstimate:
        win = self._buffer.window(now, window_s)
        if len(win) < 3:
            return PulseEstimate(None, 0.0, 0.0, 0.0)
        ts = np.array([s.t for s in win])
        rgb = np.array([[s.r, s.g, s.b] for s in win])
        est = self._backend.estimate(rgb, ts)
        if est.hr_bpm is None or est.confidence < self._config.gates.min_confidence:
            return est
        # Hysteresis: clamp large jumps once we have a prior accepted value.
        if self._last_hr is not None and abs(est.hr_bpm - self._last_hr) > MAX_HR_JUMP_BPM:
            clamped = self._last_hr + np.sign(est.hr_bpm - self._last_hr) * MAX_HR_JUMP_BPM
            est = PulseEstimate(float(clamped), est.confidence, est.spectral_snr, est.peak_dominance)
        self._last_hr = est.hr_bpm
        return est
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd src/perception && python -m pytest tests/health/test_estimator.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Run the whole health suite**

Run: `cd src/perception && python -m pytest tests/health -v`
Expected: PASS (all tasks 1–11 green)

- [ ] **Step 6: Commit**

```bash
git add src/perception/src/body_tracking/health/estimator.py src/perception/tests/health/test_estimator.py
git commit -m "feat: add rPPG estimator with hysteresis over the sample buffer"
```

---

### Task 12: Face-detector ROI wrapper (MediaPipe) + package exports

**Files:**
- Create: `src/perception/src/body_tracking/health/roi_detector.py`
- Modify: `src/perception/src/body_tracking/health/__init__.py`
- Test: `src/perception/tests/health/test_exports.py`

**Interfaces:**
- Consumes: `FaceRoi`, `roi_from_pose` (Task 8).
- Produces: `FaceRoiExtractor(model_asset_path: str | None = None)` with
  `update(frame_bgr: np.ndarray) -> FaceRoi | None` (MediaPipe Face Detection; builds forehead+cheek patches from the detected box/keypoints, returns None when no single confident face);
  and re-exports the core symbols from `health/__init__.py` for ergonomic imports.
  The MediaPipe call path is exercised on-device (Task 16), not in unit tests; the unit test only asserts importability and that `update` returns None on a black frame.

- [ ] **Step 1: Write the failing test**

`src/perception/tests/health/test_exports.py`:

```python
import numpy as np


def test_public_exports_are_importable():
    from body_tracking.health import (
        RPPGEstimator, HealthConfig, ScanController, build_metrics, describe_complexion,
    )
    assert RPPGEstimator and HealthConfig and ScanController and build_metrics and describe_complexion


def test_face_extractor_returns_none_on_black_frame():
    from body_tracking.health.roi_detector import FaceRoiExtractor
    ext = FaceRoiExtractor()
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    assert ext.update(frame) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd src/perception && python -m pytest tests/health/test_exports.py -v`
Expected: FAIL (ImportError on the `health` re-exports)

- [ ] **Step 3: Implement the extractor**

`src/perception/src/body_tracking/health/roi_detector.py`:

```python
import logging
from typing import Optional

import numpy as np
import cv2
import mediapipe as mp

from .roi import FaceRoi, _clip_patch

logger = logging.getLogger(__name__)


class FaceRoiExtractor:
    """MediaPipe Face Detection → forehead + cheek patches. CPU, lightweight."""

    def __init__(self, model_asset_path: Optional[str] = None, min_confidence: float = 0.6) -> None:
        self._min_conf = min_confidence
        self._detector = mp.solutions.face_detection.FaceDetection(
            model_selection=0, min_detection_confidence=min_confidence
        )

    def update(self, frame_bgr: np.ndarray) -> Optional[FaceRoi]:
        h, w = frame_bgr.shape[:2]
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        result = self._detector.process(rgb)
        if not result.detections:
            return None
        if len(result.detections) > 1:
            return None  # single-target gate handled upstream, but avoid ambiguity here
        det = result.detections[0]
        box = det.location_data.relative_bounding_box
        fx, fy = int(box.xmin * w), int(box.ymin * h)
        fw, fh = int(box.width * w), int(box.height * h)
        if fw <= 0 or fh <= 0:
            return None
        patch = max(6, int(fw * 0.25))
        forehead = _clip_patch(fx + fw // 2 - patch // 2, fy + int(fh * 0.08), patch, patch, w, h)
        left_cheek = _clip_patch(fx + int(fw * 0.12), fy + int(fh * 0.55), patch, patch, w, h)
        right_cheek = _clip_patch(fx + fw - int(fw * 0.12) - patch, fy + int(fh * 0.55), patch, patch, w, h)
        patches = [p for p in (forehead, left_cheek, right_cheek) if p[2] > 0 and p[3] > 0]
        if len(patches) < 2:
            return None
        return FaceRoi(patches=patches, face_px=fw)
```

- [ ] **Step 4: Add re-exports**

Replace `src/perception/src/body_tracking/health/__init__.py` with:

```python
"""Camera health-metrics (rPPG) core. Pure Python, no ROS imports."""

from .config import HealthConfig, Gates
from .types import RgbSample, PulseEstimate, ScanState, GateResult
from .estimator import RPPGEstimator
from .scan import ScanController
from .messages import build_metrics, SCHEMA_VERSION
from .complexion import describe_complexion
from .quality import evaluate_gates

__all__ = [
    "HealthConfig", "Gates", "RgbSample", "PulseEstimate", "ScanState", "GateResult",
    "RPPGEstimator", "ScanController", "build_metrics", "SCHEMA_VERSION",
    "describe_complexion", "evaluate_gates",
]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd src/perception && python -m pytest tests/health/test_exports.py -v`
Expected: PASS (2 passed)

- [ ] **Step 6: Commit**

```bash
git add src/perception/src/body_tracking/health/roi_detector.py src/perception/src/body_tracking/health/__init__.py src/perception/tests/health/test_exports.py
git commit -m "feat: add MediaPipe face-ROI extractor and package exports"
```

---

### Task 13: Wire the health pipeline into the perception node

**Files:**
- Modify: `src/perception/src/body_tracking/body_tracking_node.py`
- Modify: `src/perception/src/body_tracking/main.py` (pass `health_config` through) — only if needed; default config is fine.

**Interfaces:**
- Consumes: `RPPGEstimator`, `ScanController`, `FaceRoiExtractor`, `evaluate_gates`, `build_metrics`, `describe_complexion`, `HealthConfig`, `RgbSample`, `sample_mean_rgb`, `roi_pixel_count`.
- Produces: publishes JSON on `/health/metrics` (`std_msgs/String`); subscribes `/health/scan_cmd` (`std_msgs/String`, JSON `{action: "start"|"cancel", measurement_id, window_s?}`).

This task has no unit test (ROS integration); verified in Task 16. Keep the image callback change minimal and guard the whole feature behind `config.enabled`.

- [ ] **Step 1: Add imports and init the health pipeline**

At the top of `body_tracking_node.py`, after existing imports, add:

```python
import uuid
from .health import (
    RPPGEstimator, ScanController, HealthConfig, RgbSample, build_metrics,
    describe_complexion, evaluate_gates,
)
from .health.roi_detector import FaceRoiExtractor
from .health.roi import sample_mean_rgb, roi_pixel_count
```

In `BodyTrackingNode.__init__`, after the annotated publisher block, add:

```python
        # --- Health metrics (rPPG) ---
        self.health_config = HealthConfig.default()
        self._health_last_roi = None
        self._health_last_mean = None
        if self.health_config.enabled:
            self._roi_extractor = FaceRoiExtractor()
            self._rppg = RPPGEstimator(self.health_config)
            self._scan = ScanController(
                target_clean_s=self.health_config.scan_window_s,
                timeout_s=self.health_config.scan_timeout_s,
            )
            self.health_pub = self.create_publisher(String, "/health/metrics", 10)
            self.scan_cmd_sub = self.create_subscription(
                String, "/health/scan_cmd", self._on_scan_cmd, 10
            )
            # Timer: run estimation + publish off the hot image path.
            self.create_timer(1.0, self._on_health_timer)
            self.get_logger().info("Health metrics (rPPG) enabled")
```

- [ ] **Step 2: Sample ROI color in the image callback (cheap only)**

In `image_callback`, immediately after `cv_image = self.bridge.imgmsg_to_cv2(...)` and computing `stamp`, add (guarded so it also runs on frames skipped for detection):

```python
        if getattr(self, "health_config", None) and self.health_config.enabled:
            self._sample_health_roi(cv_image, stamp.nanoseconds / 1e9)
```

Then add these methods to the class:

```python
    def _sample_health_roi(self, frame, t_sec: float) -> None:
        # Update ROI on this frame (extractor is cheap); reuse last ROI if none.
        roi = self._roi_extractor.update(frame)
        if roi is None:
            roi = self._health_last_roi
        if roi is None:
            self._health_last_roi = None
            return
        self._health_last_roi = roi
        sample = sample_mean_rgb(frame, roi)
        if sample is None:
            # No patch had valid (in-bounds) pixels this frame -- do not
            # fabricate a sample or append anything to the pulse buffer.
            return
        r, g, b = sample
        self._health_last_mean = (r, g, b, roi.face_px, roi_pixel_count(frame, roi))
        self._rppg.add_sample(RgbSample(t=t_sec, r=r, g=g, b=b))

    def _on_scan_cmd(self, msg: String) -> None:
        try:
            cmd = json.loads(msg.data or "{}")
        except (ValueError, TypeError):
            return
        now = datetime.now().timestamp()
        action = cmd.get("action")
        if action == "start":
            mid = cmd.get("measurement_id") or str(uuid.uuid4())
            self._scan.start(mid, now)
        elif action == "cancel":
            self._scan.cancel(now)

    def _on_health_timer(self) -> None:
        now = datetime.now().timestamp()
        window_s = self.health_config.ambient_window_s
        fps = self._rppg.effective_fps(now, window_s)
        est = self._rppg.estimate(now, window_s)

        have_face = self._health_last_roi is not None and self._health_last_mean is not None
        face_px = self._health_last_mean[3] if have_face else 0
        roi_px = self._health_last_mean[4] if have_face else 0
        components = {
            "face_present": have_face,
            "single_target": have_face,
            "roi_in_bounds": have_face,
            "face_px": face_px,
            "roi_px": roi_px,
            "effective_fps": fps,
            "drop_ratio": 0.0,
            "jitter_ms": 0.0,
            "motion": 0.0,
            "illum_delta": 0.0,
            "exposure_stable": True,
        }
        gate = evaluate_gates(components, self.health_config.gates)

        # Drive the scan state machine.
        self._scan.update(now, gate.ok and est.hr_bpm is not None)

        mode = "scan" if self._scan.measurement_id and self._scan.state.value in (
            "warming", "collecting", "insufficient_quality", "complete", "failed", "cancelled"
        ) else "ambient"

        complexion = None
        if self.health_config.complexion_enabled and have_face:
            complexion = describe_complexion(self._health_last_mean[:3])

        show_est = est if gate.ok else None
        msg = String()
        msg.data = json.dumps(build_metrics(
            ts=now, mode=mode, state=self._scan.state, effective_fps=fps,
            window_s=window_s, estimate=show_est, quality_components=components,
            complexion=complexion, reason=gate.reason,
            scan_progress_s=self._scan.progress_clean_s,
            scan_target_s=self.health_config.scan_window_s,
        ))
        self.health_pub.publish(msg)
```

- [ ] **Step 3: Byte-compile check**

Run: `cd src/perception && python -m py_compile src/body_tracking/body_tracking_node.py`
Expected: no output (success)

- [ ] **Step 4: Commit**

```bash
git add src/perception/src/body_tracking/body_tracking_node.py
git commit -m "feat: wire rPPG sampling, timer publish, and scan command into perception node"
```

---

### Task 14: Orchestrator HealthBus + HTTP router

**Files:**
- Create: `src/orchestrator/web_server/health_bus.py`
- Create: `src/orchestrator/routers/health.py`
- Modify: `src/orchestrator/web_server/app.py`
- Test: `src/orchestrator/tests/test_health_router.py`
- Create: `src/orchestrator/tests/__init__.py` (if missing)

**Interfaces:**
- Produces: `HealthBus` singleton (`health_bus`) with `set_metrics(d: dict)`, `get_metrics() -> dict | None`, and a `pending_scan_cmd` outbox: `request_scan(window_s) -> str` (returns measurement_id, queues `{action:"start",...}`), `request_cancel()`, `take_cmd() -> dict | None`.
- HTTP: `GET /health/live` → latest metrics or `{"state":"idle","hr_bpm":null}`; `POST /health/scan` → `{measurement_id}`; `GET /health/scan/status` → latest metrics; `POST /health/scan/cancel` → `{status:"ok"}`.

- [ ] **Step 1: Write the failing test**

`src/orchestrator/tests/test_health_router.py`:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient
from orchestrator.web_server.app import create_app
from orchestrator.web_server.health_bus import health_bus


def test_scan_and_live_roundtrip():
    app = create_app()
    client = TestClient(app)

    r = client.post("/health/scan", json={"window_s": 30})
    assert r.status_code == 200
    mid = r.json()["measurement_id"]
    assert mid

    cmd = health_bus.take_cmd()
    assert cmd["action"] == "start" and cmd["measurement_id"] == mid

    health_bus.set_metrics({"schema_version": 1, "hr_bpm": 71.0, "state": "collecting"})
    live = client.get("/health/live").json()
    assert live["hr_bpm"] == 71.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd src/orchestrator && python -m pytest tests/test_health_router.py -v`
Expected: FAIL (ImportError on `health_bus` / router not mounted)

- [ ] **Step 3: Implement the bus**

`src/orchestrator/web_server/health_bus.py`:

```python
import threading
import uuid
from typing import Optional


class HealthBus:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._metrics: Optional[dict] = None
        self._cmd: Optional[dict] = None

    def set_metrics(self, d: dict) -> None:
        with self._lock:
            self._metrics = d

    def get_metrics(self) -> Optional[dict]:
        with self._lock:
            return self._metrics

    def request_scan(self, window_s: float) -> str:
        mid = str(uuid.uuid4())
        with self._lock:
            self._cmd = {"action": "start", "measurement_id": mid, "window_s": window_s}
        return mid

    def request_cancel(self) -> None:
        with self._lock:
            self._cmd = {"action": "cancel"}

    def take_cmd(self) -> Optional[dict]:
        with self._lock:
            cmd, self._cmd = self._cmd, None
            return cmd


health_bus = HealthBus()
```

- [ ] **Step 4: Implement the router**

`src/orchestrator/routers/health.py`:

```python
from fastapi import APIRouter
from ..web_server.health_bus import health_bus

router = APIRouter()

_IDLE = {"schema_version": 1, "state": "idle", "hr_bpm": None, "hr_confidence": None}


@router.get("/live")
async def live():
    return health_bus.get_metrics() or _IDLE


@router.post("/scan")
async def start_scan(body: dict | None = None):
    window_s = float((body or {}).get("window_s", 30.0))
    mid = health_bus.request_scan(window_s)
    return {"measurement_id": mid}


@router.get("/scan/status")
async def scan_status():
    return health_bus.get_metrics() or _IDLE


@router.post("/scan/cancel")
async def cancel_scan():
    health_bus.request_cancel()
    return {"status": "ok"}
```

- [ ] **Step 5: Mount the router**

In `src/orchestrator/web_server/app.py`, add `health` to the import and include it:

```python
from ..routers import events, actions, health
```

and inside `create_app()`, after the existing `include_router` calls:

```python
    app.include_router(health.router, prefix="/health", tags=["health"])
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd src/orchestrator && python -m pytest tests/test_health_router.py -v`
Expected: PASS (1 passed)

- [ ] **Step 7: Commit**

```bash
git add src/orchestrator/web_server/health_bus.py src/orchestrator/routers/health.py src/orchestrator/web_server/app.py src/orchestrator/tests
git commit -m "feat: add orchestrator HealthBus and /health HTTP endpoints"
```

---

### Task 15: Orchestrator ROS bridge (subscribe metrics, publish scan_cmd)

**Files:**
- Modify: `src/orchestrator/ros_node.py`

**Interfaces:**
- Consumes: `health_bus` (Task 14).
- Produces: subscribes `/health/metrics` (`std_msgs/String`) → `health_bus.set_metrics(json)`; a timer (~5 Hz) drains `health_bus.take_cmd()` and publishes to `/health/scan_cmd` (`std_msgs/String`).

No unit test (ROS integration); verified in Task 16.

- [ ] **Step 1: Add the subscription, publisher, and drain timer**

In `src/orchestrator/ros_node.py`, inside `DorabotOrchestratorNode.__init__`, after the annotated-frame subscription block, add:

```python
        # Health metrics bridge.
        import json as _json
        from orchestrator.web_server.health_bus import health_bus
        self._health_bus = health_bus
        self._health_json = _json

        self._health_sub = self.create_subscription(
            String, "/health/metrics", self._health_metrics_cb, 10
        )
        self._scan_cmd_pub = self.create_publisher(String, "/health/scan_cmd", 10)
        self.create_timer(0.2, self._drain_scan_cmd)
```

Then add the two methods:

```python
    def _health_metrics_cb(self, msg: String) -> None:
        try:
            self._health_bus.set_metrics(self._health_json.loads(msg.data or "{}"))
        except (ValueError, TypeError):
            pass

    def _drain_scan_cmd(self) -> None:
        cmd = self._health_bus.take_cmd()
        if not cmd:
            return
        out = String()
        out.data = self._health_json.dumps(cmd)
        self._scan_cmd_pub.publish(out)
```

- [ ] **Step 2: Byte-compile check**

Run: `cd src/orchestrator && python -m py_compile ros_node.py`
Expected: no output (success)

- [ ] **Step 3: Commit**

```bash
git add src/orchestrator/ros_node.py
git commit -m "feat: bridge /health/metrics and /health/scan_cmd in orchestrator ROS node"
```

---

### Task 16: On-device integration + FPS smoke test

**Files:**
- Create: `docs/superpowers/plans/health-metrics-smoke-test.md` (record procedure + results)

**Interfaces:** none (manual/on-device verification of Tasks 13–15).

This task gates the §5.1 face-detector decision from the spec: if the face detector regresses fall-detection pose FPS beyond budget, switch `HealthConfig.detector` handling to the pose-only fallback (already covered by `roi_from_pose`, Task 8) by feeding pose landmarks instead of the MediaPipe extractor.

- [ ] **Step 1: Run the full unit suite on the dev machine**

Run: `cd src/perception && python -m pytest tests/health -v && cd ../orchestrator && python -m pytest tests -v`
Expected: all PASS.

- [ ] **Step 2: Launch the stack on the Orange Pi**

```bash
bash ~/dorabot_ws/scripts/start_dorabot.sh
```

- [ ] **Step 3: Verify the metrics topic publishes**

In another SSH shell:

```bash
source /opt/ros/humble/setup.bash
ros2 topic echo /health/metrics --once
```

Expected: a JSON string with `schema_version: 1`, an `hr_bpm` (number or null), and `state: "idle"`.

- [ ] **Step 4: Measure fall-detection FPS with the feature off vs on**

Run the node with `print_fps` and health enabled, note "Detect FPS"; then set `HealthConfig.default()`'s `enabled=False` (temporary), restart, and compare.
Record both numbers in `health-metrics-smoke-test.md`.
Decision rule: if enabling health drops Detect FPS by more than ~15%, switch to the pose-fallback ROI path (feed `roi_from_pose` from the existing pose landmarks in `_sample_health_roi` instead of `FaceRoiExtractor`) and re-measure.

- [ ] **Step 5: End-to-end scan via HTTP**

```bash
curl -s -X POST localhost:8002/health/scan -H 'content-type: application/json' -d '{"window_s":30}'
# hold still ~30s in front of the camera, then:
curl -s localhost:8002/health/scan/status | python3 -m json.tool
```

Expected: `state` progresses `warming → collecting → complete`, `hr_bpm` populated with a plausible 50–100 bpm at rest, `scan.progress_clean_s` approaching 30.

- [ ] **Step 6: Record results and commit**

```bash
git add docs/superpowers/plans/health-metrics-smoke-test.md
git commit -m "docs: record on-device rPPG smoke test and FPS budget results"
```

---

### Task 17: Monitor UI — HR chip overlay + scan card

**Files:**
- Modify: `src/orchestrator/web_server/ui/index.html`

**Interfaces:**
- Consumes HTTP: `GET /health/live`, `POST /health/scan`, `GET /health/scan/status`.

No unit test (frontend); verified visually in Task 16 step 5 / browser.

- [ ] **Step 1: Add the HR chip, scan button, and card markup**

Inside the camera panel container in `index.html`, add an overlay chip and a card (place near the video element; match existing class naming):

```html
<div id="hr-chip" class="hr-chip" hidden>
  <span id="hr-value">--</span> BPM
  <span id="hr-dot" class="hr-dot"></span>
</div>

<div id="health-panel" class="health-panel">
  <button id="scan-btn" class="scan-btn">健康扫描 / Scan</button>
  <div id="scan-progress" class="scan-progress" hidden>
    测量中 Measuring… <span id="scan-pct">0</span>%
  </div>
  <div id="health-card" class="health-card" hidden>
    <div class="metric"><span>心率 Heart rate</span><b id="card-hr">--</b> BPM</div>
    <div class="metric"><span>面色 Complexion</span><b id="card-complexion">--</b></div>
    <div class="metric small" id="card-quality">--</div>
    <div class="disclaimer">仅供参考，非医疗设备 · For reference only, not a medical device</div>
  </div>
</div>
```

- [ ] **Step 2: Add styles**

In the `<style>` block, add:

```css
.hr-chip { position: absolute; top: 10px; right: 10px; background: rgba(0,0,0,.6);
  color: #fff; padding: 4px 10px; border-radius: 14px; font: 600 14px system-ui; }
.hr-dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%;
  background: #f33; margin-left: 6px; vertical-align: middle; }
.hr-dot.good { background: #3c3; } .hr-dot.mid { background: #fc3; }
.health-panel { margin-top: 10px; }
.scan-btn { padding: 8px 14px; border: 0; border-radius: 8px; background: #2b6; color: #fff;
  font: 600 14px system-ui; cursor: pointer; }
.health-card { margin-top: 10px; padding: 12px; border-radius: 10px; background: #111a;
  color: #eee; max-width: 320px; }
.health-card .metric { display: flex; justify-content: space-between; margin: 4px 0; }
.health-card .metric.small { font-size: 12px; opacity: .7; }
.health-card .disclaimer { margin-top: 8px; font-size: 11px; opacity: .6; }
```

- [ ] **Step 3: Add the polling + scan JS**

Before `</body>`, add:

```html
<script>
(function () {
  const chip = document.getElementById('hr-chip');
  const hrVal = document.getElementById('hr-value');
  const hrDot = document.getElementById('hr-dot');

  async function pollLive() {
    try {
      const m = await (await fetch('/health/live')).json();
      if (m && m.hr_bpm != null) {
        chip.hidden = false;
        hrVal.textContent = Math.round(m.hr_bpm);
        const c = m.hr_confidence || 0;
        hrDot.className = 'hr-dot ' + (c > 0.75 ? 'good' : c > 0.5 ? 'mid' : '');
      } else {
        chip.hidden = true;
      }
    } catch (e) { chip.hidden = true; }
  }
  setInterval(pollLive, 1000);

  const btn = document.getElementById('scan-btn');
  const prog = document.getElementById('scan-progress');
  const pct = document.getElementById('scan-pct');
  const card = document.getElementById('health-card');
  let scanTimer = null;

  btn.addEventListener('click', async () => {
    card.hidden = true; prog.hidden = false; pct.textContent = '0';
    await fetch('/health/scan', { method: 'POST', headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ window_s: 30 }) });
    if (scanTimer) clearInterval(scanTimer);
    scanTimer = setInterval(pollScan, 1000);
  });

  async function pollScan() {
    const m = await (await fetch('/health/scan/status')).json();
    const target = (m.scan && m.scan.target_s) || 30;
    const done = (m.scan && m.scan.progress_clean_s) || 0;
    pct.textContent = Math.min(100, Math.round((done / target) * 100));
    if (m.state === 'complete' || m.state === 'failed' || m.state === 'cancelled') {
      clearInterval(scanTimer); scanTimer = null; prog.hidden = true;
      if (m.state === 'complete') {
        document.getElementById('card-hr').textContent = m.hr_bpm != null ? Math.round(m.hr_bpm) : '--';
        document.getElementById('card-complexion').textContent =
          m.complexion ? (m.complexion.appearance_zh + ' / ' + m.complexion.appearance_en) : '--';
        document.getElementById('card-quality').textContent =
          '质量 quality: fps ' + (m.effective_fps || 0);
        card.hidden = false;
      } else {
        prog.hidden = false; prog.textContent = '测量失败，请重试 / Scan failed, try again';
      }
    }
  }
})();
</script>
```

- [ ] **Step 4: Verify in a browser**

Open `http://localhost:8002/` (or the configured port). Confirm the HR chip appears when a face is present and the scan button produces a result card. Record a screenshot in the smoke-test doc.

- [ ] **Step 5: Commit**

```bash
git add src/orchestrator/web_server/ui/index.html
git commit -m "feat: add HR overlay chip and health scan card to monitor UI"
```

---

### Task 18: Config plumbing + docs

**Files:**
- Modify: `src/perception/src/body_tracking/body_tracking_node.py` (accept optional health config dict)
- Modify: `README.md` (document the feature + non-medical disclaimer)

**Interfaces:**
- Consumes: `HealthConfig.from_dict` (Task 5).

- [ ] **Step 1: Allow env/config override of health settings**

In `body_tracking_node.py` `__init__`, replace `self.health_config = HealthConfig.default()` with:

```python
        import os as _os
        _health_enabled = _os.getenv("HEALTH_ENABLED", "1") != "0"
        self.health_config = HealthConfig.from_dict({
            "enabled": _health_enabled,
            "backend": _os.getenv("HEALTH_BACKEND", "pos"),
        })
```

- [ ] **Step 2: Document the feature**

In `README.md`, under the "Implemented today" area, add a short bullet:

```markdown
- **Camera health readout (rPPG):** live heart-rate estimate + on-demand 30s scan
  with a 面色/complexion appearance card. Non-medical, for reference only. Disable
  with `HEALTH_ENABLED=0`.
```

- [ ] **Step 3: Byte-compile + full test run**

Run: `cd src/perception && python -m py_compile src/body_tracking/body_tracking_node.py && python -m pytest tests/health -q`
Expected: compile clean; all tests pass.

- [ ] **Step 4: Commit**

```bash
git add src/perception/src/body_tracking/body_tracking_node.py README.md
git commit -m "feat: make health feature configurable and document it"
```

---

## Self-Review Notes

- **Spec coverage:** HR (Tasks 3,4,11), confidence (Task 4/11), quality gates (Task 6), scan control cross-process via topic (Tasks 9,13,14,15), versioned message with null unsupported metrics (Task 10), complexion appearance-only (Task 7), face ROI with detector + pose fallback (Tasks 8,12,16), non-blocking estimator on timer (Tasks 11,13), camera exposure/WB — surfaced as `exposure_stable` gate component (Task 6) with the lock itself deferred to the on-device step (Task 16, RealSense ownership verification per spec §14); RR/HRV/SpO2 `not_supported` (Task 10); tests incl. failure behavior (Tasks 3–11), on-device FPS smoke (Task 16); config toggle + docs (Task 18).
- **Deferred with intent (matches spec §9/§14):** the actual RealSense exposure/WB *lock* is validated on-device before enabling, because it depends on camera-capture ownership the spec flags as an open risk. The message/gate plumbing for it is in place now.
- **Custom ROS message:** spec §11 prefers a custom message; this plan uses versioned `std_msgs/String` JSON (matching the existing `fall_event` pattern and avoiding a rosidl build). `schema_version` makes a later migration clean. Noted as intentional.
