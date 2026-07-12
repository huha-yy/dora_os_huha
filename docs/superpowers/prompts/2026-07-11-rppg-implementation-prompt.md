# Implementation prompt — rPPG health metrics (Coder role)

Paste the block below into an `opencode` session in `/extra_space/dorabot_ws`.

Suggested invocation:

```bash
cd /extra_space/dorabot_ws
opencode run --model deepseek/deepseek-reasoner "$(cat docs/superpowers/prompts/2026-07-11-rppg-implementation-prompt.md)"
```

Or open opencode interactively and paste the prompt — interactive is better here,
because the Codex review gate on each commit can take several minutes and you can
watch it.

---

## PROMPT BEGINS

You are the **Coder/Tester** for `dorabot_ws` (see `AGENTS.md` §3.1 for roles).

### Read first, in order
1. `AGENTS.md` — especially §2 (environment facts) and §4 (commit gate).
2. `docs/superpowers/STATE.md` — where the project is and what's next.
3. `docs/superpowers/plans/2026-07-10-camera-health-metrics.md` — the 18-task plan.
4. `git log --oneline -12` — reconcile STATE.md against it; commits are ground truth.

### The rules that will bite you if you ignore them

**Test command — use this EXACT shape. Anything else silently fails:**
```bash
cd /extra_space/dorabot_ws/src/perception && PYTHONPATH= /extra_space/dorabot_ws/.venv/bin/python -m pytest tests/health -v
```
- `PYTHONPATH=` must be cleared. `/opt/ros/humble` is on `PYTHONPATH` and its
  `launch_testing` pytest plugin fails to import (`No module named 'lark'`),
  aborting collection **before any test runs**.
- Use the repo venv python. System `python3` has pytest but **not** numpy/scipy —
  tests there are meaningless.

**Hard constraints:**
- `src/perception/src/body_tracking/health/` must **not** import `rclpy`,
  `cv_bridge`, or any ROS module. It stays pure Python so it is testable off-robot.
- numpy is pinned `==1.26.4`. Never bump it. No PyTorch, no JAX.
- Non-medical product. v1 is **heart rate only**: `resp_bpm`, `hrv_sdnn_ms`,
  `spo2_pct` are always present and always `null`. `hr_bpm`/`hr_confidence` are
  `null` (never `0`) when there is no reading.
- Python ≥3.10, type-annotated, prefer frozen dataclasses.

**Discipline:**
- **TDD**: write the failing test, run it and watch it fail, implement, watch it pass.
- **Never commit a red test.** If a test fails and you believe the *plan* is wrong,
  STOP and say so — do not weaken the assertion. (The plan has already been wrong
  three times; see STATE.md "Plan corrections".)
- Tests must be **discriminative**. Before you commit a test that guards a bug,
  **negative-control it**: deliberately break the code, confirm the test fails,
  restore. A test that passes against the broken code is not a test.
- One task per commit, conventional message (`feat:`/`fix:`/`test:`).
- `git commit` triggers a **Codex review gate** automatically. Do **not** bypass it,
  never use `--no-verify`. If it reports `VERDICT: BLOCKER`, fix the concerns and
  commit again. `ADVISORY` proceeds — note the concerns in STATE.md.

---

### STEP 0 (do this first) — Task 10 review fix

The Task 10 message builder shipped with a **latent runtime crash**. Fix it before
anything else.

**Files in scope (touch nothing else):**
- `src/perception/src/body_tracking/health/messages.py`
- `src/perception/tests/health/test_messages.py`

**The bug.** `build_metrics()` embeds `quality_components` and `complexion` into the
returned dict **by reference, with no type coercion**. The perception ROS node builds
`quality_components` **by hand** from OpenCV/pose values, which yields numpy scalars.
Verified:
- `np.float64` DOES survive `json.dumps` (it subclasses `float`).
- `np.int64`, `np.float32`, `np.bool_` do **NOT** — `json.dumps` raises
  `TypeError: Object of type int64 is not JSON serializable`.

So an `np.int64` pixel count (`roi_px`/`face_px`), an `np.float32` motion delta, or an
`np.bool_` `exposure_stable` flag will **crash the perception node at publish time** —
the same node that runs safety-critical fall detection.

**Fixes:**
1. Make `build_metrics()` return a guaranteed-JSON-safe dict. Add a small internal
   helper that recursively coerces numpy scalars to native Python (`int`/`float`/`bool`)
   for `quality_components`, `complexion`, and the numeric fields. Use
   `isinstance(v, np.generic)` / `.item()`. Leave `None` as `None`. Do **not** silently
   drop values you cannot coerce — let them through so `json.dumps` fails loudly rather
   than the builder hiding a bug. The coercion must build **new** dicts (this also fixes
   the missing defensive copy: a caller mutating its dict must not retroactively change
   an already-returned message).
2. Add a test passing `np.int64`, `np.float32`, `np.bool_` inside `quality_components`
   and asserting `json.dumps(build_metrics(...))` succeeds. **Negative-control it.**
3. Add the missing test for `estimate is not None` **but** `estimate.hr_bpm is None` —
   assert BOTH `hr_bpm` and `hr_confidence` are `None` (never `0`).
4. Add a test pinning the exact message key set.

**Must not change:** the always-`null` `resp_bpm`/`hrv_sdnn_ms`/`spo2_pct`; the
`is not None` checks (a legitimate `0.0` must not collapse to null); `schema_version = 1`;
the public signature; `state` serialized as its lowercase string value.

78 tests currently pass. The full suite must be green before you commit.

---

### THEN — work the plan from Task 11 to Task 18

Execute one task at a time, in order, from
`docs/superpowers/plans/2026-07-10-camera-health-metrics.md`. Each task in the plan
lists its files, its interfaces, and its steps with the code to write.

Two plan corrections you MUST honour (the plan doc is already updated, but be alert):
- `sample_mean_rgb()` now returns `tuple | None`. In **Task 13**, when it returns
  `None`, do **not** append a sample to the ring buffer — sampling failed.
- `ScanController` now takes a trailing `max_dt_s: float = 2.0`.

Task-by-task notes:
- **Task 11** (estimator): pure Python, easy.
- **Task 12** (MediaPipe face detector): first module allowed to import mediapipe/cv2,
  still **no ROS**.
- **Task 13** (wire into the perception node): the ONLY perception file allowed to import
  `rclpy`. Keep the image callback cheap — ROI sampling only. All estimation runs on the
  1 Hz timer. Do not regress fall-detection FPS.
- **Tasks 14–15** (orchestrator): FastAPI `HealthBus` + `/health/*` endpoints, ROS bridge.
- **Task 16**: on-device smoke test on the Orange Pi — needs the real robot; if you cannot
  reach the hardware, STOP and report rather than faking it.
- **Task 17**: monitor UI (HR chip + scan card, bilingual, with the non-medical disclaimer).
- **Task 18**: config plumbing + README.

After each task: update `docs/superpowers/STATE.md` (tick the task, set the next one) and
commit that too.

### When you finish (or get stuck)
Report: which tasks landed (with commit hashes), the test count, any Codex ADVISORY
concerns you deferred, and anything you could not do (e.g. Task 16 needs hardware).

## PROMPT ENDS
