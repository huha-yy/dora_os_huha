# Implementation prompt — rPPG gates + UI (Coder role, round 2)

Paste the block below into an `opencode` session in `/extra_space/dorabot_ws`.

```bash
cd /extra_space/dorabot_ws
opencode run --model deepseek/deepseek-reasoner "$(cat docs/superpowers/prompts/2026-07-12-rppg-gates-and-ui-prompt.md)"
```

Interactive is better — the Codex gate on each commit takes minutes.

---

## PROMPT BEGINS

You are the **Coder/Tester** for `dorabot_ws` (see `AGENTS.md` §3.1 for roles).

Tasks 1–15 are committed; 87 tests pass. You are picking up at **Task 15b**.

### Read first, in order
1. `AGENTS.md` — especially §2 (environment facts) and §4 (commit gate).
2. `docs/superpowers/STATE.md` — position, and *why* Task 15b exists.
3. `docs/superpowers/plans/2026-07-10-camera-health-metrics.md` — Tasks 15b, 17, 18.
4. `git log --oneline -20` — commits are ground truth.

### Read this part twice

The previous Coder round **dismissed a Codex [P1] finding by citing the plan**
(see `.review/manual-review-task13.txt`). That is not a valid reason to dismiss a
reviewer. The plan's reference code has now been wrong **four** times — it is the
*least* trustworthy artifact in this repo, which is exactly why the review gate
exists.

**If a reviewer and the plan disagree, STOP and ask the human** (AGENTS.md §6).
Do not adjudicate it yourself, and never in favour of the plan.

Also: the previous round did not update `STATE.md` after each task, as instructed.
Update it. It is how the next session knows where it is.

### The rules that will bite you

**Test command — use this EXACT shape. Anything else silently fails:**
```bash
cd /extra_space/dorabot_ws/src/perception && PYTHONPATH= /extra_space/dorabot_ws/.venv/bin/python -m pytest tests/ -v
```
`PYTHONPATH=` must be cleared: `/opt/ros/humble` is on it and its `launch_testing`
pytest plugin fails to import (`No module named 'lark'`), **aborting collection
before any test runs**. Use the repo venv python — system `python3` has pytest but
not numpy/scipy, so tests there are meaningless.

**Hard constraints:**
- `src/perception/src/body_tracking/health/` must **not** import `rclpy`,
  `cv_bridge`, or any ROS module. Pure Python, testable off-robot.
- numpy pinned `==1.26.4`. Never bump. No PyTorch, no JAX.
- Non-medical product. v1 is **heart rate only**: `resp_bpm`, `hrv_sdnn_ms`,
  `spo2_pct` always present, always `null`. `hr_bpm`/`hr_confidence` are `null`
  (never `0`) when there is no reading.
- No heavy work in the perception image callback — it shares the hot path with
  safety-critical fall detection. Estimation runs on the 1 Hz timer.

**Discipline:**
- **TDD**: write the failing test, watch it fail, implement, watch it pass.
- **Never commit a red test.** If a test fails and you think the *plan* is wrong,
  STOP and say so — do not weaken the assertion.
- **Negative-control** any test that guards a bug: break the code deliberately,
  confirm the test goes red, restore.
- One task per commit, conventional message. `git commit` runs the **Codex review
  gate** automatically. Never `--no-verify`. On `VERDICT: BLOCKER`, fix and retry.

---

### Task 15b — real motion + illumination gates (do this first)

Full spec is in the plan under **"Task 15b"**. Read it there; it has the metric
definitions, the calibration table, and the step list.

Summary: `body_tracking_node.py:440-442` hard-codes `motion=0.0`,
`illum_delta=0.0`, `exposure_stable=True`, so three of eight quality gates can
never fail. Head motion is the dominant rPPG artifact — it aliases into the
0.7–4 Hz pulse band and produces a *confident wrong* BPM. Implement `motion` and
`illum_delta` for real in a new pure-Python `health/artifacts.py`.

Three things the plan spells out that you must not get wrong:

1. **Both metrics are computed over the analysis window, not frame-to-frame.**
   A per-frame delta is frame-rate dependent and far too noisy to threshold.
2. **Fail closed.** Degenerate input (fewer than 2 samples, missing ROI geometry,
   non-positive mean luminance) returns `1e9` — a value that *fails* the gate.
   Never `0.0`; `0.0` passes, and that is the whole bug you are fixing.
3. **Do not retune `config.py`.** The thresholds (`max_motion=0.05`,
   `max_illum_delta=0.15`) are already correct for the metrics as defined. If a
   test disagrees, your metric is wrong, not the threshold.

`exposure_stable` stays `True` — it needs the RealSense lock, which is Task 16.
Do not widen scope.

---

### Then Task 17 — monitor UI

`src/orchestrator/web_server/ui/index.html`. HR chip overlay + scan card, per the
plan. Bilingual, and the non-medical disclaimer is **required** on the card:
`仅供参考，非医疗设备 · For reference only, not a medical device`.

No health / wellness / vitality / diagnostic language anywhere in user-facing
strings. Complexion is 面色 (appearance), never 气色, and carries its own caveat.
Show `--` when `hr_bpm` is `null` — never `0`, never a stale value.

### Then Task 18 — config plumbing + docs

Per the plan. Include the `enabled: false` kill switch and confirm the feature is
fully bypassed when off (fall detection must be untouched).

### Task 16 is BLOCKED — do not attempt it

It requires the physical Orange Pi + RealSense. If you cannot reach the hardware,
**stop and report** rather than faking a smoke test or inventing FPS numbers.

### After each task
Update `docs/superpowers/STATE.md` (tick the task, set the next one) and commit it.

### When you finish (or get stuck)
Report: tasks landed with commit hashes, test count, any Codex ADVISORY concerns
you deferred, and anything you could not do.

## PROMPT ENDS
