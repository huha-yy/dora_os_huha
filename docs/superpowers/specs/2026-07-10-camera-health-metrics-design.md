# Camera-Based Health Metrics (rPPG) — Design

**Date:** 2026-07-10
**Status:** Draft for review
**Author:** Frank (with Claude)
**Target hardware:** Orange Pi 5, RK3588S, 8GB RAM, RealSense D415

---

## 1. Summary

Add a camera-based **wellness readout** to the Dorabot stack. Using the existing
RealSense RGB stream and the face landmarks already produced by the perception
node, estimate a small set of health-flavored metrics via **remote
photoplethysmography (rPPG)** — recovering the pulse signal from tiny color
changes in facial skin.

This is a **non-medical, "for reference / fun" feature**. It makes no clinical
claims. It reuses infrastructure that already exists (camera capture, face
landmarks, the orchestrator web layer, the chatbot) rather than adding a new
sensing pipeline.

## 2. Goals & Non-Goals

### Goals
- Show an **ambient live heart-rate** estimate as an overlay on the monitor UI.
- Offer an **on-demand ~30s "health scan"** that returns a full metric card.
- Produce a friendly **气色 (qìsè / complexion-vitality)** reading in the spirit
  of Traditional Chinese Medicine — light-hearted, not diagnostic.
- Run comfortably on the 8GB Orange Pi **without touching the fall-detection
  NPU** or degrading the existing pose pipeline.
- Require **no training data** for v1.
- Keep the estimator behind an interface so a deep-learning backend can be added
  later without re-architecting.

### Non-Goals
- No clinical-grade accuracy, no medical device claims.
- No dataset collection or model training in v1.
- No deep-learning / NPU inference in v1 (design allows it later).
- SpO2 is **built but hidden** in v1 (see §7).

## 3. Metrics in Scope

| Metric | v1 status | Reliability from RGB | Notes |
|---|---|---|---|
| Heart rate (BPM) | **Shown** (ambient + scan) | Good when face is still | The anchor metric |
| Respiratory rate | Shown (scan) | Moderate | Derived from same signal |
| HRV (SDNN) | Shown (scan), labeled *approximate* | Noisy | Needs a clean 30s window |
| SpO2 | **Built, hidden** behind config flag | Poor / experimental | Off in UI until trusted |
| 气色 (qìsè) | Shown (scan) | Heuristic / playful | Complexion + luster + evenness → score + label |

## 4. Approach Decision (Estimator)

**Chosen: port the classical POS algorithm (Wang et al., 2017), with CHROM as a
fallback**, implemented directly in numpy/scipy.

Rationale:
- Zero training data, zero PyTorch, zero RKNN conversion.
- Sub-millisecond per-window cost; a few KB of buffers. Does not compete with
  YOLO (NPU) or MediaPipe pose (CPU).
- POS is the standard unsupervised baseline and the natural thing to validate a
  deep model against later.

Rejected for v1:
- **rPPG-Toolbox deep models (TS-CAN/PhysNet):** higher accuracy but require
  PyTorch runtime + RKNN conversion (temporal/attention layers map poorly) and
  would time-share the fall-detection NPU. Disproportionate to a wellness bar.
- **open-rppg (JAX):** JAX-on-ARM packaging friction.

Reference implementations to consult (not vendored wholesale):
- `ubicomplab/rPPG-Toolbox` — for POS/CHROM reference and future benchmarking.
- `KegangWangCCNU/open-rppg` — real-time streaming patterns.

### Extensibility interface

```
class RPPGBackend(Protocol):
    def estimate(self, rgb_window: np.ndarray, fps: float) -> PulseSignal: ...

class POSBackend(RPPGBackend): ...      # v1 default
class CHROMBackend(RPPGBackend): ...    # v1 fallback
# class DeepBackend(RPPGBackend): ...   # future: RKNN/torch, drop-in
```

Backend is selected by config; the rest of the pipeline is backend-agnostic.

## 5. Architecture & Placement

The perception `body_tracking` node already holds **both** the raw frame and the
face landmarks (nose, eyes, ears) each cycle. rPPG is computed **there**, in a
new self-contained `health/` package, to avoid a second image subscription and
frame copies.

```
RealSense ──raw Image──► perception (/body_tracking node)
   YOLO(NPU) + MediaPipe pose(CPU)  ── unchanged ──►
                     │  frame + face landmarks
                     └─► health.RPPGEstimator
                             ├─ ROI extraction (forehead + cheeks from landmarks)
                             ├─ rolling RGB signal buffer (ring)
                             ├─ POS/CHROM backend → pulse signal
                             ├─ metric derivation (HR, RR, HRV, SpO2*, 气色)
                             └─ publish /health/metrics (std_msgs/String JSON)
```

Downstream (mirrors the existing `fall_event` + `frame_bus` patterns):

```
orchestrator ──subscribe /health/metrics──► HealthBus (latest snapshot, like frame_bus)
   ├─ GET  /health/live          → ambient overlay (HR + confidence), polled ~1s
   ├─ POST /health/scan          → begin a 30s full scan
   └─ GET  /health/scan/status   → poll { running, progress, result_card }

UI (index.html)
   ├─ HR chip overlaid on the video stream
   └─ "健康扫描 / Scan" button → progress → 5-metric result card + disclaimer

chatbot
   └─ voice intent ("测一下我的心率" / "check my heart rate") → POST /health/scan
```

The scan is a **mode signal**: the orchestrator's scan request is relayed to the
perception estimator (via a small command topic or a shared flag), which
accumulates a clean 30s window and publishes a `scan_complete` result.

## 6. Signal Pipeline (per estimator)

1. **ROI selection** — derive forehead + both-cheek patches from existing pose
   landmarks (eyes/nose/ears). No FaceMesh needed for v1; revisit if ROI proves
   too coarse.
