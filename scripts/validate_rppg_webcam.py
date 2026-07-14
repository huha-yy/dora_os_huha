#!/usr/bin/env python3
"""Task 16a -- validate the rPPG pipeline against a REAL face on a webcam.

Every test so far exercises the pipeline against synthetic sine waves we generated
ourselves. A pipeline can pass all of them and still recover nothing but noise from
an actual human. This script answers the two questions that only a real face can:

  1. Does POS/CHROM recover a plausible resting heart rate from a real face?
  2. Does the motion gate actually fire when the subject moves?

It exercises the production path exactly as the perception node does --
FaceRoiExtractor -> roi_centroid + sample_mean_rgb -> RgbSample -> RPPGEstimator,
with the real quality gates -- but with no ROS and no RealSense, so it runs on any
dev machine with a webcam.

This is NOT the on-device FPS budget test (Task 16b). That needs the RK3588 and the
D415; x86 FPS numbers say nothing about the Pi.

Usage:
    PYTHONPATH= .venv/bin/python scripts/validate_rppg_webcam.py
    PYTHONPATH= .venv/bin/python scripts/validate_rppg_webcam.py --camera 2 --still 40

Sit facing the camera in even, steady lighting. Fill a decent part of the frame --
the gates require a face at least ~127 px wide, so lean in if it reports
`face_too_small`. Avoid a window or a flickering lamp behind you.
"""

import argparse
import os
import sys
import time
from collections import Counter

import cv2
import numpy as np

try:
    import pyrealsense2 as rs
except ImportError:
    rs = None

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "perception", "src"))

from body_tracking.health import (  # noqa: E402
    FAIL_CLOSED,
    HealthConfig,
    RgbSample,
    RPPGEstimator,
    chroma_drift_metric,
    evaluate_gates,
    illumination_metric,
    motion_metric,
)
from body_tracking.health.camera import lock_color_sensor  # noqa: E402
from body_tracking.health.roi import roi_centroid, roi_pixel_count, sample_mean_rgb  # noqa: E402
from body_tracking.health.roi_detector import FaceRoiExtractor  # noqa: E402


class WebcamSource:
    """A plain V4L2 webcam.

    Wrapped rather than used directly: `cv2.VideoCapture` is a C extension type and
    rejects arbitrary attributes, so `exposure_stable` cannot be stapled onto it.
    """

    def __init__(self, index: int, width: int = 640, height: int = 480):
        self.cap = cv2.VideoCapture(index)
        if not self.cap.isOpened():
            raise RuntimeError(f"cannot open /dev/video{index}")
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

        # BOTH controls, and both verified by reading back.
        #
        # Auto-WHITE-BALANCE is the one that matters most here and is the easiest to
        # forget: it re-mixes R/G/B while holding brightness roughly constant, which is
        # invisible to a luminance check and is exactly what POS/CHROM read. Locking
        # only auto-exposure and calling the camera "stable" would let this harness
        # validate a heart rate computed from AWB drift. Measured on the D415, that
        # drift reaches 7.5% against a ~1% pulse.
        # V4L2: exposure 1 == manual, 3 == auto.  auto_wb 0 == off, 1 == on.
        #
        # BOTH conditions are required: set() must report success AND the readback must
        # match. A readback alone fails OPEN for AUTO_WB, because OpenCV returns 0.0 for
        # an UNSUPPORTED property -- which is exactly the "off" value we want. A webcam
        # with no AWB control at all would then read back as successfully locked while
        # its white balance kept hunting.
        ae_locked = (self.cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1)
                     and self.cap.get(cv2.CAP_PROP_AUTO_EXPOSURE) == 1)
        awb_locked = (self.cap.set(cv2.CAP_PROP_AUTO_WB, 0)
                      and self.cap.get(cv2.CAP_PROP_AUTO_WB) == 0)

        self.exposure_stable = bool(ae_locked and awb_locked)
        self.lock_failures = [
            name for name, ok in (("auto_exposure", ae_locked), ("auto_white_balance", awb_locked))
            if not ok
        ]

    def read(self):
        return self.cap.read()

    def release(self):
        self.cap.release()


