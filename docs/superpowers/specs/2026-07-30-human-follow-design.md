# Human Follow (跟随模式) — Design

**Date:** 2026-07-30
**Status:** Draft for review (written after Codex design review — BLOCKER concerns folded in)
**Author:** Frank (with Claude)
**Target hardware:** Orange Pi 5, RK3588, 8GB RAM, RealSense D415, holonomic omni-wheel base

---

## 1. Summary

Add a **human-follow** behavior to the Dorabot stack: on a Chinese voice command,
the robot locks onto the person who issued it and physically follows them,
maintaining a comfortable standoff distance, until told to stop or it loses them.

The robot already **detects** people (YOLO person detection + MediaPipe pose in
the perception node) and already has the primitives for **where** a person is in
3D (`DepthTo3DConverter.bbox_to_3d_position` → `Point3D` in metres). This feature
adds the missing pieces: a **target lock** that keeps following the *right* person
when others are around, a **motion-control loop** on the holonomic base, an
**arbitration layer** so follow motion doesn't fight the other `/cmd_vel`
producers, and the **safety machinery** required for a robot that drives
autonomously near people.

This is a **supervised / demo-grade v1**: conservative speed caps, a gamepad
hard-stop, and a "stop when unsure" contract. It is explicitly **not** an
unsupervised production autonomy feature.

> **Provenance note.** An earlier draft of this design proposed publishing
> `/cmd_vel` directly, a spatial-only target lock, on-demand depth via a latched
> topic, and voice/UI as the only stop. A code-grounded Codex review returned a
> **BLOCKER** verdict and corrected all four (see §13). This spec is the revised,
> post-review design.

## 2. Goals & Non-Goals

### Goals
- On a Chinese voice command ("小戴，跟我走"), **acquire** the nearest-and-centered
  person (with a clear margin) as the follow target.
- **Keep the lock on the right person** when 2–4 people are in view, including
  brief crossings and occlusions — or **stop and re-confirm** when genuinely
  ambiguous. Never silently switch target.
- **Follow** the target on the holonomic base: rotate to keep them centered, drive
  to hold a ~1.2 m standoff, capped at a slow supervised speed.
- **Stop reliably** via four independent surfaces: gamepad hard-stop, voice, UI
  button, and automatic stop when the target is lost.
- Run **without degrading fall-detection frame rate** and without blocking the
  perception image callback.
- All user-facing voice and TTS is **Chinese-first** (English deferred).

### Non-Goals (v1)
- No unsupervised operation. v1 is supervised/demo-grade only.
- No appearance-based deep re-identification (recognizing a specific person after
  they fully leave and re-enter). Target lock is spatial + motion + optional
  coarse color tie-break only.
- No path planning, mapping, or navigation around obstacles. Obstacle depth is a
  **weak brake** (slow/stop), not an avoidance planner.
- No lateral strafing (`vy`) in the control law (interface preserved for later).
- No following through doorways/corners as a designed behavior — losing the target
  at a corner triggers the bounded loss-recovery, then stop.
- No English voice/TTS (later phase).

## 3. Operating assumptions & environment

- **Crowd context:** target + a few others (2–4 people typically in frame).
- **Supervision:** a human is always present during v1 operation.
- **Space:** tidy indoor space (home/office). Low obstacles (chair legs, steps),
  side obstacles, and rear obstacles are **outside** the forward camera's view and
  are handled only by conservative caps + supervision, not by sensing.
- **Base:** holonomic omni-wheel; `chassis_ros_node` consumes `/cmd_vel` (Twist)
  and supports `vx, vy, omega` independently. Chassis watchdog stops the base if
  no `/cmd_vel` arrives for 1 s.
- **Camera:** RealSense D415, **mounted upside-down** (`flip_180=true`),
  forward-facing at roughly head height. Color **and** depth are flipped 180°.
- **Depth:** off by default (CPU budget shared with safety-critical fall
  detection); enabled for the duration of a follow session (see §7).

## 4. Architecture

Six components, each with a single responsibility. Only the mux publishes chassis
`/cmd_vel`.

