# Camera-Based Health Metrics (rPPG) — Design

**Date:** 2026-07-10
**Status:** Draft for review (revised after Codex review)
**Author:** Frank (with Claude)
**Target hardware:** Orange Pi 5, RK3588S, 8GB RAM, RealSense D415

---

## 1. Summary

Add a camera-based **wellness readout** to the Dorabot stack. Using the existing
RealSense RGB stream, estimate **heart rate** from facial video via **remote
photoplethysmography (rPPG)** — recovering the pulse signal from tiny color
changes in facial skin — plus a **playful complexion-appearance card**.

This is a **non-medical, "for reference / fun" feature**. It makes no clinical
claims. It reuses infrastructure that already exists (camera capture, the
perception node, the orchestrator web layer, the chatbot) rather than adding a
new sensing pipeline.

> **Revision note:** an earlier draft claimed face landmarks were already
> available and scoped HR + RR + HRV + SpO2 + a "vitality" score. A code-grounded
> review corrected several load-bearing assumptions (see §14). v1 is now scoped to
> **HR only** (with confidence + scan quality) plus a renamed **complexion
> appearance** card. RR, HRV, and SpO2 are moved to future work behind interface
> stubs — they are not honestly recoverable at a wellness bar from this hardware
> without validation.

## 2. Goals & Non-Goals

### Goals
- Show an **ambient live heart-rate** estimate (with a confidence indicator) as an
  overlay on the monitor UI.
- Offer an **on-demand ~30s "health scan"** that returns HR, confidence, and a
  scan-quality summary, plus the complexion card.
- Produce a friendly **面色 / complexion-appearance** reading — a fun visual
  description, explicitly separated from anything health-related.
- Run comfortably on the 8GB Orange Pi **without degrading fall-detection frame
  rate** and without blocking the perception image callback.
- Require **no training data** for v1.
- Keep the estimator behind an interface so a deep-learning backend can be added
  later without re-architecting.

### Non-Goals
- No clinical-grade accuracy, no medical device claims.
- No dataset collection or model training in v1.
- No deep-learning / NPU inference in v1 (design allows it later).
- **No RR, HRV, or SpO2 shown in v1** (interface stubs only; see §7).

## 3. Metrics in Scope

| Metric | v1 status | Honesty note |
|---|---|---|
| Heart rate (BPM) | **Shown** (ambient + scan) | Reliable only when face is still, well-lit, close, and camera exposure/WB are stable. Always paired with a confidence value. |
| Scan quality | **Shown** (scan) | Summary of the gates in §8 so the user understands *why* a reading is trusted or withheld. |
| 面色 / complexion appearance | **Shown** (scan), fun-only | Renamed from 气色. Described as a **visual appearance** read, never mapped to health/vitality. See §7.3. |
| Respiratory rate | **Not in v1** — stub only | Pulse-amplitude RR over 30s is fragile. If added later, derive from pose/depth chest motion, labeled experimental. |
| HRV (SDNN) | **Not in v1** — stub only | SDNN needs reliable beat-to-beat intervals; face-camera peaks over 30s are too noisy to be honest. Requires pulse-ox/ECG validation first. |
| SpO2 | **Not in v1** — documented "not supported" | RGB ratio-of-ratios without controlled illumination + calibration is unreliable. Interface stub + docs only; no hidden implementation that could leak into demos. |

## 4. Approach Decision (Estimator)

**Chosen: port the classical POS algorithm (Wang et al., 2017), with CHROM as a
fallback**, implemented directly in numpy/scipy.

Rationale:
- Zero training data, zero PyTorch, zero RKNN conversion.
- Cheap: per-frame work is averaging a small ROI; window processing (band-pass +
  spectral estimate) runs on a timer, not in the image callback (§5).
- POS is the standard unsupervised baseline and the natural thing to validate a
  deep model against later.

POS/CHROM is an **HR baseline only** — it does not make RR/HRV/SpO2 trustworthy.

### Required operating conditions (must be checked, not assumed)

rPPG only works inside a bounded envelope. The estimator must measure and gate on:
face pixel width, ROI pixel area, effective (post-skip) frame rate, inter-frame
timestamp jitter, camera exposure/white-balance stability, and head motion. See
§8 for the concrete gates and §9 for camera-setting handling.

### Extensibility interface

```
class RPPGBackend(Protocol):
    def estimate(self, rgb_window: np.ndarray, ts: np.ndarray) -> PulseEstimate: ...
    #   PulseEstimate: hr_bpm | None, confidence 0..1, spectral_snr, peak_dominance

class POSBackend(RPPGBackend): ...      # v1 default
class CHROMBackend(RPPGBackend): ...    # v1 fallback
# class DeepBackend(RPPGBackend): ...   # future: RKNN/torch, drop-in
```

