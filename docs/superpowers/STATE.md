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
| 16a | Real-face validation (**now on the D415**) | harness ready — **needs a human to run it** | |
| 16b | On-device FPS budget + e2e | deferred — needs the Orange Pi | |
| 16c | Wire the scan-scoped camera lock | **NEXT** — lock built (`5b52c48`), not applied | |
| 17 | Monitor UI (HR chip + scan card) | done | `c65ce77`, fixed `2551cc1` `cf1be94` |
| 18 | Config plumbing + docs | done | `c65ce77`, docs added `cf1be94` |

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

## The D415 is on the dev box (2026-07-14) — and one of my assumptions was wrong

`illum_delta` **cannot see auto-white-balance drift.** `c58c0de` left
`exposure_stable` hard-coded `True` and justified it as "illum_delta catches the
observable symptom of exposure hunting." That is true for auto-**exposure** and false
for auto-**white-balance**: AWB re-mixes R/G/B while holding brightness roughly
constant, so a *luminance* metric is blind to it by construction — and POS/CHROM
consume precisely the ratios AWB is scrambling.

Measured on the real D415, static scene. **AE and AWB are ON by default**, and after
any event that makes them re-adapt the chrominance takes **~5 seconds** to settle:

| window | illum_delta | B/G CoV |
|---|---|---|
| AUTO 0–10s | 0.1168 | **7.484%** ← adapting |
| AUTO 2–12s | 0.0031 | 0.983% |
| AUTO 5–15s | 0.0004 | 0.105% ← settled |
| LOCKED, any | 0.0005 | 0.089% ← clean from frame zero |

7.5% chrominance drift against a pulse that modulates the channels by ~1%: **the
camera's own regulation is several times larger than the signal.** The window is 10s,
so one AE/AWB event contaminates an entire window. And illum_delta peaked at 0.1168 —
**under its 0.15 gate. The window passed.**

Replayed through the production gates on real hardware (`5b52c48`):

| | illum_delta | chroma_drift | result |
|---|---|---|---|
| AUTO from cold | 0.1076 → PASS | 0.0539 → **REJECT** | withheld |
| LOCKED | 0.0103 → PASS | 0.0018 → PASS | published |

**New `chroma_drift` gate** (`max(CoV(R/G), CoV(B/G))`, gate 0.03). The threshold is
squeezed from **both** sides, because **the pulse is itself a chrominance modulation**
— that is what POS/CHROM extract:

- a real pulse moves R/G and B/G by **0.56%** (0.5% pulse) to **1.20%** (2% pulse)
- a settled camera: 0.08–0.22%
- a severe AWB transient: **7.48%**

A tighter gate would reject the signal it exists to protect. So it catches
**catastrophic** AWB hunting, not mild drift — the 2–12s tail (0.98%) sits inside the
pulse range and is genuinely indistinguishable. Mild drift is handled by the lock.

**`health/camera.py`** — `lock_color_sensor()`, pure and duck-typed so it unit-tests
without a camera. Disables AE+AWB and **verifies by reading back**: `set_option` can be
accepted and silently ignored, and a lock we *believe* in but do not have is worse than
no lock, since it would mark `exposure_stable=True` while the camera keeps hunting.

### Camera-lock scope — human decided 2026-07-14: **scan-only**

The colour stream is **shared** with YOLO and safety-critical **fall detection**. A
permanent AE lock would leave those working on an under-exposed image if the lighting
changes — trading fall-detection reliability for a better heart rate. Not an acceptable
trade. `HealthConfig.lock_camera_on_scan` already implied this.

**NOT YET WIRED.** The lock exists and is verified against the hardware, but nothing
applies it at runtime. Next commit: RealSense publisher locks on scan start, restores
auto on scan end; perception drives `exposure_stable` from the real lock state.

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
# The D415 is now connected -- validate on the PRODUCTION camera, AE/AWB locked:
PYTHONPATH= .venv/bin/python scripts/validate_rppg_webcam.py --realsense

