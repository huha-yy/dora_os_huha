#!/usr/bin/env python3
import os
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from std_msgs.msg import String
from geometry_msgs.msg import Point
from cv_bridge import CvBridge
import cv2
from rclpy.time import Time
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
import click
import numpy as np
from tqdm import tqdm
from .body_detector import BodyDetector
from .health import (
    RPPGEstimator, ScanController, HealthConfig, RgbSample, ScanState, build_metrics,
    describe_complexion, evaluate_gates,
)
from .health.roi_detector import FaceRoiExtractor
from .health.roi import sample_mean_rgb, roi_pixel_count
from .state import FrameTrackingResult, RawPose, HumanStatus
from collections import deque
import logging
import json
import uuid
from datetime import datetime

logger = logging.getLogger(__name__)

# Configure logging format to include module name and line number at the beginning
if not logging.root.handlers:  # Only configure if logging hasn't been configured yet
    logging.basicConfig(
        level=logging.INFO, format="%(module)s:%(lineno)d - %(levelname)s - %(message)s"
    )

FALL_EVENT_NONE = "fall_event_none"
FALL_EVENT_FALLING_CANDIDATE = "falling_candidate"
FALL_EVENT_FALLEN = "fallen"


class BodyTrackingNode(Node):
    def __init__(
        self,
        detection_model_name: str = "yolo11n_rknn_model",
        pose_model_name: str = "pose_landmarker_lite.task",
        print_fps: bool = False,
        process_every_n: int = 1,
        debug_video_path: str | None = None,
        real_time_view: bool = False,
        mock_fall_detection: bool = False,
        publish_annotated: bool = True,
    ):
        super().__init__("body_tracking")

        self.bridge = CvBridge()
        self.publish_annotated = publish_annotated
        if debug_video_path is not None:
            running_mode = "image"
        else:
            running_mode = "live_stream"
        self.body_detector = BodyDetector(
            detection_model_name=detection_model_name,
            pose_model_name=pose_model_name,
            mode=running_mode,
        )
        self.fps = 30.0
        self.video_writer = None
        self.debug_video_path = debug_video_path
        self.debug: bool = False
        self.real_time_view = real_time_view
        if self.debug_video_path is not None:
            os.makedirs(os.path.dirname(self.debug_video_path), exist_ok=True)
            self.debug = True
        # Subscribe to camera. Sensor-data (BEST_EFFORT) QoS to match the
        # RealSense publisher; a RELIABLE subscriber would receive nothing from
        # a BEST_EFFORT image publisher.
        camera_qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
        )
        self.image_sub = self.create_subscription(
            Image,
            "/camera/camera/color/image_raw",
            self.image_callback,
            camera_qos,
        )
        self.last_timestamp = 0
        self.detection_model_name = detection_model_name
        self.print_fps = print_fps
        self.process_every_n = max(1, process_every_n)
        self._frame_counter = 0
        self._last_annotated: np.ndarray | None = None
        self._last_fall_msg: String | None = None
        self._last_detect_timestamp = 0

        # Publisher: fall_event
        self.fall_pub = self.create_publisher(String, "/fall_event", 10)

        # Publisher: person_detection (placeholder)
        self.person_pub = self.create_publisher(Point, "/person_detection", 10)

        # Publisher: annotated frames for the live UI (bbox + skeleton + status).
        # Best-effort QoS keeps latency low for video streaming.
        self.annotated_pub = None
        if self.publish_annotated:
            annotated_qos = QoSProfile(
                reliability=ReliabilityPolicy.BEST_EFFORT,
                history=HistoryPolicy.KEEP_LAST,
                depth=2,
            )
            self.annotated_pub = self.create_publisher(
                Image, "/body_tracking/image_annotated", annotated_qos
            )

        self.tracking_results = deque(maxlen=int(self.fps * 10))
        self.last_human_status = HumanStatus.create_dummy()
        self.node_up_time = datetime.now().timestamp()
        self.mock_fall_detection = mock_fall_detection
        # --- Health metrics (rPPG) ---
        self.health_config = HealthConfig.default()
        self._health_last_roi = None
        self._health_last_mean = None
        self._health_roi_age = 999
        self._health_last_frame_t = 0.0
        self._health_scan_result = None
        self._health_last_scan_state = None
        if self.health_config.enabled:
            self._roi_extractor = FaceRoiExtractor()
            self._rppg = RPPGEstimator(self.health_config)
            self._scan = ScanController(
                target_clean_s=self.health_config.scan_window_s,
                timeout_s=self.health_config.scan_timeout_s,
            )
            self.health_pub = self.create_publisher(String, "/health/metrics", 10)
            self.scan_cmd_sub = self.create_subscription(
                String, "/health/scan_cmd", self._on_scan_cmd, 10
            )
            self.create_timer(1.0, self._on_health_timer)
            self.get_logger().info("Health metrics (rPPG) enabled")

        self.get_logger().info(
            "BodyTrackingNode started (process_every_n=%d), waiting for images..."
            % self.process_every_n
        )

    def _print_fps(self, stamp: Time, *, detect: bool = False):
        if not self.print_fps:
            return
        last = self._last_detect_timestamp if detect else self.last_timestamp
        if last <= 0:
            if detect:
                self._last_detect_timestamp = stamp.nanoseconds
            else:
                self.last_timestamp = stamp.nanoseconds
            return
        delta_time = stamp.nanoseconds - last
        if delta_time <= 0:
            return
        fps = 1e9 / delta_time
        label = "Detect FPS" if detect else "Camera FPS"
        print(f"{label}: {fps:.1f}")
        if detect:
            self._last_detect_timestamp = stamp.nanoseconds
        else:
            self.last_timestamp = stamp.nanoseconds

    def _print_human_status(
        self,
        tracking_result: FrameTrackingResult,
        cv_image: np.ndarray,
        timestamp: float,
    ):
        text_items = [
            (f"Vertical Speed: {tracking_result.vertical_speed:.2f}", 40),
            (
                f"Is Falling Candidate: {self.last_human_status.is_falling_candidate}",
                80,
            ),
            (f"Is Fallen: {self.last_human_status.is_fallen}", 120),
            (f"Timestamp: {timestamp:.6f}s", 160),
        ]
        for text, y_pos in text_items:
            cv2.putText(
                cv_image,
                text,
                (20, y_pos),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.0,
                (0, 255, 0),
                2,
                cv2.LINE_AA,
            )

    def save_debug_video(
        self, tracking_result: FrameTrackingResult | None, cv_image: np.ndarray
    ):
        if self.debug_video_path is None:
            return
        height, width = cv_image.shape[:2]
        if self.video_writer is None:
            self.video_writer = cv2.VideoWriter(
                self.debug_video_path,
                cv2.VideoWriter_fourcc(*"mp4v"),
                self.fps,
                (width, height),
            )
            if not self.video_writer.isOpened():
                self.get_logger().error(
                    f"Failed to open VideoWriter at {self.output_video_path}"
                )
                self.video_writer = None
                return
        if tracking_result is not None:
            cv_image = tracking_result.debug_frame
            timestamp = tracking_result.timestamp
            self._print_human_status(tracking_result, cv_image, timestamp)
        self.video_writer.write(cv_image)

    def vertical_speed_calculation(self, tracking_result: FrameTrackingResult) -> float:
        # TODO: only support one person for now; convert to real world units
        if len(self.tracking_results) < 6:
            logger.debug("Not enough tracking results to calculate vertical speed")
            return 0.0
        if not tracking_result.has_human_poses:
            return 0.0
        previous_tracking_result = self.tracking_results[-5]
        if not previous_tracking_result.has_human_poses:
            return 0.0
        last_timestamp = tracking_result.timestamp
        first_timestamp = previous_tracking_result.timestamp
        time_delta = last_timestamp - first_timestamp
        vertical_speed = (
            tracking_result.human_poses[0].bbox_center.y
            - previous_tracking_result.human_poses[0].bbox_center.y
        ) / time_delta
        return vertical_speed

    def update_human_status(self, tracking_result: FrameTrackingResult) -> String:
        status = String()
        timestamp = datetime.now().timestamp()
        if not tracking_result.has_human_poses:
            status.data = json.dumps(
                {"status": FALL_EVENT_NONE, "timestamp": timestamp}
            )
            return status
        vertical_speed = self.vertical_speed_calculation(tracking_result)
        tracking_result.vertical_speed = vertical_speed
        human_pose = tracking_result.get_person_by_id(0)
        if human_pose.raw_pose == RawPose.UPRIGHT:
            # upright pose will reset the previous falling status
            self.last_human_status = HumanStatus(
                tracking_result=tracking_result,
                vertical_speed=vertical_speed,
                timestamp=tracking_result.timestamp,
            )
            status.data = json.dumps(
                {"status": FALL_EVENT_NONE, "timestamp": timestamp}
            )
            return status
        if human_pose.raw_pose == RawPose.HORIZONTAL:
            human_status = HumanStatus(
                tracking_result=tracking_result,
                vertical_speed=vertical_speed,
                timestamp=tracking_result.timestamp,
            )
            if human_status.is_dummy:
                # this condition should not happen now
                self.last_human_status = human_status
                status.data = json.dumps(
                    {"status": FALL_EVENT_NONE, "timestamp": timestamp}
                )
                return status
            if self.last_human_status.get_raw_pose() == RawPose.UPRIGHT:
                time_delta = (
                    tracking_result.timestamp - self.last_human_status.timestamp
                )
                if time_delta < 1.0:
                    # within 1 second from upright to horizontal, it is a falling candidate
                    human_status.is_falling_candidate = True
                    human_status.last_upright_timestamp = (
                        self.last_human_status.timestamp
                    )
                    human_status.first_laying_down_timestamp = tracking_result.timestamp
                    status.data = json.dumps(
                        {
                            "status": FALL_EVENT_FALLING_CANDIDATE,
                            "timestamp": timestamp,
                            "human_status": human_status.json,
                        }
                    )
                else:
                    human_status.is_falling_candidate = False
                    status.data = json.dumps(
                        {"status": FALL_EVENT_NONE, "timestamp": timestamp}
                    )
                self.last_human_status = human_status
                return status
            if self.last_human_status.get_raw_pose() == RawPose.HORIZONTAL:
                if self.last_human_status.is_falling_candidate:
                    time_delta = (
                        tracking_result.timestamp
                        - self.last_human_status.first_laying_down_timestamp
                    )
                    if time_delta > 10.0:  # laying down for more than 10 seconds
                        human_status.is_fallen = True
                        status.data = json.dumps(
                            {
                                "status": FALL_EVENT_FALLEN,
                                "timestamp": timestamp,
                                "human_status": human_status.json,
                            }
                        )
                    else:
                        status.data = json.dumps(
                            {
                                "status": FALL_EVENT_FALLING_CANDIDATE,
                                "timestamp": timestamp,
                                "human_status": human_status.json,
                            }
                        )
        return status

    def _publish_annotated(self, frame: np.ndarray, fall_msg: String) -> None:
        """Overlay the current fall status and publish the annotated frame."""
        if self.annotated_pub is None or frame is None:
            return
        try:
            status = json.loads(fall_msg.data or "{}").get("status", FALL_EVENT_NONE)
        except (ValueError, TypeError):
            status = FALL_EVENT_NONE

        banner = {
            FALL_EVENT_NONE: ("OK", (0, 180, 0)),
            FALL_EVENT_FALLING_CANDIDATE: ("FALL? (candidate)", (0, 165, 255)),
            FALL_EVENT_FALLEN: ("FALL DETECTED", (0, 0, 255)),
        }.get(status, ("OK", (0, 180, 0)))
        label, color = banner

        out = frame
        if out.ndim == 2:
            out = cv2.cvtColor(out, cv2.COLOR_GRAY2BGR)
        h, w = out.shape[:2]
        cv2.rectangle(out, (0, 0), (w, 28), color, -1)
        cv2.putText(
            out,
            f"Status: {label}",
            (8, 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
        try:
            annotated_msg = self.bridge.cv2_to_imgmsg(out, encoding="bgr8")
            self.annotated_pub.publish(annotated_msg)
        except Exception as exc:  # pragma: no cover - defensive
            self.get_logger().warn(f"Failed to publish annotated frame: {exc}")

    def _update_health_roi(self, frame: np.ndarray) -> None:
        roi = self._roi_extractor.update(frame)
        if roi is None:
            self._health_last_roi = None
            return
        self._health_last_roi = roi
        self._health_roi_age = 0

    def _sample_health_roi(self, frame: np.ndarray, t_sec: float) -> None:
        self._health_roi_age += 1
        if self._health_roi_age > self.process_every_n * 5:
            self._health_last_roi = None
        roi = self._health_last_roi
        if roi is None:
            self._health_last_mean = None
            return
        sample = sample_mean_rgb(frame, roi)
        if sample is None:
            self._health_last_mean = None
            return
        r, g, b = sample
        self._health_last_mean = (r, g, b, roi.face_px, roi_pixel_count(frame, roi))
        self._rppg.add_sample(RgbSample(t=t_sec, r=r, g=g, b=b))

    def _on_scan_cmd(self, msg: String) -> None:
        try:
            cmd = json.loads(msg.data or "{}")
        except (ValueError, TypeError):
            return
        if not isinstance(cmd, dict):
            return
        now = self.get_clock().now().nanoseconds / 1e9
        action = cmd.get("action")
        if action == "start":
            mid = cmd.get("measurement_id") or str(uuid.uuid4())
            self._scan.start(mid, now)
        elif action == "cancel":
            self._scan.cancel(now)

    def _on_health_timer(self) -> None:
        ros_now = self.get_clock().now().nanoseconds / 1e9

        have_face = self._health_last_roi is not None and self._health_last_mean is not None

        frame_age = ros_now - self._health_last_frame_t if self._health_last_frame_t > 0 else 99.0
        stale = frame_age > 5.0

        window_s = self.health_config.ambient_window_s
        if stale:
            fps = 0.0
            est = None
            have_face = False
            drop_ratio = 1.0
            jitter_ms = 999.0
        else:
            fps = self._rppg.effective_fps(self._health_last_frame_t, window_s)
            est = self._rppg.estimate(self._health_last_frame_t, window_s)
            win = self._rppg._buffer.window(self._health_last_frame_t, window_s)
            if len(win) >= 2:
                intervals = np.diff([s.t for s in win])
                jitter_ms = float(np.std(intervals)) * 1000.0 if len(intervals) > 1 else 0.0
                expected = int(fps * window_s) if fps > 0 else len(win)
                drop_ratio = max(0.0, 1.0 - len(win) / max(expected, 1))
            else:
                drop_ratio = 0.0
                jitter_ms = 0.0

        face_px = self._health_last_mean[3] if have_face else 0
        roi_px = self._health_last_mean[4] if have_face else 0
        components = {
            "face_present": have_face,
            "single_target": have_face,
            "roi_in_bounds": have_face,
            "face_px": face_px,
            "roi_px": roi_px,
            "effective_fps": fps,
            "drop_ratio": drop_ratio,
            "jitter_ms": jitter_ms,
            "motion": 0.0,
            "illum_delta": 0.0,
            "exposure_stable": True,
        }
        gate = evaluate_gates(components, self.health_config.gates)

        show_est = est if (gate.ok and est is not None) else None
        prev_state = self._scan.state
        self._scan.update(ros_now, gate.ok and est is not None and est.hr_bpm is not None)

        if self._scan.state == ScanState.COMPLETE and prev_state != ScanState.COMPLETE:
            self._health_scan_result = show_est

        _all_scan_states = {"warming", "collecting", "insufficient_quality", "complete", "failed", "cancelled"}
        mode = (
            "scan"
            if self._scan.measurement_id is not None
            and self._scan.state.value in _all_scan_states
            else "ambient"
        )

        publish_est = self._health_scan_result if self._scan.state == ScanState.COMPLETE else show_est

        complexion = None
        if self.health_config.complexion_enabled and have_face:
            complexion = describe_complexion(self._health_last_mean[:3])

        msg = String()
        msg.data = json.dumps(build_metrics(
            ts=ros_now, mode=mode, state=self._scan.state, effective_fps=fps,
            window_s=window_s, estimate=publish_est, quality_components=components,
            complexion=complexion, reason=gate.reason,
            scan_progress_s=self._scan.progress_clean_s,
            scan_target_s=self.health_config.scan_window_s,
        ))
        self.health_pub.publish(msg)

    def image_callback(self, msg: Image):
        cv_image = self.bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
        stamp = Time.from_msg(msg.header.stamp)
        self._print_fps(stamp)

        if getattr(self, "health_config", None) and self.health_config.enabled:
            self._health_last_frame_t = stamp.nanoseconds / 1e9
            self._sample_health_roi(cv_image, self._health_last_frame_t)

        self._frame_counter += 1
        if (
            self.process_every_n > 1
            and self._frame_counter % self.process_every_n != 0
        ):
            if self._last_annotated is not None and self._last_fall_msg is not None:
                self._publish_annotated(self._last_annotated, self._last_fall_msg)
            return

        # Draw overlays when we are saving a debug video OR streaming to the UI.
        draw_overlays = self.debug or self.publish_annotated

        tracking_result = self.body_detector.detect(
            cv_image,
            frame_timestamp_ms=int(stamp.nanoseconds / 1e6),
            debug=draw_overlays,
            print_fps=self.print_fps,
        )
        self._print_fps(stamp, detect=True)
        tracking_result.timestamp = stamp.nanoseconds / 1e9
        fall_msg = self.update_human_status(tracking_result)
        if self.debug:
            self.save_debug_video(tracking_result, cv_image)

        annotated = (
            tracking_result.debug_frame
            if tracking_result.debug_frame is not None
            else cv_image
        )
        if self.real_time_view:
            cv2.imshow("RealSense Color", annotated)
            cv2.waitKey(1)
        self._last_annotated = annotated
        self._last_fall_msg = fall_msg
        self._publish_annotated(annotated, fall_msg)

        if getattr(self, "health_config", None) and self.health_config.enabled:
            self._update_health_roi(cv_image)

        tracking_result.debug_frame = None
        self.tracking_results.append(tracking_result)
        # self.person_pub.publish(tracking_result)
        # TODO: add the real distance calculation
        detection = Point()
        detection.x = 1.0  # forward (meters)
        detection.y = 0.0  # left/right
        detection.z = 0.5  # height

        self.person_pub.publish(detection)

        # Fake fall flag for demonstration
        up_time = datetime.now().timestamp() - self.node_up_time
        if up_time > 1.0 and self.mock_fall_detection:
            logger.info("Mock fall detection triggered")
            fall_msg.data = json.dumps(
                {
                    "status": FALL_EVENT_FALLING_CANDIDATE,
                    "timestamp": datetime.now().timestamp(),
                }
            )
        self.fall_pub.publish(fall_msg)

        # Optional: tiny log
        self.get_logger().debug("Published detection and fall_event")

    def load_test_video(self):
        cap = cv2.VideoCapture("/home/frank/data/fall_detection/in_video.mp4")
        fps = int(cap.get(cv2.CAP_PROP_FPS))
        print(f"fps: {fps}")
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        print(f"fps: {fps}, width: {width}, height: {height}")
        out = cv2.VideoWriter(
            "/home/frank/data/fall_detection/tracking_video_with_local_test.mp4",
            cv2.VideoWriter_fourcc(*"mp4v"),
            fps,
            (width, height),
        )
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        timestamp = 0
        frame_time_delta = 1.0 / fps

        for _ in tqdm(range(total_frames)):
            ret, cv_image = cap.read()
            if not ret:
                break
            frame_tracking_result = self.body_detector.detect(cv_image, debug=True)
            frame_tracking_result.timestamp = timestamp
            self.update_human_status(frame_tracking_result)
            frame_out = (
                frame_tracking_result.debug_frame
                if frame_tracking_result.debug_frame is not None
                else cv_image
            )
            self._print_human_status(frame_tracking_result, frame_out, timestamp)
            # Ensure 3-channel BGR for writer
            if len(frame_out.shape) == 2:
                frame_out = cv2.cvtColor(frame_out, cv2.COLOR_GRAY2BGR)
            out.write(frame_out)
            timestamp += frame_time_delta
            frame_tracking_result.debug_frame = None
            self.tracking_results.append(frame_tracking_result)
        cap.release()
        out.release()

    def destroy_node(self):
        if self.video_writer is not None:
            self.video_writer.release()
        super().destroy_node()


@click.command()
@click.option("--detection_model_name", type=str, default="yolo11n_rknn_model")
@click.option("--pose-model-name", type=str, default="pose_landmarker_lite.task")
@click.option("--print-fps", is_flag=True, default=False)
@click.option("--process-every-n", type=int, default=1, show_default=True)
@click.option("--debug-video-path", type=str, default=None)
@click.option("--real-time-view", is_flag=True, default=False)
@click.option("--load-test-video", is_flag=True, default=False)
@click.option("--mock-fall-detection", is_flag=True, default=False)
@click.option("--publish-annotated/--no-publish-annotated", default=True)
def main(
    detection_model_name: str = "yolo11n_rknn_model",
    pose_model_name: str = "pose_landmarker_lite.task",
    print_fps: bool = False,
    process_every_n: int = 1,
    debug_video_path: str | None = None,
    real_time_view: bool = False,
    load_test_video: bool = False,
    mock_fall_detection: bool = False,
    publish_annotated: bool = True,
):
    rclpy.init(args=None)
    node = BodyTrackingNode(
        detection_model_name=detection_model_name,
        pose_model_name=pose_model_name,
        print_fps=print_fps,
        process_every_n=process_every_n,
        debug_video_path=debug_video_path,
        real_time_view=real_time_view,
        mock_fall_detection=mock_fall_detection,
        publish_annotated=publish_annotated,
    )
    if load_test_video:
        node.load_test_video()
        return
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    except Exception as exc:
        # ROS may already be shutting down when the orchestrator stops sibling services.
        if exc.__class__.__name__ != "ExternalShutdownException":
            raise
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