```
                         ┌─────────────────────────────────────────────┐
  voice "小戴，跟我走"   │  chatbot skill (follow_control, keywords)     │
  ───────────────────►  │  → orchestrator bridge → /human_follow/cmd    │
                         └───────────────┬─────────────────────────────┘
                                         │ (start / stop, JSON)
                                         ▼
  perception (body_tracking_node)   ┌───────────────────┐      /cmd_vel/follow
  ┌────────────────────────────┐    │  human_follow     │ ───────────────┐
  │ target tracker (IDs+Kalman)│    │  node             │                │
  │ 3D localization (depth)    │───►│  - control loop   │                ▼
  │ forward-obstacle distance  │    │  - loss state m/c  │        ┌──────────────┐
  │ publishes:                 │    │  - caps + gates   │        │  twist_mux   │
  │  /human_follow/target_state│    │  pure-py core     │        │ (arbitration)│──► /cmd_vel ──► chassis
  └────────────────────────────┘    └───────────────────┘        └──────▲───────┘
                                                                         │ inputs (timed, prioritized)
   F710 gamepad ──► /cmd_vel/stop (hard-stop, top priority) ─────────────┤
   voice-chassis / exo ──► /cmd_vel/manual ──────────────────────────────┤
   orchestrator UI stop ──► /cmd_vel/stop  +  /human_follow/cmd(stop) ────┘
```

### 4.1 Components

1. **`twist_mux` (arbitration layer).** The single publisher to chassis
   `/cmd_vel`. Standard, battle-tested ROS package (reuse, not hand-rolled).
   Producers are remapped to private inputs with per-input timeouts and locks.
2. **Perception (`body_tracking_node`, extended).** Owns the **target tracker**,
   **3D localization**, and **forward-corridor obstacle distance**. Publishes the
   rich `/human_follow/target_state` on a **timer** (not the image callback).
   Requests depth-on for follow sessions.
3. **`human_follow` node (new).** Consumes `target_state`; runs the control loop,
   loss state machine, and safety caps; publishes `/cmd_vel/follow`. Its control
   math is a **ROS-free, unit-testable Python module** (mirrors `body_tracking/health/`).
4. **Voice skill (`chatbot/skills/follow_control`).** Chinese keyword matching for
   start/stop → orchestrator bridge → `/human_follow/cmd`. No direct ROS from the
   chatbot venv (it is ROS-isolated by design).
5. **Orchestrator.** Bridges the voice command to ROS; serves a UI **Stop** button
   and a live follow-state display; can publish `/cmd_vel/stop`.
6. **Gamepad hard-stop.** F710 → `/cmd_vel/stop` at top mux priority; halts and
   exits follow independent of voice/vision/UI.

### 4.2 Why this split (Option A)

The control loop lives **outside** the perception process (fault isolation from
safety-critical fall detection) and **outside** the chatbot (its venv cannot
`import rclpy`, and subprocess `ros2 topic pub` is far too slow for a real-time
loop). Perception owns *perception* (who/where); `human_follow` owns *motion*.
Codex confirmed this split does **not** create a real latency problem provided the
target-state message is stamped and fresh (10–15 Hz perception state feeding a
20–50 Hz controller is fine).

## 5. Target acquisition & tracking

### 5.1 The "right person" contract

`person_id` in the current code is a placeholder — the detector hardcodes `0` and
`get_person_by_id()` returns the first person. This feature introduces a real
tracker with a hard behavioral contract:

> **Never switch target silently. When identity is ambiguous, STOP and re-confirm.**

### 5.2 Tracker

Lightweight, CPU-only (no deep re-ID):

- **Per-person track IDs** assigned across frames.
- **Kalman prediction** of each track's image/3D position between detections.
- **Assignment gating:** associate detections to tracks by predicted position +
  bbox size; reject associations outside a gate.
- **Optional coarse appearance tie-break:** torso color histogram, used only to
  disambiguate when two tracks are within each other's gate (a crossing).
- **Ambiguity detection:** if the locked target cannot be associated with
  confidence — two candidates inside the gate, a crossing with no color margin, or
  a stale track — the tracker reports `ambiguous`, and the controller stops.

### 5.3 Acquisition

On `start`, the target is the person who is **nearest and most centered, with a
clear margin** over the runner-up. If no candidate has a clear margin (e.g. two
people equally centered), acquisition **fails safely** — the robot does not move
and announces it needs a clearer target. Acquisition also requires the
depth-ready handshake (§7).

## 6. Motion control

### 6.1 Control law

- **omega** ∝ horizontal bearing error (keep target centered).
- **vx** ∝ (measured standoff − target standoff), target **~1.2 m** (config).
- **vy = 0** for v1. The control interface carries a lateral-error term but it is
  clamped to zero (YAGNI; holonomic strafing is a later enhancement).