# The A/B: same run with AE/AWB left on auto. Readings are withheld BY DESIGN;
# watch chroma_drift, not the HR.
PYTHONPATH= .venv/bin/python scripts/validate_rppg_webcam.py --realsense --no-lock
```

Sit close (the gates need a face ≳127 px wide), even lighting, still for 40s, then
move your head for 12s. It prints why each reading was withheld, so a failure is
diagnostic rather than mysterious, and it now reports the **confidence distribution
against the 0.70 gate** — which is what tells us whether a real face clears a gate
sited against synthetic pulses.

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

### Audit of Tasks 17/18 (`c65ce77`) — two further gaps, both fixed

Claude audited opencode's work against the plan and spec on 2026-07-12:

- **Task 17 shipped the complexion without its caveat.** Spec §7.3 requires the
  面色 card to carry one, and `describe_complexion()` has produced it all along
  ("lighting/WB dependent, not a health indicator") — the UI simply never rendered
  it. The generic "非医疗设备 / not a medical device" line is a *different* claim: a
  user shown 面色偏白 reads it as a health signal unless told it is an appearance
  read that depends on lighting. Fixed in `cf1be94`.
- **Task 18 step 2 was never done.** The README documentation did not exist; the
  only "health" hits in it were the orchestrator's pre-existing liveness endpoint.
  Written in `cf1be94`.

What *did* check out: no forbidden health/wellness/vitality/diagnostic language;
面色 not 气色; `hr_bpm` null renders `--` not `0`; the `HEALTH_ENABLED=0` kill
switch fully bypasses the feature and leaves fall detection untouched; face
detection correctly runs only on processed frames while cheap RGB sampling runs
every frame.

### Orchestrator test gap — filled (`7db45af`, `610a462`). It was hiding three bugs.

Task 14 shipped with **one** test for the whole HealthBus + HTTP router. Writing the
missing ones (1 → 29) surfaced three defects:

1. **[P1] Stale vital signs served as live.** `HealthBus` never expired anything and
   the ROS bridge only ever calls `set_metrics()`. If perception crashed, ROS
   disconnected, or the camera was unplugged, `/health/live` kept serving the last
   heart rate **forever** and the UI kept rendering it as current. The perception
   node's own 5s frame-staleness guard does not cover this — it only runs while that
   node is alive and publishing, so node death defeats it entirely. Metrics are now
   stamped on arrival with a **monotonic** clock (an NTP step must not make a stale
   reading look fresh) and withheld past `METRICS_TTL_S = 5.0`.
2. **[P2] `window_s` was silently ignored.** The API accepted it, the bus carried it,
   the ROS topic shipped it — and `_on_scan_cmd` used the configured 30s anyway. A
   60s scan silently ran for 30s. `ScanController.start()` now takes a per-scan
   override, reset each start so one scan's window cannot leak into the next.
3. **[P2] No input validation.** `{"window_s": "abc"}` was a 500; negatives and
   absurd values were forwarded to perception. Now bounded 5–120s with a 422.
   NaN/Infinity too — strict JSON cannot encode them, but `json.loads` accepts the
   literals, so a real client can send them.

Codex then caught a **weak test of mine**: `body.get(k) is None` also passes when the
key is *missing*, so it did not notice that the idle payload omitted the null
`resp_bpm`/`hrv_sdnn_ms`/`spo2_pct` stubs the v1 contract requires. Fixed both.

### The review gate itself was unsound — fixed (`7891667`, `688356f`)

Codex never emits the `VERDICT:` line the prompt asks for, so the hook's *inference*
path is the normal path, and it had two bugs: it read only `tail -n 80` of a
4000-line transcript (a long final answer could hide its own findings and be read
as clean — failing in the dangerous direction), and it aborted genuinely clean
reviews by trying to pattern-match unbounded praise prose. Now it anchors to the
`codex` marker, reads the whole final answer, treats zero findings as APPROVED, and
fails closed when the reviewer bailed out without reviewing.

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

## THE BIG ONE — pure noise was publishing a heart rate (~20% of windows)

Found on 2026-07-12 while triaging the deferred findings below. This was the most
serious defect in the project and **nothing in 120 tests caught it**, because every
test fed the estimator a pulse and checked it recovered it. Nothing tested the
opposite and far more dangerous case: **feed it no pulse and see whether it invents
one.** It did.

Measured over 400 trials of pure Gaussian noise, 10s window:

| | confidence |
|---|---|
| pure noise | mean **0.44**, p99 **0.64**, max 0.73 |
| a real 1% pulse | p01 **0.85**, min 0.82 |
| **`min_confidence` gate** | **0.50 — inside the noise distribution** |

Confidence never approaches zero for noise: `0.5*snr/(snr+4) + 0.5*dominance` has a
floor near 0.44, because a random spectrum still has *some* peak in the 0.7–4 Hz band
and dominance rewards it. The gate wasn't separating signal from noise — it was
cutting through the middle of the noise.

**Not theoretical.** Every other gate (face present, size, FPS, motion, illumination)
passes happily for a real, still, well-lit face whose rPPG signal is simply too weak
to recover — poor light, an unlucky skin tone, a camera with aggressive denoising.
That window *is* noise, and it was ~1-in-5 to show a confident phantom heart rate.

**Gate raised 0.50 → 0.70** (`e195075`), sited from data, not guessed:

| gate | phantom-HR rate | accepts a weak 0.5% pulse |
|---|---|---|
| 0.50 | **16.7%** | 100% |
| 0.60 | 2.0% | 99% |
| **0.70** | **0.25%** | 89% (POS) / 99% (CHROM) |
| 0.80 | 0.00% | 36% |

`tests/health/test_noise_rejection.py` pins the phantom rate, the sensitivity, **and
the separation itself**, so a change to the confidence formula cannot quietly erase
the gap the gate depends on.

> **The gate is sited against SYNTHETIC pulses.** Where a *real* face lands is still
> unknown — that is **Task 16a**. The webcam harness now reports the confidence
> distribution against the gate, so that run answers it directly. If real faces
> cluster below 0.70, tune with real data. **Do not go back to 0.50.**

---

## Deferred minor findings — triaged 2026-07-12

- **T13 — FIXED** (`c58c0de`). The node no longer reaches into `_rppg._buffer`;
  `RPPGEstimator.window()` is public.
- **T5 — FIXED** (`e195075`, `4fa5c9f`). Config carries the quality gates, so a
  mistake there is a *safety* bug: someone tightening `min_confidence` to 0.9 who
  typo'd the key was silently running the default with no way to find out.
  `from_dict` now rejects unknown keys (with a did-you-mean), unknown backends,
  out-of-range gates, non-positive windows, and **non-finite values** — a `NaN`
  threshold silently *disables* its gate, since `motion > nan` never trips
  (demonstrated: `max_motion=NaN` lets `motion=999` pass cleanly). Because
  `from_dict` is now strict, the node guards its own construction: a bad
  `HEALTH_BACKEND` logs loudly and disables the health feature rather than raising
  and taking down the node that also runs **safety-critical fall detection**. A demo
  feature must never kill the safety feature.
- **T4 — DISMISSED after investigation.** The premise was wrong. `alpha·s2` cannot
  blow up: `alpha = std(s1)/std(s2)` makes `std(alpha·s2)` bounded by `std(s1)` by
  construction, and any DC term is removed by the bandpass. The `ts`/`rgb` length
  mismatch already raises loudly from numpy. No change — but the probe written to
  test it is what surfaced the noise-gate bug above.
- **T1, T2 — open, low value.** Weak assertions in `test_rgb_sample_is_immutable_*`
  and `test_gate_result_defaults`; `effective_fps`'s `span <= 0` guard is dead code
  now that `append()` enforces strict monotonicity. Cosmetic; safe to merge with
  these open.
- **Process:** the Coder did not update STATE.md after each task as instructed
  (tasks 11–15 landed with STATE.md untouched). Reconciled manually on 2026-07-12.
