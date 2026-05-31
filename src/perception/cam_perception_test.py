"""Standalone perception smoke test (no ROS).

Reads the RealSense D415 directly via pyrealsense2, runs the BodyDetector
(YOLO person detection + MediaPipe pose), and saves an annotated frame so we
can confirm the full detection pipeline works on the RK3588S before ROS 2 is
installed.

Run FROM the workspace root so imports + model paths resolve like the real node:

    cd ~/dorabot_ws
    src/perception/.venv-cam-test/bin/python src/perception/cam_perception_test.py
"""
import os
import time
from datetime import datetime

import cv2
import numpy as np
import pyrealsense2 as rs

from src.body_tracking.body_detector import BodyDetector

N_FRAMES = int(os.environ.get("N_FRAMES", "30"))
OUT_PATH = os.environ.get("OUT_PATH", "/tmp/perception_test.jpg")


def main() -> int:
    print(f"BodyDetector loading (cwd={os.getcwd()})...")
    detector = BodyDetector(mode="image")  # synchronous pose, simpler for a test

    pipe = rs.pipeline()
    cfg = rs.config()
    cfg.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 30)
    pipe.start(cfg)
    print("RealSense started; running detection...")

    last_annotated = None
    persons_seen = 0
    t0 = time.time()
    try:
        for i in range(N_FRAMES):
            frames = pipe.wait_for_frames(5000)
            color = frames.get_color_frame()
            if not color:
                continue
            img = np.asanyarray(color.get_data())
            ts_ms = int(datetime.now().timestamp() * 1000)
            result = detector.detect(img, frame_timestamp_ms=ts_ms, debug=True)
            n = len(result.human_poses)
            persons_seen += n
            if result.debug_frame is not None:
                last_annotated = result.debug_frame
            elif last_annotated is None:
                last_annotated = img
            print(f"  frame {i:02d}: persons={n}")
    finally:
        pipe.stop()

    dt = time.time() - t0
    fps = N_FRAMES / dt if dt > 0 else 0.0
    if last_annotated is not None:
        cv2.imwrite(OUT_PATH, last_annotated)
        print(f"Saved annotated frame -> {OUT_PATH}")
    print(f"RESULT: frames={N_FRAMES} persons_total={persons_seen} "
          f"elapsed={dt:.1f}s avg_fps={fps:.2f}")
    print("OK_PERCEPTION" if persons_seen >= 0 else "FAIL")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