Backend is selected by config; the rest of the pipeline is backend-agnostic. RR,
HRV, and SpO2 exist as interface stubs that return `not_supported` in v1.

## 5. Architecture & Placement

**ROI color sampling lives in the perception node** (near the frames), but **all
window processing and scan state live in a separate, non-blocking estimator** —
not in the hot image callback, which already runs YOLO detection, MediaPipe pose,
annotation, and fall-state publishing, and supports frame skipping.

### 5.1 Face ROI (the corrected assumption)

The current node produces **MediaPipe Pose** landmarks from a YOLO person crop —
i.e. nose/eyes/ears only, **not** a FaceMesh. A forehead/cheek ROI derived purely
from those points is crude and degrades with head rotation, distance, and
occlusion. v1 therefore adds a **lightweight face detector** (MediaPipe Face
Detection, CPU, cheap) to get a stable face box + keypoints, from which we derive
forehead + cheek patches. This is a real added component, not "reuse what's there."

*Fallback if the face detector proves too costly alongside pose:* reuse the pose
nose/eye points for a coarse central-face ROI and rely harder on the §8 quality
gates to reject bad frames. Decided during implementation via the on-device FPS
smoke test (§11).

### 5.2 Frame policy (interaction with `process_every_n`)

The node skips detection on some frames (`process_every_n`) and republishes the
prior annotation. rPPG needs both a *fresh ROI* and a *high, even sample rate*:

- **On pose/detection frames:** update the face ROI (box + patches).
- **Between them (every camera frame):** reuse/track the last ROI and sample its
  mean RGB into the ring buffer, timestamped with the real frame time.
- The estimator records **effective FPS** and **dropped-frame ratio**; if the
  sample rate or ROI freshness falls below §8 thresholds, readings are withheld.

### 5.3 Process/threading model

```
perception body_tracking node (existing process)
  image callback (hot path, unchanged budget):
     └─ ROISampler.sample(frame, roi) → append (t, meanRGB) to ring buffer   [O(ROI) only]
  wall-clock timer (~1 Hz, separate callback):
     └─ RPPGEstimator.step(buffer window) → PulseEstimate → publish /health/metrics
  ScanController (state machine, driven by the scan service):
     └─ accumulates clean accepted seconds, publishes scan states + result
```

The estimator and scan state are plain, unit-testable objects; ROS is only the
transport. Nothing heavy runs inside the image callback.

### 5.4 Downstream (mirrors existing patterns)

```
orchestrator ──subscribe /health/metrics──► HealthBus (latest snapshot, like frame_bus)
   ├─ GET  /health/live          → ambient overlay (HR + confidence)
   └─ (scan control via ROS service below, surfaced as HTTP)

UI (index.html)
   ├─ HR chip overlaid on the video (HR + confidence dot; hidden when quality low)
   └─ "健康扫描 / Scan" button → progress (clean accepted seconds) → result card

chatbot
   └─ voice intent ("测一下我的心率") → orchestrator → scan service
```

## 6. Signal Pipeline (per estimator)

1. **ROI selection** — forehead + cheek patches from the face detector (§5.1).
2. **Signal accumulation** — spatial-mean RGB of the ROI per camera frame into a
   timestamped ring buffer (real, non-uniform intervals; resampled before FFT).
3. **Pulse extraction** — POS (fallback CHROM) over a sliding ~10s window
   (ambient) or the accumulated clean window (scan): detrend → normalize →
   project → band-pass 0.7–4 Hz → combine.
4. **HR derivation** — resample to uniform grid → Welch/zero-padded PSD for
   adequate frequency resolution → dominant peak in 0.7–4 Hz (42–240 BPM) with:
   - **confidence** from spectral SNR + peak dominance,
   - **temporal hysteresis / peak tracking** across windows (no jumpy values),
   - a **refractory / plausibility limit** on beat-to-beat change,
   - an explicit **"no value"** state when confidence is below threshold.
5. **Quality gating** — see §8. The ambient overlay shows HR + confidence only
   when gates pass; the scan card only finalizes after enough *clean accepted
   seconds* (not wall-clock seconds).

RR / HRV / SpO2 derivations are **not implemented** in v1 (stubs return
`not_supported`).

## 7. Non-HR Features

### 7.1 Respiratory rate — deferred
Not in v1. If added, prefer pose/depth **chest-motion** estimation over
pulse-amplitude modulation, and label it experimental.

### 7.2 HRV — deferred
Not in v1. Requires reliable beat-to-beat intervals validated against a
pulse-ox/ECG reference before it can be shown. Stub only.