class RealSenseSource:
    """The production camera. Optionally locks AE/AWB, which is what a scan does.

    `exposure_stable` reports what ACTUALLY happened, never what we asked for. A lock
    we believe in but do not have is worse than no lock -- it would let this harness
    "validate" a heart rate the camera was busy corrupting. Fails closed.
    """

    def __init__(self, lock: bool = True, width: int = 640, height: int = 480, fps: int = 30):
        self.pipe = rs.pipeline()
        cfg = rs.config()
        cfg.enable_stream(rs.stream.color, width, height, rs.format.bgr8, fps)
        profile = self.pipe.start(cfg)
        sensor = next(s for s in profile.get_device().query_sensors()
                      if s.get_info(rs.camera_info.name) == "RGB Camera")
        self.exposure_stable = False
        if lock:
            result = lock_color_sensor(sensor, rs.option.enable_auto_exposure,
                                       rs.option.enable_auto_white_balance)
            self.exposure_stable = result.locked
            if not result.locked:
                print(f"  CAMERA LOCK FAILED: {result.failures}")
                print("  -> exposure_stable=False; readings will be WITHHELD. "
                      "This run cannot validate anything.")
        else:
            sensor.set_option(rs.option.enable_auto_exposure, 1)
            sensor.set_option(rs.option.enable_auto_white_balance, 1)
            print("  --no-lock: AE/AWB left on AUTO. exposure_stable=False, so readings "
                  "are WITHHELD by design.\n  This mode exists to SHOW that auto is "
                  "unusable -- watch chroma_drift, not the HR.")

    def read(self):
        frame = self.pipe.wait_for_frames().get_color_frame()
        if not frame:
            return False, None
        return True, np.asanyarray(frame.get_data())

    def release(self):
        self.pipe.stop()


def _gate_components(rppg, cfg, now, have_face, face_px, roi_px, exposure_stable):
    """Mirror of BodyTrackingNode._on_health_timer. Keep the two in step."""
    win = rppg.window(now, cfg.ambient_window_s)
    fps = rppg.effective_fps(now, cfg.ambient_window_s)
    motion = motion_metric(win)
    illum = illumination_metric(win)
    chroma = chroma_drift_metric(win)
    if len(win) >= 2:
        intervals = np.diff([s.t for s in win])
        jitter_ms = float(np.std(intervals)) * 1000.0 if len(intervals) > 1 else 0.0
        expected = int(fps * cfg.ambient_window_s) if fps > 0 else len(win)
        drop_ratio = max(0.0, 1.0 - len(win) / max(expected, 1))
    else:
        drop_ratio, jitter_ms = 0.0, 0.0
    return {
        "face_present": have_face,
        "single_target": have_face,
        "roi_in_bounds": have_face,
        "face_px": face_px,
        "roi_px": roi_px,
        "effective_fps": fps,
        "drop_ratio": drop_ratio,
        "jitter_ms": jitter_ms,
        "motion": motion,
        "illum_delta": illum,
        "chroma_drift": chroma,
        # The ACTUAL lock state, never an assumption. If the camera was not locked,
        # this harness must not be able to "validate" a reading taken while AE/AWB
        # were free to scramble the very ratios POS/CHROM read.
        "exposure_stable": exposure_stable,
    }


