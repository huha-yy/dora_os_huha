# STATE.md — where the project is right now

> Read this first, then reconcile it against `git log --oneline -15`.
> Commits are ground truth; this file is a derived view that can go stale.

**Branch:** `feat/camera-health-metrics`
**Last updated:** 2026-07-11

---

## Active plan

**P1 — Camera-based health metrics (rPPG heart rate)**

- Spec: `docs/superpowers/specs/2026-07-10-camera-health-metrics-design.md`
- Plan: `docs/superpowers/plans/2026-07-10-camera-health-metrics.md` (18 tasks)

Adds a non-medical camera heart-rate readout (classical POS/CHROM rPPG, no
training data, CPU-only) plus an appearance-only complexion card, shown as a
live overlay and an on-demand 30s scan in the monitor UI.

---

## Position

**Tasks 1–10 are committed. Task 10 has an unapplied review fix — start there.**

| # | Task | Status | Commits |
|---|------|--------|---------|
| 1 | Test scaffolding + core types | done | `490e697` |
| 2 | RGB ring buffer | done | `87ca115..e961870` |
| 3 | Signal utils (resample/bandpass/HR-FFT) | done | `ff545d6..905b12b` |
| 4 | POS/CHROM backends | done | `fbfba84..8ff4e62` |
| 5 | HealthConfig + Gates | done | `c203ec0` |
| 6 | Quality gates | done | `cea19e1..1a686f9` |
| 7 | Complexion (面色) appearance | done | `c8a055c..57c87cc` |
| 8 | Face ROI + mean-RGB sampling | done | `01cb950..7b7d6ed` |
| 9 | Scan state machine | done | `6aeab9a..74ea4a4` |
| 10 | Versioned message builder | **committed, FIX PENDING** | `258c42f` |
| 11 | Estimator (buffer → PulseEstimate) | not started | |
| 12 | MediaPipe face-ROI extractor + exports | not started | |
| 13 | Wire health pipeline into perception node | not started | |
| 14 | Orchestrator HealthBus + HTTP router | not started | |
| 15 | Orchestrator ROS bridge | not started | |
| 16 | On-device integration + FPS smoke test | not started | |
| 17 | Monitor UI (HR chip + scan card) | not started | |
| 18 | Config plumbing + docs | not started | |

Test suite currently: **78 passing** (`tests/health`).

---

## Next step — Task 10 review fix (do this first)

A review of Task 10 found a **latent runtime crash** that was never fixed (the
fixing agent was killed by a quota limit). `build_metrics()` embeds
`quality_components` and `complexion` by reference with no coercion. The
perception node builds `quality_components` **by hand** from OpenCV/pose values,
which yields numpy scalars. Probed facts:

- `np.float64` DOES survive `json.dumps` (it subclasses `float`).
- `np.int64`, `np.float32`, `np.bool_` do **NOT** — `json.dumps` raises
  `TypeError: Object of type int64 is not JSON serializable`.

So an `np.int64` pixel count (`roi_px`/`face_px`), an `np.float32` motion delta,
or an `np.bool_` `exposure_stable` flag will **crash the perception node at
publish time** — the same node that runs safety-critical fall detection.

**Fix in `src/perception/src/body_tracking/health/messages.py`:**

1. Coerce numpy scalars to native Python (`int`/`float`/`bool`) recursively for
   `quality_components`, `complexion`, and the numeric fields. Use `.item()` /
   `isinstance(v, np.generic)`. Leave `None` as `None`. Do **not** silently drop
   unknown types — let `json.dumps` fail loudly rather than hiding a bug.
   This also gives the defensive copy the module currently lacks.
2. Add a test passing `np.int64`/`np.float32`/`np.bool_` inside
   `quality_components` and asserting `json.dumps(build_metrics(...))` succeeds.
   **Negative-control it:** confirm the test fails against the un-coerced code.
3. Add the missing test for `estimate is not None` **but** `estimate.hr_bpm is
   None` — both `hr_bpm` and `hr_confidence` must be `None`, never `0`.
4. Add a test pinning the exact message key set.

Do not change: the always-null `resp_bpm`/`hrv_sdnn_ms`/`spo2_pct`, the
`is not None` checks (a legitimate `0.0` must not collapse to null),
`schema_version = 1`, or the public signature.

After that, continue with Task 11.

---

## Plan corrections already applied (do not re-introduce)

The review loop caught three **blocking bugs in the plan's own reference code**.
The plan doc has been corrected, but if you read an older copy, beware:

1. **`peak_dominance` (Task 3).** Originally `peak_bin / total_in_band` — which
   is zero-padding dependent (0.46/0.29/0.15/0.07 at n_fft 1x/2x/4x/8x) and
   scored only 0.146 for a *perfect* sine. Since `confidence = 0.5*snr_term +
   0.5*dominance` and the gate needs `confidence >= 0.5`, the feature would have
   almost never shown a reading. Now: share of in-band power within ±0.2 Hz of
   the peak (`PEAK_NEIGHBOURHOOD_HZ`). Clean sine → 0.9999, noise → 0.27.

2. **`sample_mean_rgb` (Task 8).** Checked upper bounds but not `x < 0`/`y < 0`,
   so a negative-origin patch became a **negative numpy slice that wrapped around
   and sampled pixels from the opposite edge of the frame** — silently. Fixed;
   it now returns `tuple | None` (`None` = sampling failed), so Task 13 must not
   append a sample when it gets `None`.

3. **`ScanController` (Task 9).** `dt` was uncapped, so `start(now=0)` plus a
   single `update(now=25, gate_ok=True)` credited **25 clean seconds** and
   completed a scan off ONE good frame — defeating the entire clean-second safety
   design. Now clamped via `max_dt_s=2.0` (the node drives `update()` from a 1 Hz
   timer). Backwards `now` is ignored rather than rewinding the baseline.

**Lesson for the Coder:** the plan's code is a starting point, not gospel. If a
test fails, consider that the *plan* may be wrong before weakening the assertion.
Never commit a red test.

---

## Deferred minor findings (triage before merge)

- T1: `test_rgb_sample_is_immutable_*` never asserts `FrozenInstanceError`;
  `test_gate_result_defaults` never exercises the `default_factory` default.
- T2: `effective_fps`'s `span <= 0` guard is dead code now that `append()`
  enforces strict monotonicity; its test doesn't actually reach it.
- T4: `alpha = std(a)/(std(b)+1e-8)` can blow up when `std(b)` is tiny-but-nonzero;
  no cross-check that `ts.size == rgb.shape[0]`.
- T5: `HealthConfig.from_dict` silently drops unknown keys (a typo like `min_fp`
  quietly uses the default — bad for safety-relevant gate tuning). No value
  validation (backend isn't restricted to pos/chrom; negative windows accepted).