### 7.3 面色 / complexion appearance — fun, non-health
- Renamed from 气色. Presented as a **visual appearance** description, in its own
  card, visually and textually separated from the HR/health area.
- Computed from ROI mean color, brightness, and evenness, mapped to neutral,
  appearance-only phrases (e.g. 面色红润 / 面色偏白 / 光泽均匀) **without** any
  health, vitality, or diagnostic labels, and without a "score out of 100."
- Card carries an explicit caveat: results depend heavily on lighting, camera
  white balance, and makeup, and are **not** a health indicator. This avoids the
  skin-tone-bias and color-grading pitfalls of treating it as a metric.

### 7.4 SpO2 — not supported in v1
No implementation, hidden or otherwise. Interface stub returns `not_supported`
and documentation states RGB SpO2 needs controlled illumination + per-device
calibration we do not have. This prevents a hidden path from surfacing in demos.

## 8. Quality Gating (concrete)

A reading is shown only when **all** hard gates pass; confidence is a graded
score used for the overlay dot and to accept "clean seconds" during a scan.

**Hard gates (any failure → withhold / not an accepted second):**
- face present and **exactly one** target in frame
- ROI fully in-bounds, ROI area ≥ `min_roi_px`, face width ≥ `min_face_px`
- effective FPS ≥ `min_fps`, dropped-frame ratio ≤ `max_drop_ratio`
- inter-frame timestamp jitter ≤ `max_jitter`
- head motion (landmark displacement / optical-flow proxy) ≤ `max_motion`
- illumination delta between consecutive frames ≤ `max_illum_delta`
- camera exposure/WB stable over the window (§9)

**Graded confidence (0..1):** spectral SNR, peak dominance, and peak stability
across sub-windows. Below `min_confidence` → "no value" / "measuring…".

**Scan progress** = accumulated clean accepted seconds ÷ `scan_window_s`, **not**
elapsed wall-clock time.

## 9. Camera Exposure / White-Balance Handling

The RealSense RGB auto-exposure and auto-white-balance can **create or erase** the
pulse color signal, which is the single biggest signal-integrity risk.

- **During a scan:** attempt to **lock exposure, gain, and white balance** on the
  RealSense RGB sensor for the scan duration, then restore prior settings.
- If locking is unavailable/undesired: **monitor** reported exposure/WB/gain and
  treat any change during the window as a hard-gate failure (§8), flagged in the
  scan-quality summary.
- Document that the annotated MJPEG stream is unaffected (locking applies to the
  capture used for rPPG sampling; the shared camera implication is called out as
  an implementation risk to verify — see §12).

## 10. Scan Control (cross-process)

Perception and orchestrator are **separate processes** — a shared in-memory flag
is impossible. Scan control is a **ROS service (or action)** exposed by the
perception node and called by the orchestrator:

- **Request:** `measurement_id`, `window_s`, optional `lock_camera` flag.
- **Operations:** start, **cancel**, and a **timeout**.
- **States published** (on `/health/metrics` and/or the service result):
  `idle → warming → collecting → insufficient_quality → complete | failed | cancelled`.
- `collecting` progress reports **clean accepted seconds**; `insufficient_quality`
  is entered (with a `reason`) when gates keep failing past a grace period.

The orchestrator surfaces this as HTTP for the UI/chatbot:
`POST /health/scan` (→ start, returns `measurement_id`), `GET /health/scan/status`
(→ state + progress + result), `POST /health/scan/cancel`.

## 11. Data Contract

**Versioned message.** Prefer a small **custom ROS message**; if `std_msgs/String`
JSON is used as an interim, it must carry the same fields and a `schema_version`.

```json
{
  "schema_version": 1,
  "ts": 1751000000.0,
  "measurement_id": "uuid-or-null",   // null for ambient
  "mode": "ambient",                   // "ambient" | "scan"
  "state": "collecting",               // idle|warming|collecting|insufficient_quality|complete|failed|cancelled
  "reason": null,                      // populated on insufficient_quality/failed
  "effective_fps": 26.4,
  "window_s": 10.0,
  "hr_bpm": 72.4,                      // nullable
  "hr_confidence": 0.81,               // 0..1, nullable
  "quality_components": {
    "spectral_snr": 6.2, "peak_dominance": 0.7, "face_px": 180,
    "roi_px": 5400, "drop_ratio": 0.03, "motion": 0.02, "exposure_stable": true
  },
  "complexion": { "appearance_zh": "面色红润", "appearance_en": "rosy appearance",
                  "caveat": "lighting/WB dependent, not a health indicator" },
  "resp_bpm": null,                    // not_supported in v1
  "hrv_sdnn_ms": null,                 // not_supported in v1
  "spo2_pct": null,                    // not_supported in v1
  "scan": { "progress_clean_s": 4.0, "target_s": 30.0 }
}
```

