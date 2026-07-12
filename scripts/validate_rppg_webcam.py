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

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "perception", "src"))

from body_tracking.health import (  # noqa: E402
    FAIL_CLOSED,
    HealthConfig,
    RgbSample,
    RPPGEstimator,
    evaluate_gates,
    illumination_metric,
    motion_metric,
)
from body_tracking.health.roi import roi_centroid, roi_pixel_count, sample_mean_rgb  # noqa: E402
from body_tracking.health.roi_detector import FaceRoiExtractor  # noqa: E402


def _gate_components(rppg, cfg, now, have_face, face_px, roi_px):
    """Mirror of BodyTrackingNode._on_health_timer. Keep the two in step."""
    win = rppg.window(now, cfg.ambient_window_s)
    fps = rppg.effective_fps(now, cfg.ambient_window_s)
    motion = motion_metric(win)
    illum = illumination_metric(win)
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
        "exposure_stable": True,  # Task 16b: the real RealSense lock
    }


def run_phase(cap, extractor, rppg, cfg, seconds, label, banner):
    print(f"\n{'=' * 72}\n  {banner}\n{'=' * 72}")
    t_end = time.monotonic() + seconds
    last_print = 0.0
    reasons, hrs, frame_costs = Counter(), [], []

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

        comps = _gate_components(rppg, cfg, now, have_face, face_px, roi_px)
        gate = evaluate_gates(comps, cfg.gates)
        est = rppg.estimate(now, cfg.ambient_window_s, gate_ok=gate.ok)

        reasons[gate.reason or "PASS"] += 1
        if gate.ok and est.hr_bpm is not None:
            hrs.append(est.hr_bpm)

        if now - last_print >= 1.0:
            last_print = now
            m = comps["motion"]
            i = comps["illum_delta"]
            hr = f"{est.hr_bpm:5.1f}" if est.hr_bpm is not None else "  -- "
            conf = f"{est.confidence:.2f}" if est.hr_bpm is not None else " -- "
            print(
                f"  {t_end - now:4.0f}s left | fps {comps['effective_fps']:4.1f} "
                f"| face {face_px:3d}px roi {roi_px:5d} "
                f"| motion {'  n/a' if m >= FAIL_CLOSED else f'{m:6.3f}'} "
                f"| illum {'  n/a' if i >= FAIL_CLOSED else f'{i:6.3f}'} "
                f"| HR {hr} ({conf}) | {gate.reason or 'PASS'}"
            )

    return {"label": label, "reasons": reasons, "hrs": hrs,
            "cost_ms": float(np.mean(frame_costs)) if frame_costs else 0.0}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--camera", type=int, default=0)
    ap.add_argument("--still", type=int, default=40, help="seconds of the sit-still phase")
    ap.add_argument("--motion", type=int, default=12, help="seconds of the move-your-head phase")
    args = ap.parse_args()

    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        print(f"cannot open /dev/video{args.camera}")
        return 2
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

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
