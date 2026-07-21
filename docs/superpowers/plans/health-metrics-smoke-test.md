# On-device smoke test — camera health metrics (Task 16b)

## Run 1 results — 2026-07-18 (Orange Pi 5, D415, health branch on `health-test-16b`)

Driven remotely over SSH; `main` on the Pi left untouched (health applied on a throwaway
branch, which was clean — the "6-month divergence" was git-history reshaping only; the
Pi's actual working files were byte-identical to the branch base, so the 45-file health
patch applied with zero conflicts).

- **Health core on aarch64:** ✅ POS recovered 72.1 bpm from a synthetic pulse
  (conf 1.00); MediaPipe FaceRoiExtractor constructs. numpy 1.26.4 / scipy 1.15.3 /
  mediapipe 0.10.18 present in the Pi venv.
- **Camera-lock round-trip (16c) on real hardware:** ✅ idle `auto:true` → scan start
  `locked:true` with both `auto_exposure_off` and `auto_white_balance_off` verified →
  "camera lock ENGAGED" logged → cancel restores `auto:true`. Exposure confirmed back to
  auto after shutdown (clean release).
- **FPS budget — ⚠️ OVER BUDGET, decision gate fired.** Fall-detection "Detect FPS",
  steady state (warm-up trimmed), vision-only launch (camera + perception, no nav/chatbot):

  | | median | mean | frac < 10 fps |
  |---|---|---|---|
  | health OFF | **14.9** | 13.8 | 21% |
  | health ON  | **9.9** | 11.1 | 56% |

  **Drop: 34% median / 19% mean — both exceed the 15% budget.** The extra per-frame
  MediaPipe *face* detector (`FaceRoiExtractor`) is too expensive on the RK3588.

  **DECISION:** switch to the pose-only ROI fallback. `roi_from_pose` (Task 8) exists but
  is **not yet wired** into `body_tracking_node.py` — the node always calls
  `FaceRoiExtractor`. Next task: in `_update_health_roi`, when
  `HealthConfig.detector == "pose_fallback"`, derive the face ROI from the pose landmarks
  already computed for fall detection (nose/eyes) instead of running a second detector,
  then re-measure on device.

  **RESOLVED (2026-07-19):** pose-only ROI fallback wired (`pose_face_roi`, default
  `detector=pose_fallback`) and re-measured on the Pi:

  | | median | mean | frac < 10 fps |
  |---|---|---|---|
  | health OFF | 14.9 | 13.0 | 25% |
  | health ON (pose_fallback) | 14.9 | 12.2 | 31% |

  **Drop: 0% median / 6% mean — WITHIN the 15% budget** (was 34%/19% with the face
  detector). ✅ FPS budget met.
- **E2E scan reading:** not attempted this run (deferred lighting fix — an underexposed
  face is correctly withheld; see scope note below).

---


Run this on the **Orange Pi 5 (RK3588S) with the D415**. It validates the parts that
can only be tested on the real robot: the two-node camera-lock plumbing, the ROS topic
contract, and — the real decision gate — the fall-detection **FPS budget** with the
health feature on vs off.

> **Scope note — lighting/exposure is DEFERRED.** We found (Task 16a) that a backlit or
> dimly-lit face is underexposed (green ≈ 16/255), and the confidence gate correctly
> withholds those readings. The exposure fix (spot-meter the face before locking) is not
> built yet. So **do not expect a scan to COMPLETE with a heart rate** unless your face
> is well-lit and front-lit. That is expected, not a bug. This smoke test validates
> plumbing, safety, and FPS — not a successful reading. A completed scan is a bonus.

Fill in the `RESULT:` lines as you go and commit this file at the end.

---

## 0. Deploy the branch to the Pi

```bash
cd ~/dorabot_ws                     # the Pi's checkout
git fetch dora_os
git checkout feat/camera-health-metrics
git pull dora_os feat/camera-health-metrics
git log --oneline -1               # expect the tip of feat/camera-health-metrics
```

No new dependencies were added: `health/camera.py` is pure Python, the RealSense
publisher already uses `pyrealsense2`, perception already uses `mediapipe`/`cv2`. numpy
stays pinned `==1.26.4`.

- [ ] **RESULT:** branch tip commit on the Pi = `____________`

---

## 1. Unit suite on the Pi (fast sanity)

```bash
cd ~/dorabot_ws/src/perception && PYTHONPATH= <repo-venv>/bin/python -m pytest tests/ -q
```

- [ ] **RESULT:** ____ passed (expected 180)

---

## 2. Launch the stack (health ON)

```bash
cd ~/dorabot_ws
HEALTH_ENABLED=1 bash scripts/start_dorabot.sh
```