Fields for unsupported metrics are always `null` and documented as
`not_supported` in v1, not "coming soon in the UI."

## 12. Configuration

```yaml
health:
  enabled: true
  backend: pos                 # pos | chrom | (future) deep
  face_roi:
    detector: mediapipe_face   # mediapipe_face | pose_fallback
  ambient_window_s: 10
  scan_window_s: 30            # target CLEAN seconds
  scan_timeout_s: 90          # wall-clock guard
  gates:
    min_fps: 15
    max_drop_ratio: 0.2
    min_face_px: 120
    min_roi_px: 3000
    max_jitter_ms: 20
    max_motion: 0.05
    max_illum_delta: 0.15
    min_confidence: 0.5
  camera:
    lock_on_scan: true         # lock exposure/gain/WB during scan
  complexion:
    enabled: true              # fun, appearance-only
```

## 13. Testing Strategy

- **Unit (no ROS, no camera):** synthetic RGB windows with an injected sinusoid →
  assert POS/CHROM recover HR within tolerance; assert PSD/peak-tracking,
  hysteresis, confidence scoring, and all §8 gate predicates on fixed inputs.
  *(Note: synthetic tests prove the math plumbing, not real rPPG accuracy.)*
- **Recorded-clip regression (required for accuracy claims):** short face clips
  with a reference HR (finger pulse-ox captured alongside), including **failure
  cases**: head motion, poor/uneven lighting, exposure/WB drift, multiple people,
  face turned away, talking, and `process_every_n > 1`. Assert HR MAE within a
  documented tolerance on the good clips and correct **withhold** behavior on the
  bad ones. *(Reference clips TBD by Frank.)*
- **Scan state-machine tests:** start/cancel/timeout, clean-second accounting,
  transitions into `insufficient_quality` with a reason.
- **Integration:** stub `/health/metrics` + scan service → assert orchestrator
  `HealthBus`, `/health/live`, `/health/scan*` endpoints and the UI card.
- **On-device smoke (gating the §5.1 face-detector decision):** measure
  fall-detection pose FPS with the feature **off vs on**; if the face detector
  regresses FPS beyond budget, fall back to the pose-only coarse ROI.
- Target 80%+ coverage on the `health/` package (per project testing rules).

## 14. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Pose landmarks give a poor face ROI | Add MediaPipe Face Detection (§5.1); pose-only coarse ROI as gated fallback |
| Auto-exposure/WB creates or erases the signal | Lock exposure/gain/WB during scan, or gate on stability (§9) |
| Heavy work in the image callback drops fall-detection FPS | ROI sampling only in callback; estimation on a timer/thread (§5.3); on-device FPS smoke test |
| `process_every_n` starves the sample rate | Explicit frame policy: ROI on pose frames, color every camera frame (§5.2) |
| Cross-process scan trigger | ROS service/action with id, cancel, timeout, states (§10) |
| Noisy metrics shown as fact | v1 shows only HR + confidence; RR/HRV/SpO2 deferred; scan quality surfaced |
| Complexion read misused as health | Renamed, appearance-only, separated card, explicit caveat (§7.3) |
| Shared camera vs exposure lock | Verify RealSense capture ownership before enabling `lock_on_scan` (§9/§12) |

## 15. Out of Scope / Future Work

- RR (chest-motion based), HRV (validated), SpO2 (controlled illumination +
  calibration) — behind the existing interface stubs.
- Deep-learning backend (RKNN or torch) via `RPPGBackend`.
- Dataset collection + validation (UBFC-rPPG, PURE, VIPL-HR, SCAMPS).
- Trend logging / history of readings; feeding health signals into caregiving
  logic (a larger, separate effort — v1 is display-only).

## 16. References

- rPPG-Toolbox (ubicomplab, NeurIPS 2023): https://github.com/ubicomplab/rPPG-Toolbox
- open-rppg (real-time, JAX): https://github.com/KegangWangCCNU/open-rppg
- POS: Wang et al., "Algorithmic Principles of Remote PPG," IEEE TBME 2017.
- CHROM: de Haan & Jeanne, "Robust Pulse Rate From Chrominance-Based rPPG," 2013.
- Datasets: UBFC-rPPG, PURE, COHFACE, VIPL-HR, MAHNOB-HCI, SCAMPS (synthetic).
- Review that shaped this revision: Codex code-grounded review, 2026-07-10
  (face-ROI, cross-process trigger, exposure/WB, metric honesty).
