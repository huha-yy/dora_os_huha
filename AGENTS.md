# AGENTS.md — Operating manual for AI agents working on `dorabot_ws`

This file is the source of truth for any AI agent (Claude Code, Codex, agy,
opencode with DeepSeek, etc.) operating in this repository. Read it on every
new session. The user's explicit instructions always override anything here.

`CLAUDE.md` and `GEMINI.md` are symlinks to this file — edit `AGENTS.md` only.

---

## 0. Read these first, in order

1. **`docs/superpowers/STATE.md`** — current position. Names the active plan,
   the last completed task, and what to do next.
2. The plan referenced by `STATE.md` (under `docs/superpowers/plans/`).
3. The design spec under `docs/superpowers/specs/` for any architectural question.
4. `git log -10 --oneline` and `git status` to confirm tree state.
5. **Reconcile STATE.md against `git log` before trusting it.** Commits are
   ground truth; STATE.md is a derived view that goes stale when a session is
   interrupted (quota hit, crash). If `git log` shows task commits past what
   STATE.md records, fix STATE.md first, commit that reconciliation through the
   review gate, then resume.

Do not write code before steps 1–5 are done.

---

## 1. What this project is

`dorabot_ws` — an autonomous robot stack running on an **Orange Pi 5 (RK3588S,
8GB) with a RealSense D415**. Live vision + fall detection, a voice chatbot, and
optional mapping/navigation.

```
chatbot (:8000) ──┐
RealSense D415 ───┤
perception ───────┼──► orchestrator (:8080) ──► unified web UI
fall events ──────┘        ├─ live annotated camera (MJPEG)
                           └─ chatbot sidebar
```

| Path | Role |
|---|---|
| `src/perception/` | ROS 2 node: YOLO (RK3588 NPU) + MediaPipe pose (CPU), fall detection. Also hosts the `health/` rPPG package. |
| `src/orchestrator/` | FastAPI web layer + ROS bridge. Serves the monitor UI. |
| `src/ai_agent/`, `src/chatbot/` | Voice chatbot (MiniMax LLM). |
| `src/nav/` | Optional SLAM / Nav2. |

**Active work:** camera-based health metrics (rPPG heart rate). See STATE.md.

---

## 2. Hard-won environment facts (read before running anything)

These cost real debugging time. Do not rediscover them.

### Tests: you MUST clear `PYTHONPATH`

```bash
cd src/perception && PYTHONPATH= /extra_space/dorabot_ws/.venv/bin/python -m pytest tests/health -v
```

- **`PYTHONPATH=` is mandatory.** The shell profile puts `/opt/ros/humble` on
  `PYTHONPATH`; its `launch_testing` pytest plugins fail to load (`No module
  named 'lark'`) and **abort collection before any test runs**. Clearing it also
  enforces the "health core imports no ROS" rule below.
- **Use the repo venv python** (`/extra_space/dorabot_ws/.venv/bin/python`).
  System `python3` has pytest but **not** numpy/scipy/mediapipe — tests there
  are meaningless.
- The venv has numpy 1.26.4, scipy 1.15.3, mediapipe, opencv. Install with
  `uv pip install --python /extra_space/dorabot_ws/.venv/bin/python <pkg>`
  (the venv has no `pip`).

### Pins and boundaries

- **numpy is pinned `==1.26.4`** for MediaPipe/cv_bridge ABI compatibility. Never bump it.
- **`src/perception/src/body_tracking/health/` MUST NOT import `rclpy`,
  `cv_bridge`, or any ROS module.** It is pure Python so it is unit-testable
  off-robot. ROS lives only in `body_tracking_node.py` and the orchestrator.
- No PyTorch, no JAX. The Pi runs YOLO on the NPU; everything else is CPU numpy/scipy.
- Do not run heavy work in the perception image callback — it is the hot path
  shared with **safety-critical fall detection**. Estimation belongs on a timer.

### Product constraints (non-negotiable)

- The health feature is **non-medical**. No health, vitality, wellness, or
  diagnostic language anywhere in user-facing strings.
- **v1 is HEART RATE ONLY.** `resp_bpm`, `hrv_sdnn_ms`, `spo2_pct` are always
  present in the message and always `null`. Never populate them.
- `hr_bpm` / `hr_confidence` are `null` (never `0`) when there is no reading.
- Complexion is **appearance-only** (面色, not 气色) with a bilingual
  "not a health indicator" caveat. No numeric score.

---

## 3. Multi-tool development workflow — roles and fallbacks

This repo is developed by a **role-separated agent team**. Each role has a
primary tool and a fallback. All tools read this file.

### 3.1 Role assignments

| Role | Primary | Fallback 1 | Fallback 2 |
|---|---|---|---|
| **Brainstormer** | Claude Code | DeepSeek (via opencode) | — |
| **Planner** | Claude Code | DeepSeek (via opencode) | — |
| **Coder** | DeepSeek (via opencode) | — | — |
| **Tester** | DeepSeek (via opencode) | — | — |
| **Reviewer** | Codex CLI | agy | DeepSeek subagent (via opencode) |

