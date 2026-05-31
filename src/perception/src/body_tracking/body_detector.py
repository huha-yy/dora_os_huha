from ultralytics import YOLO
import numpy as np
import cv2
from tqdm import tqdm
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
import mediapipe as mp
from dataclasses import dataclass
from .landmarks import POSE_LANDMARKS, POSE_CONNECTIONS
import os
import logging
import math
from enum import Enum
from datetime import datetime
import threading
import time
from .state import (
    PoseDetectionResult,
    HumanPose,
    BoundingBox,
    FrameTrackingResult,
    HumanLandmarks,
)

logger = logging.getLogger(__name__)

# Configure logging format to include module name and line number at the beginning
if not logging.root.handlers:  # Only configure if logging hasn't been configured yet
    logging.basicConfig(
        level=logging.INFO, format="%(module)s:%(lineno)d - %(levelname)s - %(message)s"
    )



class BodyDetector:
    def __init__(
        self,
        detection_model_name: str = "yolo11n_rknn_model",
        pose_model_name: str = "pose_landmarker_lite.task",
        mode: str = "live_stream",
    ) -> None:
        # `detection_model_name` may be either:
        #   - a CPU PyTorch model file, e.g. "yolov8n.pt" (fallback), or
        #   - a Rockchip NPU model directory, e.g. "yolo11n_rknn_model"
        #     produced on an x86 host via `yolo export ... format=rknn name=rk3588`.
        # Ultralytics' AutoBackend detects the .rknn directory and runs it on the
        # RK3588 NPU via rknn-toolkit-lite2, so the rest of this class is unchanged.
        cwd = os.getcwd()
        detection_model_path = os.path.join(
            cwd, "src/perception/models", detection_model_name
        )
        if not os.path.exists(detection_model_path):
            logger.warning(
                "Detection model not found at %s; passing name directly to YOLO "
                "(it may auto-download the CPU weights).",
                detection_model_path,
            )
            detection_model_path = detection_model_name
        pose_model_path = os.path.join(cwd, "src/perception/models", pose_model_name)
        logger.info("Loading detection model: %s", detection_model_path)
        self.model = YOLO(detection_model_path, verbose=False)
        # Dictionary to store pose detection results from async callback, keyed by timestamp
        self.pose_results = {}
        self.result_lock = threading.Lock()
        self.current_timestamp_ms = 0

        # Define result callback for live stream mode
        def result_callback(result, output_image, timestamp_ms):
            """Callback function to handle pose detection results in live stream mode."""
            with self.result_lock:
                self.pose_results[timestamp_ms] = result

        base_options = python.BaseOptions(model_asset_path=pose_model_path)
        if mode == "live_stream":
            running_mode = vision.RunningMode.LIVE_STREAM
            res_callback = result_callback
        else:
            running_mode = vision.RunningMode.IMAGE
            res_callback = None
        self.mode = mode  # Store mode for later use
        options = vision.PoseLandmarkerOptions(
            base_options=base_options,
            running_mode=running_mode,
            min_pose_detection_confidence=0.5,
            min_pose_presence_confidence=0.5,
            min_tracking_confidence=0.5,
            result_callback=res_callback,
        )
        self.pose_landmarker = vision.PoseLandmarker.create_from_options(options)

    def draw_pose(
        self,
        image: np.ndarray,
        landmarks: np.ndarray,
        pose_detection_result: PoseDetectionResult | None = None,
    ) -> None:
        h, w, _ = image.shape

        # Draw keypoints
        for lm in landmarks:
            x = int(lm.x * w)
            y = int(lm.y * h)
            cv2.circle(image, (x, y), 3, (0, 255, 0), -1)

        # Draw skeleton
        for a, b in POSE_CONNECTIONS:
            x1 = int(landmarks[a].x * w)
            y1 = int(landmarks[a].y * h)
            x2 = int(landmarks[b].x * w)
            y2 = int(landmarks[b].y * h)
            cv2.line(image, (x1, y1), (x2, y2), (255, 0, 0), 2)

        if pose_detection_result is not None:
            text_items = [
                (f"Raw Pose: {pose_detection_result.raw_pose.value}", 30),
                (f"Pose: {pose_detection_result.pose.value}", 55),
                (f"MP Pose: {pose_detection_result.mp_pose.value}", 80),
                (f"Bbox Pose: {pose_detection_result.bbox_pose.value}", 105),
                (f"Torso Angle: {pose_detection_result.torso_angle}", 130),
                (f"Bbox Aspect Ratio: {pose_detection_result.bbox_aspect_ratio}", 150),
            ]
            for text, y_pos in text_items:
                cv2.putText(
                    image,
                    text,
                    (10, y_pos),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 255, 0),
                    2,
                )

    def load_test_video(self):
        self.tracking_results = []
        cap = cv2.VideoCapture("/home/frank/data/fall_detection/in_video.mp4")
        fps = int(cap.get(cv2.CAP_PROP_FPS))
        print(f"fps: {fps}")
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        print(f"fps: {fps}, width: {width}, height: {height}")
        out = cv2.VideoWriter(
            "/home/frank/data/fall_detection/tracking_video_with_pose.mp4",
            cv2.VideoWriter_fourcc(*"mp4v"),
            fps,
            (width, height),
        )
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        timestamp = 0
        frame_time_delta = 1.0 / fps

        for _ in tqdm(range(total_frames)):
            ret, frame = cap.read()
            if not ret:
                break
            frame_tracking_result = self.detect(frame, debug=True)
            frame_tracking_result.timestamp = timestamp
            vertical_speed = self.vertical_speed_calculation(frame_tracking_result)
            frame_out = (
                frame_tracking_result.debug_frame
                if frame_tracking_result.debug_frame is not None
                else frame
            )
            # Ensure 3-channel BGR for writer
            if len(frame_out.shape) == 2:
                frame_out = cv2.cvtColor(frame_out, cv2.COLOR_GRAY2BGR)
            cv2.putText(
                frame_out,
                f"Vertical Speed: {vertical_speed:.2f}",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.0,
                (0, 255, 0),
                2,
                cv2.LINE_AA,
            )
            out.write(frame_out)
            timestamp += frame_time_delta
            frame_tracking_result.debug_frame = None
            self.tracking_results.append(frame_tracking_result)
        cap.release()
        out.release()

    def detect(
        self,
        frame: np.ndarray,
        frame_timestamp_ms: int,
        debug: bool = False,
        print_fps: bool = False,
    ) -> FrameTrackingResult:
        # TODO: add person tracking
        if print_fps:
            start_time = datetime.now()
            results = self.model(frame, verbose=False)
            end_time = datetime.now()
            print(f"Detection time: {end_time - start_time}")
        else:
            results = self.model(frame, verbose=False)
        frame_tracking_result = FrameTrackingResult(human_poses=[], debug_frame=None)

        # Use provided frame timestamp (e.g., from ROS2 camera) or generate one
        # The timestamp is used both as a key for matching async results AND for MediaPipe's temporal tracking
        base_timestamp_ms = (
            frame_timestamp_ms
            if frame_timestamp_ms is not None
            else int(datetime.now().timestamp() * 1000)
        )

        for result in results:
            for bbox, cls in zip(result.boxes.xyxy, result.boxes.cls):
                if int(cls) != 0:  # 'person' class
                    continue
                x1, y1, x2, y2 = map(int, bbox)
                bounding_box = BoundingBox(x1, y1, x2, y2)
                person_box = frame[y1:y2, x1:x2]
                if person_box.size == 0:
                    continue

                rgb_person_box = cv2.cvtColor(person_box, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(
                    image_format=mp.ImageFormat.SRGB, data=rgb_person_box
                )

                # Use detect_async for live stream mode, detect for image mode
                if self.mode == "live_stream":
                    # Use a monotonic counter to ensure timestamps always increase
                    # MediaPipe requires monotonically increasing timestamps for async detection
                    start_time = datetime.now()
                    with self.result_lock:
                        self.current_timestamp_ms += 1
                        timestamp_ms = self.current_timestamp_ms
                    self.pose_landmarker.detect_async(mp_image, timestamp_ms)
                    # Wait for result from callback (polling with timeout)
                    tracking_result = None
                    max_wait_time = 1.0  # seconds
                    wait_start = datetime.now()
                    while tracking_result is None:
                        with self.result_lock:
                            if timestamp_ms in self.pose_results:
                                tracking_result = self.pose_results.pop(timestamp_ms)
                                break
                        if (
                            datetime.now() - wait_start
                        ).total_seconds() > max_wait_time:
                            logger.warning(
                                f"Timeout waiting for pose detection result (timestamp: {timestamp_ms})"
                            )
                            break
                        time.sleep(0.001)  # Small sleep to avoid busy waiting
                    end_time = datetime.now()
                else:
                    # IMAGE mode: use synchronous detect
                    start_time = datetime.now()
                    tracking_result = self.pose_landmarker.detect(mp_image)
                    end_time = datetime.now()
                if print_fps:
                    print(f"Pose detection time: {end_time - start_time}")
                if tracking_result is not None and tracking_result.pose_landmarks:
                    landmarks = HumanLandmarks(tracking_result.pose_landmarks[0])
                    pose_detection_result = (
                        PoseDetectionResult.from_landmarks_and_bounding_box(
                            landmarks, bounding_box
                        )
                    )
                    human_pose = HumanPose(
                        bounding_box=bounding_box,
                        landmarks=landmarks,
                        pose_detection_result=pose_detection_result,
                        person_id=0,
                    )
                    frame_tracking_result.human_poses.append(human_pose)
                    if debug:
                        self.draw_pose(
                            person_box, landmarks.landmarks, pose_detection_result
                        )
                if debug:
                    frame[y1:y2, x1:x2] = person_box
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 0, 0), 2)
                    frame_tracking_result.debug_frame = frame
        return frame_tracking_result


if __name__ == "__main__":
    detector = BodyDetector()
    detector.load_test_video()