Watch the logs for, in order:
- `RealSense started: Intel RealSense D415 ...`
- `Health metrics (rPPG) enabled`
- no `ModuleNotFoundError` from `run_camera.py` (the camera node imports
  `body_tracking.health.camera` via a sys.path shim — confirm it starts clean).

- [ ] **RESULT:** stack up, health enabled, camera node clean? ____

---

## 3. Topics publish (new SSH shell)

```bash
source /opt/ros/humble/setup.bash
ros2 topic list | grep health
# expect: /health/metrics  /health/scan_cmd  /health/camera_lock  /health/camera_lock_state

ros2 topic echo /health/metrics --once
```

Expected in `/health/metrics`: `schema_version: 1`, `state: "idle"`, `hr_bpm` a number
or `null`, and the always-null `resp_bpm` / `hrv_sdnn_ms` / `spo2_pct`.

```bash
ros2 topic echo /health/camera_lock_state --once   # latched: returns immediately
# expect JSON with "locked": false (AUTO at idle) and "auto": true
```

- [ ] **RESULT:** all four topics present? ____   idle metrics well-formed? ____   lock_state locked=false at idle? ____

---

## 4. Camera-lock round-trip on real hardware (the 16c payoff)

Start a scan and watch the RealSense publisher's log:

```bash
curl -s -X POST localhost:8002/health/scan -H 'content-type: application/json' -d '{"window_s":30}'
```

Expected, within ~1–2s:
- publisher logs `camera lock ENGAGED`
- `ros2 topic echo /health/camera_lock_state --once` now shows `"locked": true`,
  `"auto_exposure_off": true`, `"auto_white_balance_off": true`

Then cancel (or let it finish) and confirm release:

```bash
curl -s -X POST localhost:8002/health/scan/cancel
# publisher logs "camera lock released"; lock_state -> locked:false, auto:true
```

Also test the **dead-man's lease**: start a scan, then kill the perception node
(`pkill -f body_tracking`). Within ~3s the publisher should log
`camera lock lease expired ... restoring auto` and lock_state should go back to
`auto:true` — the shared stream must never be left locked.

- [ ] **RESULT:** lock engages on scan? ____   releases on cancel? ____   lease restores auto after perception dies? ____

---

## 5. FPS budget — THE decision gate

The MediaPipe face detector runs on the CPU in the perception node. If it costs too much
of the fall-detection frame rate, we must switch to the pose-only ROI fallback.

Enable FPS printing (set `perception.print_fps: true` in `configs/orchestrator/config.yaml`,
or run the perception node directly with `--print-fps`). Measure **"Detect FPS"** in the
perception log, steady-state, in two conditions:

```bash
# A) health ON
HEALTH_ENABLED=1 bash scripts/start_dorabot.sh      # note steady-state "Detect FPS"

# B) health OFF (baseline)
HEALTH_ENABLED=0 bash scripts/start_dorabot.sh      # note steady-state "Detect FPS"
```

- [ ] **RESULT A (health ON):** Detect FPS = ______
- [ ] **RESULT B (health OFF):** Detect FPS = ______
- [ ] **Drop = (B − A) / B = ______ %**

**Decision rule:** if enabling health drops Detect FPS by **more than ~15%**, switch to
the pose-only ROI path — feed `roi_from_pose` (Task 8, already built) from the existing
pose landmarks in `_sample_health_roi` instead of `FaceRoiExtractor`, and re-measure.
Set `HealthConfig.detector = "pose_fallback"`.

- [ ] **RESULT:** within budget (drop ≤ 15%)? ____   if not, pose-fallback re-measured Detect FPS = ______

---

## 6. End-to-end scan via HTTP (bonus — needs good lighting)

Only expected to COMPLETE if your face is well-lit and front-lit (see the scope note).
Otherwise it will (correctly) withhold and eventually FAIL/timeout at 90s — record which.

```bash
curl -s -X POST localhost:8002/health/scan -H 'content-type: application/json' -d '{"window_s":30}'
# hold still, face a light source, ~30s, then:
curl -s localhost:8002/health/scan/status | python3 -m json.tool
```

- [ ] **RESULT:** state reached = ______ (warming/collecting/insufficient_quality/complete/failed)
- [ ] if complete: hr_bpm = ______   ; if not: withhold reason(s) = ______ (e.g. low confidence from underexposure — expected until the lighting fix)

---

## 7. Record & commit

Fill in the RESULT lines above, note anything surprising, then:

```bash
git add docs/superpowers/plans/health-metrics-smoke-test.md
git commit -m "docs: record on-device rPPG smoke test and FPS budget results"
```

**Report back:** the FPS drop % (the number that decides pose-fallback), whether the lock
round-trip and lease worked on hardware, and any crash/import surprise the split dev-box
env could not catch.