**Budget notes.** Claude Code and Codex have hourly/weekly caps — when the
primary hits its limit, switch to the fallback. DeepSeek is pay-as-you-go via
API key, used through opencode. `agy` uses OAuth.

**Autonomy.** Coder and Tester proceed without asking permission as long as the
Reviewer raises no blocking concern. The human is consulted only for design
decisions.

### 3.2 Calling opencode with DeepSeek (Coder / Tester)

```bash
opencode run --model deepseek/deepseek-reasoner "<task prompt>"
```

- `deepseek/deepseek-reasoner` for implementation and debugging.
- `deepseek/deepseek-chat` for cheap mechanical edits.
- The Coder follows **subagent-driven development**: one task at a time, each
  dispatched with its full task text plus the constraints in §2.
- The Tester follows **TDD**: write the failing test, watch it fail, implement,
  watch it pass. **Never commit a red test.**

### 3.3 Calling Codex CLI (Reviewer, primary)

Codex is slow on large diffs. **Always give it ≥30 min** (`timeout 1800`; from
an agent tool call pass `timeout=1800000` ms).

```bash
codex exec review --skip-git-repo-check "<review prompt>"
```

If Codex reports quota exhausted or times out, fall back to `agy`.
**Never commit with `--no-verify`.**

### 3.4 Calling agy (Reviewer, fallback 1)

`agy` reads the diff on **stdin** and needs auto-approval to run non-interactively:

```bash
git diff --cached | agy -p "<review prompt>" --dangerously-skip-permissions
```

### 3.5 Calling Claude Code as reviewer (emergency only)

Claude Code is normally the Brainstormer/Planner. Use it as Reviewer only when
Codex, agy, and DeepSeek are all unavailable:

```bash
git diff --cached | claude -p "review this diff..."
```

---

## 4. Commit gate — Reviewer sign-off is mandatory

**Every code commit MUST be preceded by a reviewer pass.** The agent MUST NOT
decide a review can be skipped — only the reviewer's verdict clears the gate.

The `.githooks/pre-commit` hook enforces this automatically. Activate it once
per clone:

```bash
git config core.hooksPath .githooks
```

The hook:
1. Skips trivial diffs (≤10 lines) and docs-only commits.
2. Runs **Codex** on the staged diff (30 min timeout); on failure/quota falls
   back to **agy**; if both are down it aborts and tells you to review manually.
3. Saves every review to `.review/` and prints it.
4. Reads the verdict line and acts:
   - `VERDICT: APPROVED` → commit proceeds.
   - `VERDICT: ADVISORY` → commit proceeds; address concerns in a follow-up.
   - `VERDICT: BLOCKER` → **commit aborted.** Fix, re-stage, retry.

### Escape hatches

| Situation | Command |
|---|---|
| Normal commit | `git commit` — hook auto-runs Codex → agy |
| Codex quota'd / timing out | `SKIP_CODEX_REVIEW=1 git commit` — still runs agy |
| All reviewers confirmed down | Review manually, save output to `.review/`, then `SKIP_ALL_REVIEW=1 git commit` and reference the review file in the commit body |

`git commit --no-verify` is **forbidden** — it skips the whole pipeline.

### Review discipline

- One review per task-commit. Do not batch reviews across tasks.
- Address every concern the reviewer raises, or state in the commit body why it
  is dismissed.
- Reviewer findings that are **Critical** or **Important** block the commit.
  Minor findings go in a follow-up and are recorded in STATE.md.
- **Verify fixes with a negative control** where a test claims to guard a bug:
  break the code deliberately, confirm the test fails, restore. A test that
  passes against the broken code is not a test.

---

## 5. Conventions

- **Commits:** conventional format — `feat:`, `fix:`, `test:`, `docs:`,
  `refactor:`, `chore:`, `perf:`, `ci:`. Attribution is disabled globally.
- **Branches:** never commit directly to `main`. Work on a feature branch.
- **Style:** PEP 8, type annotations on all signatures, prefer frozen
  dataclasses. Functions <50 lines, files <800 lines.
- **Tests:** TDD, 80%+ coverage target. Tests must be *discriminative* — if a
  test would pass against a deliberately broken implementation, it is not
  earning its keep.
- **Errors:** handle explicitly, never swallow. Prefer a loud failure over a
  plausible-but-wrong number — this project computes vital signs, where a silent
  wrong answer is worse than no answer.

---

## 6. When in doubt

- **Skill exists?** Use it (`superpowers:using-superpowers`).
- **Plan unclear?** Stop and ask the user, or fix the plan first.
- **About to do something destructive?** Confirm with the user.
- **Reviewer and plan disagree?** The human decides. Present both, don't guess.