- Output is rate-limited (ramp) and clamped to the caps below, then published to
  `/cmd_vel/follow` **continuously** while `human_follow` owns motion.

### 6.2 Demo caps (v1, conservative)

| Cap | v1 value (config) | Rationale |
|-----|-------------------|-----------|
| Max linear speed | ≤ 0.3 m/s | supervised walking-pace-safe |
| Max angular speed | small, tuned | avoid whipping around |
| Min standoff floor | hard floor < target | never approach closer than this |
| Follow standoff | ~1.2 m | comfortable companion distance |

Caps are **config values**, intended to be relaxed only after the tracker and
gamepad e-stop are field-proven.

### 6.3 Coordinate-sign safety

Because color **and** depth are flipped 180° and `Point3D.x` is positive-right, a
single sign error would drive the robot **toward** the error instead of correcting
it. A **physical sign test** (person left/right/near/far → expected wheel motion)
is a **mandatory gate** in the bring-up runbook before any nonzero motion is
enabled on the robot.

## 7. Depth handling

On-demand depth via a latched topic is **not** implementable: the RealSense node
decides depth at *pipeline startup* (`enable_depth` controls whether the stream
and publisher exist at all).

**v1 approach:**
- Depth runs for the **whole follow session** (a follow-enabled camera profile),
  not toggled per-command.
- Before any nonzero motion, `human_follow` requires a **depth-ready handshake**:
  `depth_ready == true`, a **fresh** aligned-depth frame, and camera info present.
- If depth goes stale or missing at any point, the obstacle check and the target
  distance **fail closed** → stop.

Enabling depth costs RK3588 CPU shared with fall detection; the bring-up runbook
measures fall-detection FPS with depth on and follow active, and the feature must
stay within the established FPS budget (as the health feature did).

## 8. Obstacle handling (weak brake)

- Perception samples depth in a **forward drive corridor** and publishes the
  nearest in-corridor distance in `target_state`.
- `human_follow` uses it to **slow/stop** if something in the path is too close —
  a **weak brake, explicitly not a safety guarantee.**
- **Documented blind spots:** low obstacles (chair legs, steps), side obstacles,
  and anything behind the robot are invisible to a forward head-height camera.
  Conservative caps + supervision are the backstop, not a fallback.
- **Fail closed:** stale/missing obstacle depth → treat as blocked → stop.

## 9. Loss handling

On losing the locked target (occlusion, target leaves frame, rounds a corner):

1. **Halt translation immediately** (vx = 0).
2. **Bounded rotate-search** toward the last-seen bearing: **omega ≤ 0.2 rad/s,
   ≤ 2–3 s, ≤ 45–60° total yaw**, and abort on stale state or a near obstacle.
3. If re-acquired near the predicted position → resume `following`.
4. Else → exit to `stopped`, announce **"我跟丢了"** (TTS, Chinese).

Rotate-search is a **tiny bounded recovery**, never an open-ended scan.

## 10. Stop surfaces & arbitration

| Surface | Channel | Priority / effect |
|---------|---------|-------------------|
| **Gamepad hard-stop** (F710) | `/cmd_vel/stop` | **Top.** Instant halt + exit follow. |
| Orchestrator / UI stop | `/cmd_vel/stop` + `/human_follow/cmd(stop)` | Halt + exit follow. |
| Voice "小戴，别跟了" | chatbot → bridge → `/human_follow/cmd(stop)` | Exit follow. |
| Auto-stop (lost) | internal | Exit to `stopped` after loss recovery fails. |

**Mux rules:** priority **stop > manual/gamepad-drive > follow > voice one-shot**;
per-input **timeout ~0.2–0.3 s** (much tighter than the chassis 1 s watchdog);
publish a **zero** on owner switch; **manual drive input cancels follow**; the stop
channel is independent of follow-node liveness (a crashed `human_follow` cannot
keep the base moving — its input times out and the mux falls back).

## 11. State machine

```
idle ──start──► acquiring ──margin ok──► waiting_for_depth ──depth ready──► following
  ▲                 │ no clear margin           │ depth stale                    │
  │                 ▼                            ▼                    target lost │
  └──────────────  error/idle (announce)   stopped ◄──────────── searching ◄─────┘
                                                    recovery fails      │ re-acquired
                                                                        └──► following
```

