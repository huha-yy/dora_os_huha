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
| 15b | Real motion + illumination gates | done | `c58c0de` |
| 16a | Real-face webcam validation | harness ready — **needs a human to run it** | |
| 16b | On-device FPS budget + e2e | deferred — needs the Orange Pi | |
| 17 | Monitor UI (HR chip + scan card) | done | `c65ce77`, fixed below |
| 18 | Config plumbing + docs | done | `c65ce77` |

Test suite currently: **111 passing** (`tests/`).

**The code is written, but v1 is NOT validated.** Tasks 16a and 16b both remain,
and they are the only things that have ever pointed this pipeline at a real human.
Until 16a passes, "done" means "the tests we wrote pass against the sine waves we
generated" — it does not mean the feature reads a heart rate.

**Do not push to `main`.** Work stays on `feat/camera-health-metrics` and merges
via PR (AGENTS.md §5: never commit directly to main).

---

## Task 15b — DONE (2026-07-12)

Codex raised a **[P1]** on Task 13 and again on `e6c01bd`: the node hard-coded
`motion=0.0`, `illum_delta=0.0`, `exposure_stable=True`, so three of the eight
quality gates could never fail. The Coder overrode it by citing the plan. The
human adjudicated: implement them. Done.

`health/artifacts.py` now computes both over the analysis window:

- `motion` = `sqrt(var(cx) + var(cy)) / mean(face_width)` — centroid dispersion in
  face widths, so it is scale- and distance-invariant.
- `illum_delta` = `std(luminance) / mean(luminance)` — a coefficient of variation.
  Relative, not absolute: the pulse *is* a 0.1–1% luminance modulation, and an
  absolute threshold would gate out the signal we are trying to measure.

Both fail **closed** (`FAIL_CLOSED = 1e9`) on any degenerate input — too few
samples, missing ROI geometry, non-finite values, black ROI. `0.0` would *pass*
the gate, which was the whole defect.

The node now populates `cx`/`cy`/`w` on every `RgbSample` (via the new
`roi_centroid()`), and the deferred **T13** finding is fixed — it uses the new
public `RPPGEstimator.window()` instead of reaching into `_buffer`.

### The gate alone was not enough — hysteresis contamination

Codex caught a second **[P1]** on the first attempt at this fix, and it was right.
`RPPGEstimator.estimate()` is **stateful**: `_last_hr` anchors the ±12 bpm
hysteresis clamp. The node called it *before* evaluating the gates, so a
motion-corrupted window was rejected for publication but **still committed
`_last_hr`** — and the next *accepted* reading was then clamped toward the
artifact. Demonstrated: a rejected 150 bpm window followed by a clean 72 bpm one
published **118**. The gate rejected the bad window and leaked it anyway.

Fixed by evaluating the gates first (every component derives from the sample
window alone, so nothing needed the estimate) and giving `estimate()` a
**required** `gate_ok` parameter — no default, so a caller cannot silently restore
the bug. A rejected window short-circuits and resets the hysteresis, leaving the
next clean reading free to be correct.

**Lesson: a quality gate is only as good as what it gates.** Rejecting a value at
the *publish* boundary is not enough when the estimator carries state across
windows.

### Known gap — `exposure_stable` is still hard-coded `True`

It needs the RealSense exposure/WB lock, which is **Task 16b** on-device work.
This is defensible for now only because `illum_delta` catches the observable
*symptom* of exposure hunting (luminance drift) — it is no longer the sole
defence. **Close it in Task 16b.** There is a `TODO(Task 16)` at the site.

---

## Task 16 is split — 16a can run today, 16b needs the robot

**The biggest untested assumption in this feature:** all 111 tests validate against
*synthetic sine waves we generated ourselves*. A pipeline can pass every one of
them and still recover nothing but noise from an actual human face. Nobody has
pointed this at a real person yet.

**Task 16a — `scripts/validate_rppg_webcam.py`.** Answers exactly that, on any dev
machine with a webcam. No ROS, no RealSense, no Pi. It drives the production path
(`FaceRoiExtractor` → `roi_centroid`/`sample_mean_rgb` → `RgbSample` →
`RPPGEstimator` + the real gates) and asks two questions:

1. Does POS recover a *plausible, stable* resting HR from a real face?
2. Does the motion gate *actually fire* when the subject moves?

It needs a human to sit in front of the camera, so it cannot be run by an agent.

```bash
PYTHONPATH= .venv/bin/python scripts/validate_rppg_webcam.py
```

Sit close (the gates need a face ≳127 px wide), even lighting, still for 40s, then
move your head for 12s. It prints why each reading was withheld, so a failure is
diagnostic rather than mysterious.

**Task 16b — the Orange Pi.** Deferred by the human on 2026-07-12. Still to do:
- FPS budget, health on vs off. **This is a real decision gate:** if the MediaPipe
  face detector costs >~15% of fall-detection FPS on the RK3588, switch to the
  pose-only ROI fallback (`roi_from_pose`, already built in Task 8).
- The RealSense exposure/WB lock, closing the `exposure_stable` gap above.
- End-to-end `/health/metrics` topic + HTTP scan on the robot.

x86 FPS numbers say nothing about the RK3588 — do not substitute one for the other.

---

## Process hazard hit on 2026-07-12 — do not run two agents on one worktree

opencode (Tasks 17/18) and Claude (Task 16a) ran **concurrently in the same
worktree**. opencode's `git add -A` swept up Claude's *uncommitted, in-progress*
files — `scripts/validate_rppg_webcam.py` and unsaved STATE.md edits — into
`c65ce77`, a commit that claims to be about the monitor UI. The review gate then
fired on the combined diff, so Claude's commit was blocked by defects in
opencode's code.

Two defects reached HEAD as a result, both now fixed:

1. **UI: destroyed DOM nodes.** `finalizeScan()` wrote the failure text into
   `#scan-progress` via `innerHTML`, destroying `#scan-pct` and `#scan-bar-fill` —
   which are cached in `const`s at load. After any failed or cancelled scan, a
   retry updated **detached elements** and the progress bar silently never moved.
   Fixed with a separate `#scan-status` element and `textContent`.
2. **STATE.md told the next agent to push to `origin/main`**, contradicting
   AGENTS.md §5. Removed.

**Rule: one agent per worktree.** If two must run, give each a git worktree
(`git worktree add`), or serialise them. Never `git add -A` in a shared tree.

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