def run_phase(cap, extractor, rppg, cfg, seconds, label, banner):
    print(f"\n{'=' * 72}\n  {banner}\n{'=' * 72}")
    t_end = time.monotonic() + seconds
    last_print = 0.0
    reasons, hrs, confs, frame_costs = Counter(), [], [], []

    while time.monotonic() < t_end:
        ok, frame = cap.read()
        if not ok:
            print("  camera read failed"); break
        now = time.monotonic()

        t0 = time.perf_counter()
        roi = extractor.update(frame)
        have_face = roi is not None
        face_px = roi.face_px if have_face else 0
        roi_px = 0

        if have_face:
            mean = sample_mean_rgb(frame, roi)
            centroid = roi_centroid(roi)
            if mean is not None and centroid is not None:
                roi_px = roi_pixel_count(frame, roi)
                r, g, b = mean
                rppg.add_sample(RgbSample(t=now, r=r, g=g, b=b,
                                          cx=centroid[0], cy=centroid[1], w=float(face_px)))
        frame_costs.append((time.perf_counter() - t0) * 1000.0)

        comps = _gate_components(rppg, cfg, now, have_face, face_px, roi_px,
                                 getattr(cap, "exposure_stable", False))
        gate = evaluate_gates(comps, cfg.gates)
        est = rppg.estimate(now, cfg.ambient_window_s, gate_ok=gate.ok)

        reasons[gate.reason or "PASS"] += 1
        # Record confidence whenever the OTHER gates passed -- that is the population
        # the confidence gate is deciding on. (est is None-ish when the gate failed.)
        if gate.ok:
            confs.append(est.confidence)
            if est.hr_bpm is not None:
                hrs.append(est.hr_bpm)

        if now - last_print >= 1.0:
            last_print = now
            m = comps["motion"]
            i = comps["illum_delta"]
            c = comps["chroma_drift"]
            hr = f"{est.hr_bpm:5.1f}" if est.hr_bpm is not None else "  -- "
            conf = f"{est.confidence:.2f}" if est.hr_bpm is not None else " -- "
            print(
                f"  {t_end - now:4.0f}s left | fps {comps['effective_fps']:4.1f} "
                f"| face {face_px:3d}px roi {roi_px:5d} "
                f"| motion {'  n/a' if m >= FAIL_CLOSED else f'{m:6.3f}'} "
                f"| illum {'  n/a' if i >= FAIL_CLOSED else f'{i:6.3f}'} "
                f"| chroma {'  n/a' if c >= FAIL_CLOSED else f'{c:6.4f}'} "
                f"| HR {hr} ({conf}) | {gate.reason or 'PASS'}"
            )

    return {"label": label, "reasons": reasons, "hrs": hrs, "confs": confs,
            "cost_ms": float(np.mean(frame_costs)) if frame_costs else 0.0}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--camera", type=int, default=0)
    ap.add_argument("--realsense", action="store_true",
                    help="use the D415 (the production camera) instead of a webcam")
    ap.add_argument("--no-lock", action="store_true",
                    help="with --realsense, leave AE/AWB on AUTO -- the A/B comparison")
    ap.add_argument("--still", type=int, default=40, help="seconds of the sit-still phase")
    ap.add_argument("--motion", type=int, default=12, help="seconds of the move-your-head phase")
    args = ap.parse_args()

    if args.realsense:
        if rs is None:
            print("pyrealsense2 not installed")
            return 2
        cap = RealSenseSource(lock=not args.no_lock)
        print(f"source: RealSense D415  (AE/AWB {'LOCKED' if not args.no_lock else 'AUTO'})")
    else:
        try:
            cap = WebcamSource(args.camera)
        except RuntimeError as exc:
            print(exc)
            return 2
        print(f"source: /dev/video{args.camera} (webcam)  "
              f"AE+AWB lock {'OK' if cap.exposure_stable else 'FAILED -> readings withheld'}")
        if not cap.exposure_stable:
            print(f"  could not lock: {', '.join(cap.lock_failures)}")
            print("  A camera that will not hold its exposure AND white balance cannot give "
                  "a trustworthy reading. Use --realsense.")

    cfg = HealthConfig.default()
    extractor = FaceRoiExtractor()
    rppg = RPPGEstimator(cfg)

    print(f"backend={cfg.backend}  window={cfg.ambient_window_s}s  "
          f"gates: face>={cfg.gates.min_face_px}px roi>={cfg.gates.min_roi_px}px "
          f"fps>={cfg.gates.min_fps} motion<={cfg.gates.max_motion} "
          f"illum<={cfg.gates.max_illum_delta} conf>={cfg.gates.min_confidence}")

    still = run_phase(cap, extractor, rppg, cfg, args.still, "still",
                      f"PHASE 1 ({args.still}s) -- SIT STILL, face the camera, breathe normally")
    moving = run_phase(cap, extractor, rppg, cfg, args.motion, "moving",
                       f"PHASE 2 ({args.motion}s) -- NOW MOVE YOUR HEAD around, keep it up")
    cap.release()

    print(f"\n{'=' * 72}\n  RESULT\n{'=' * 72}")
    print(f"  per-frame CPU cost (x86, NOT the Pi): {still['cost_ms']:.1f} ms\n")

    hrs = still["hrs"]
    ok_still = False
    if hrs:
        arr = np.array(hrs)
        stable = float(np.std(arr))
        print(f"  PHASE 1: {len(hrs)} readings passed the gates")
        print(f"           HR  median {np.median(arr):.1f} bpm   "
              f"mean {arr.mean():.1f}   spread (std) {stable:.1f}   "
              f"range {arr.min():.0f}-{arr.max():.0f}")
        plausible = 45.0 <= float(np.median(arr)) <= 110.0
        ok_still = plausible and stable < 8.0
        print(f"           plausible resting HR (45-110)?  {'YES' if plausible else 'NO'}")
        print(f"           stable (std < 8 bpm)?           {'YES' if stable < 8.0 else 'NO'}")
    else:
        print("  PHASE 1: NO readings passed the gates. Why they were withheld:")
        for reason, n in still["reasons"].most_common():
            print(f"           {n:5d}x  {reason}")

    # The confidence distribution is the whole ballgame. Synthetic pure noise scores
    # up to ~0.64 (p99) and an ordinary 1% pulse scores ~0.85+, which is why the gate
    # sits at min_confidence. What we do NOT know until this script runs is where a
    # REAL face lands. If real confidence clusters below the gate, the gate is too
    # strict for this camera and lighting; if it sits in the noise band, the reading
    # is not trustworthy no matter what number it prints.
    confs = np.array(still["confs"]) if still["confs"] else np.array([])
    print()
    if confs.size:
        print(f"  CONFIDENCE on a real face (gate = {cfg.gates.min_confidence}):")
        print(f"           median {np.median(confs):.3f}   p05 {np.percentile(confs, 5):.3f}   "
              f"max {confs.max():.3f}")
        print(f"           cleared the gate: {100.0 * (confs >= cfg.gates.min_confidence).mean():.0f}% "
              f"of windows")
        print(f"           for scale -- synthetic noise p99 ~0.64, a clean 1% pulse ~0.85+")
    else:
        print("  CONFIDENCE: no windows produced an estimate at all.")

    moved_rejected = moving["reasons"].get("head_motion", 0)
    total_moving = sum(moving["reasons"].values()) or 1
    pct = 100.0 * moved_rejected / total_moving
    print(f"\n  PHASE 2: motion gate fired on {moved_rejected}/{total_moving} frames ({pct:.0f}%)")
    for reason, n in moving["reasons"].most_common():
        print(f"           {n:5d}x  {reason}")
    ok_motion = pct >= 50.0
    print(f"           motion gate actually rejects movement?  {'YES' if ok_motion else 'NO'}")

    print()
    if ok_still and ok_motion:
        print("  VERDICT: PASS -- recovers a plausible pulse, and rejects motion.")
        rc = 0
    else:
        print("  VERDICT: NOT PROVEN. Read the withheld-reasons above before trusting this.")
        print("           Common fixes: sit closer (face_too_small / roi_too_small),")
        print("           steadier light (illumination_change), hold still (head_motion).")
        rc = 1
    print(f"{'=' * 72}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