2. **Signal accumulation** — spatial-mean RGB of the ROI per frame into a ring
   buffer (timestamped for real, non-constant frame intervals).
3. **Pulse extraction** — POS (fallback CHROM) over a sliding ~10s window
   (ambient) or the full 30s window (scan): detrend → normalize → project →
   band-pass 0.7–4 Hz → combine.
4. **Metric derivation:**
   - **HR** — dominant FFT peak in 0.7–4 Hz (42–240 BPM).
   - **Respiratory rate** — 0.1–0.4 Hz band + amplitude modulation of the pulse.
   - **HRV (SDNN)** — peak-to-peak intervals over the 30s window; *approximate*.
   - **SpO2 (hidden)** — ratio-of-ratios on red/blue AC/DC with a per-device
     calibration constant; config-gated, off by default.
   - **气色 (qìsè)** — from ROI: mean skin tone, luster (brightness), evenness
     (color variance) → 0–100 vitality score + label (红润 / 正常 / 偏白 / 暗沉).
     Purely heuristic.
5. **Quality gating** — a signal-quality (SNR) + face-stillness score decides
   whether numbers are shown or a `测量中… / Measuring…` state is shown. Ambient
   overlay shows HR + a confidence dot only when quality passes; the full card
   only appears after a clean 30s window.

## 7. SpO2 Handling (built-but-hidden)

- Implemented behind `health.spo2.enabled` config flag, **default false**.
- Never shown in the ambient overlay.
- When enabled, appears in the scan card tagged **实验性 / experimental** with the
  non-medical disclaimer.
- Requires a per-device calibration constant; documented as unvalidated.

## 8. UI / UX

- **Ambient:** small HR chip over the live MJPEG feed (`♥ 72 · ●` confidence),
  hidden when quality is poor.
- **Scan:** button (and voice) → 30s countdown with a "hold still / 请保持不动"
  hint → result card with HR, RR, HRV (approx), 气色 score+label, and SpO2 only
  if enabled.
- **Disclaimer:** persistent "仅供参考，非医疗设备 / For reference only, not a
  medical device" on the card.
- Bilingual labels (zh + en), consistent with the existing UI.

## 9. Data Contracts

`/health/metrics` (String, JSON), published ~1 Hz ambient and on scan completion:

```json
{
  "ts": 1751000000.0,
  "mode": "ambient",            // "ambient" | "scan"
  "quality": 0.82,              // 0..1 signal quality
  "face_present": true,
  "hr_bpm": 72.4,
  "resp_bpm": 15.1,             // scan only
  "hrv_sdnn_ms": 48.0,          // scan only, approximate
  "spo2_pct": null,             // null unless config-enabled
  "qise": { "score": 78, "label": "红润", "label_en": "rosy" },
  "scan": { "running": false, "progress": 1.0 }
}
```

## 10. Configuration

```yaml
health:
  enabled: true
  backend: pos                 # pos | chrom | (future) deep
  ambient_window_s: 10
  scan_window_s: 30
  min_quality: 0.5
  spo2:
    enabled: false             # built-but-hidden
    calibration: { a: 0.0, b: 0.0 }
  qise:
    enabled: true
```

## 11. Testing Strategy

- **Unit (no ROS, no camera):** feed synthetic RGB windows with a known injected
  sinusoid → assert POS/CHROM recover the correct HR within tolerance; assert
  band-pass, FFT-peak, HRV, and 气色 mapping on fixed inputs. Golden-signal
  fixtures.
- **Recorded-video regression:** run the estimator over a short recorded clip
  with a reference HR (e.g. a finger pulse-ox reading captured alongside) and
  assert MAE within a documented tolerance. (Reference clip TBD by Frank.)
- **Integration:** stub `/health/metrics` publisher → assert orchestrator
  `HealthBus`, `/health/live`, `/health/scan` endpoints behave.
- **On-device smoke:** confirm no fall-detection frame-rate regression with the
  estimator enabled (measure pose FPS before/after).
- Target 80%+ coverage on the `health/` package (per project testing rules).

## 12. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Motion / lighting corrupt the signal | Quality gating; "hold still" prompt; hide numbers when SNR low |
| Coarse pose landmarks give a poor ROI | Start with forehead+cheek patches; escalate to FaceMesh only if needed |
| SpO2 looks broken / misleads | Hidden by default, experimental tag, disclaimer |
| Users treat it as medical | Persistent non-medical disclaimer; playful framing for 气色 |
| Frame-rate regression on the Pi | On-device smoke test; estimator is cheap and skippable per-frame |

## 13. Out of Scope / Future Work

- Deep-learning backend (RKNN or torch) via the `RPPGBackend` interface.
- Dataset collection + validation (UBFC-rPPG, PURE, VIPL-HR, SCAMPS) if accuracy
  needs to improve.
- Trend logging / history of readings over time.
- Feeding health signals into fall-detection / caregiving logic (a larger,
  separate effort — this v1 is display-only).

## 14. References

- rPPG-Toolbox (ubicomplab, NeurIPS 2023): https://github.com/ubicomplab/rPPG-Toolbox
- open-rppg (real-time, JAX): https://github.com/KegangWangCCNU/open-rppg
- POS: Wang et al., "Algorithmic Principles of Remote PPG," IEEE TBME 2017.
- CHROM: de Haan & Jeanne, "Robust Pulse Rate From Chrominance-Based rPPG," 2013.
- Datasets: UBFC-rPPG, PURE, COHFACE, VIPL-HR, MAHNOB-HCI, SCAMPS (synthetic).
- SpO2 feasibility (experimental): CL-SPO2Net (MDPI Bioengineering 2024);
  "Camera Measurement of Blood Oxygen Saturation," arXiv:2503.01699.