States: `idle, acquiring, waiting_for_depth, following, searching, lost, stopped,
error`. The current state is published and shown in the UI.

## 12. Message & topic contract

- **`/human_follow/target_state`** (new; JSON String v1, custom msg later):
  `stamp`, `frame_id`, `state` (enum §11), `lock_id`/`track_id`,
  `target_visible`, `target_confidence`, `association_confidence`, `x, y, z`
  (metres, camera frame), `bearing`, `distance`, `depth_ready`,
  `obstacle_distance`, `obstacle_stamp` (freshness), `ambiguous`, `reason`.
- **`/human_follow/cmd`** (new): `{action: "start"|"stop", ts}` from voice/UI.
- **`/cmd_vel/follow`, `/cmd_vel/manual`, `/cmd_vel/voice`, `/cmd_vel/stop`**
  (new mux inputs). Chassis subscribes only to mux output `/cmd_vel`.
- Existing producers remapped: chatbot chassis skill / exo bridge → `/cmd_vel/manual`;
  orchestrator stop → `/cmd_vel/stop`; F710 drive → `/cmd_vel/manual`, F710
  hard-stop button → `/cmd_vel/stop`.

**Fail-closed everywhere:** any missing/stale field (no depth, stale target,
missing obstacle stamp) resolves to *stop*, never to *proceed*.

## 13. Codex review — blockers and resolutions

| # | Codex blocker | Resolution in this design |
|---|---------------|---------------------------|
| 1 | Follow publishing `/cmd_vel` directly fights ≥3 existing producers (incl. exo bridge @50 Hz). | **`twist_mux`** arbitration; follow never touches chassis `/cmd_vel` directly (§4, §10). |
| 2 | Spatial-only lock under-scoped for "keep the right person." | Real tracker (IDs + Kalman + gating) with **stop-on-ambiguity** contract (§5). |
| 3 | On-demand depth via latched topic is unimplementable (depth set at pipeline startup). | Depth on for the **whole session** + **depth-ready handshake** before motion (§7). |
| 4 | Voice/UI stop is not a real e-stop. | **Gamepad hard-stop** (top priority) **+ demo caps** (§6.2, §10). |

MAJOR/MINOR folded in: richer stamped message (§12); obstacle depth = weak brake +
fail-closed (§8); bounded rotate-search caps (§9); flip_180 sign test (§6.3); mux
timeout ≪ chassis watchdog (§10); voice routed via orchestrator bridge (§4);
explicit UI states (§11); `vy` interface preserved (§6).

## 14. Testing strategy

**Off-robot unit tests (pure modules — no ROS):**
- Control law: bearing/distance error → `(vx, omega)`; cap clamping; ramp limits.
- Loss state machine: following→searching→stopped; rotate-search bounds; re-acquire.
- Ambiguity: two candidates in gate → `ambiguous` → controller stop.
- Tracker: assignment/gating, crossing → ambiguity, occlusion → Kalman predict → re-acquire.
- Fail-closed: stale depth / stale target / missing obstacle stamp → stop.

**Node/integration:**
- `twist_mux` priority ordering, per-input timeout, zero-on-handover, gamepad override,
  manual-cancels-follow.
- Depth-ready handshake gates motion.

**On-device bring-up runbook (like the health smoke-test):**
- **Mandatory flip_180 sign test before enabling motion.**
- Fall-detection FPS with depth on + follow active stays within budget.
- Scripted scenarios: single target follow; second person crosses → stop-on-ambiguity;
  target occluded → rotate-search → re-acquire / give up; each stop surface;
  gamepad hard-stop during motion.

## 15. Phasing

1. **Arbitration first:** introduce `twist_mux`, remap existing producers, verify no
   regression in current voice/gamepad driving. (De-risks everything else.)
2. **Perception target state:** tracker + 3D + obstacle corridor + `target_state`
   publish (no motion yet).
3. **`human_follow` control core:** pure module + node publishing `/cmd_vel/follow`;
   bench + sign test.
4. **Voice + UI + gamepad hard-stop** wiring.
5. **On-device bring-up** per §14 runbook; tune caps.

## 16. Future work (post-v1)

- Relax demo caps after field-proving.
- Lateral (`vy`) control for smoother holonomic following.
- Appearance re-ID for genuinely crowded spaces.
- English voice/TTS.
- Follow-through-doorways / corner anticipation.
- Richer obstacle sensing (downward/side coverage) if unsupervised operation is ever targeted.
