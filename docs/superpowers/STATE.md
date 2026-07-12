# STATE.md — where the project is right now

> Read this first, then reconcile it against `git log --oneline -20`.
> Commits are ground truth; this file is a derived view that can go stale.

**Branch:** `feat/camera-health-metrics`
**Last updated:** 2026-07-12

---

## Active plan

**P1 — Camera-based health metrics (rPPG heart rate)**

- Spec: `docs/superpowers/specs/2026-07-10-camera-health-metrics-design.md`
- Plan: `docs/superpowers/plans/2026-07-10-camera-health-metrics.md` (18 tasks + 15b)

Adds a non-medical camera heart-rate readout (classical POS/CHROM rPPG, no
training data, CPU-only) plus an appearance-only complexion card, shown as a
live overlay and an on-demand 30s scan in the monitor UI.

---

## Position

**Tasks 1–15 are committed. Task 15b (new) is next — see below.**

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
| 10 | Versioned message builder | done | `258c42f`, fixed `d8a1db3..9d234ed` |
| 11 | Estimator (buffer → PulseEstimate) | done | `f4eae9a` |
| 12 | MediaPipe face-ROI extractor + exports | done | `dcd8c3c` |
| 13 | Wire health pipeline into perception node | done | `048a901`, fixed `e6c01bd` |
| 14 | Orchestrator HealthBus + HTTP router | done | `617393c` |
| 15 | Orchestrator ROS bridge | done | `ce53f86` |
| **15b** | **Real motion + illumination gates** | **NEXT** | |
| 16 | On-device integration + FPS smoke test | blocked — needs the Orange Pi | |
| 17 | Monitor UI (HR chip + scan card) | not started | |
| 18 | Config plumbing + docs | not started | |

Test suite currently: **87 passing** (`tests/health`).

---

## Next step — Task 15b: make the motion and illumination gates real

**Why this exists.** Codex raised this as a **[P1]** on Task 13 and again on
`e6c01bd`. The Coder overrode it (`.review/manual-review-task13.txt`) on the
grounds that "the plan's Task 13 reference code uses these same pass values."
That is not a valid reason — the plan's reference code has been wrong three
times already (see "Plan corrections" below), which is why the review gate
exists. The human adjudicated on 2026-07-12: **implement the gates now.**

**The defect.** `body_tracking_node.py:440-442` hard-codes three of the eight
quality-gate components to always-pass values:

```python
"motion": 0.0,          # gate max_motion=0.05      → can never fail
"illum_delta": 0.0,     # gate max_illum_delta=0.15 → can never fail
"exposure_stable": True,
```

Head motion is the single largest source of rPPG artifacts: movement aliases
directly into the 0.7–4 Hz pulse band, so a moving subject does not produce *no*
reading — it produces a **confident wrong** one. The motion gate is the primary
defence against exactly the failure mode AGENTS.md §5 says to avoid above all.
With it stubbed open, the gate is decorative.

Note `evaluate_gates()` already fails closed on a *missing* key (`motion`
defaults to `1e9`). The node is actively supplying pass values to override that.

**Scope: motion and illum_delta only.** `exposure_stable` genuinely needs the
RealSense (locking exposure/WB), which is Task 16 on-device work. It stays
`True` for now — defensible because `illum_delta` measures the observable
*consequence* of exposure instability (luminance drift from auto-exposure
hunting), so it is no longer the only thing standing between us and a bad
reading. **This is a known, tracked gap — close it in Task 16.**

**Ordering.** 15b comes before Task 16. Running the on-device smoke test with
the motion gate stubbed open would validate a system whose main safety gate does
nothing — the test could not tell a good reading from a motion artifact.

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
   it now returns `tuple | None` (`None` = sampling failed).

3. **`ScanController` (Task 9).** `dt` was uncapped, so `start(now=0)` plus a
   single `update(now=25, gate_ok=True)` credited **25 clean seconds** and
   completed a scan off ONE good frame. Now clamped via `max_dt_s=2.0`.

**Lesson for the Coder — this has now bitten us four times.** The plan's code is
a starting point, not gospel. If a reviewer and the plan disagree, the plan is
the more likely of the two to be wrong. **Do not dismiss a reviewer finding by
citing the plan.** Escalate to the human instead (AGENTS.md §6).

---

## Deferred minor findings (triage before merge)

- **T13:** the node reaches into `self._rppg._buffer` (a private attribute) to
  recompute the window for the drop/jitter gates. Give `RppgEstimator` a public
  accessor.
- T1: `test_rgb_sample_is_immutable_*` never asserts `FrozenInstanceError`;
  `test_gate_result_defaults` never exercises the `default_factory` default.
- T2: `effective_fps`'s `span <= 0` guard is dead code now that `append()`
  enforces strict monotonicity; its test doesn't actually reach it.
- T4: `alpha = std(a)/(std(b)+1e-8)` can blow up when `std(b)` is tiny-but-nonzero;
  no cross-check that `ts.size == rgb.shape[0]`.
- T5: `HealthConfig.from_dict` silently drops unknown keys (a typo like `min_fp`
  quietly uses the default — bad for safety-relevant gate tuning). No value
  validation (backend isn't restricted to pos/chrom; negative windows accepted).
- **Process:** the Coder did not update STATE.md after each task as instructed
  (tasks 11–15 landed with STATE.md untouched). Reconciled manually on 2026-07-12.
