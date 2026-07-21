#!/usr/bin/env python3
"""Lightweight RealSense -> ROS 2 publisher backed by pyrealsense2.

This replaces the heavy `realsense2_camera` ROS wrapper (which has no arm64
apt binary and requires a long librealsense source build). It uses the
pyrealsense2 pip wheel — already verified working on the D415 — and publishes
to the same topic names the perception node and the rest of the stack expect:

    /camera/camera/color/image_raw            sensor_msgs/Image  (bgr8)
    /camera/camera/color/camera_info          sensor_msgs/CameraInfo
    /camera/camera/aligned_depth_to_color/image_raw   sensor_msgs/Image (16UC1)

The depth stream and alignment are optional (off by default to save CPU on the
RK3588S; enable with --enable-depth for mapping / 3D localization).
"""
import json
import logging
import os
import sys

import click
import cv2
import numpy as np
import pyrealsense2 as rs
import rclpy
from cv_bridge import CvBridge
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy, DurabilityPolicy
from sensor_msgs.msg import CameraInfo, Image
from std_msgs.msg import Bool, String

# `body_tracking` is a sibling package (src/perception/src/body_tracking). This node is
# launched via run_camera.py as `src.camera.realsense_publisher_node`, where that dir is
# NOT on sys.path, so put our own package root there rather than depend on the launcher.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from body_tracking.health.camera import (  # noqa: E402
    lock_color_sensor,
    lock_satisfied,
    restore_auto_on_sensor,
)

# If no fresh lock request arrives within this window, restore auto. The perception
# node republishes the request at 1 Hz, so this is a dead-man's switch: a crashed or
# hung perception node must not leave the shared colour stream locked for fall
# detection. Three missed requests before we act.
LOCK_LEASE_S = 3.0

logger = logging.getLogger(__name__)


def _flip_image_180(image: np.ndarray) -> np.ndarray:
    return cv2.rotate(image, cv2.ROTATE_180)


def _adjust_camera_info_for_flip_180(info: CameraInfo) -> None:
    """Update intrinsics after a 180° image rotation (in-place)."""
    w, h = info.width, info.height
    info.k[2] = w - info.k[2]  # cx
    info.k[5] = h - info.k[5]  # cy
    info.p[2] = w - info.p[2]
    info.p[6] = h - info.p[6]
    if len(info.d) >= 4:
        info.d[2] *= -1.0  # p1
        info.d[3] *= -1.0  # p2


class RealSensePublisherNode(Node):
    def __init__(
        self,
        width: int = 640,
        height: int = 480,
        fps: int = 30,
        enable_depth: bool = False,
        align_depth: bool = True,
        frame_id: str = "camera_color_optical_frame",
        flip_180: bool = False,
    ) -> None:
        super().__init__("realsense_publisher")
        self.bridge = CvBridge()
        self.frame_id = frame_id
        self.enable_depth = enable_depth
        self.align_depth = align_depth and enable_depth
        self.flip_180 = flip_180

        # Sensor data QoS: best-effort keep-last is the convention for image streams.
        qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=5,
        )
        self.color_pub = self.create_publisher(
            Image, "/camera/camera/color/image_raw", qos
        )
        self.info_pub = self.create_publisher(
            CameraInfo, "/camera/camera/color/camera_info", qos
        )
        self.depth_pub = None
        if self.enable_depth:
            self.depth_pub = self.create_publisher(
                Image, "/camera/camera/aligned_depth_to_color/image_raw", qos
            )

        # --- configure the RealSense pipeline ---
        self.pipeline = rs.pipeline()
        config = rs.config()
        config.enable_stream(
            rs.stream.color, width, height, rs.format.bgr8, fps
        )
        if self.enable_depth:
            config.enable_stream(
                rs.stream.depth, width, height, rs.format.z16, fps
            )
        self.profile = self.pipeline.start(config)
        self.align = rs.align(rs.stream.color) if self.align_depth else None

        self._camera_info = self._build_camera_info()
        if self.flip_180:
            _adjust_camera_info_for_flip_180(self._camera_info)
        device = self.profile.get_device()
        flip_note = ", flip_180=on" if self.flip_180 else ""
        self.get_logger().info(
            f"RealSense started: {device.get_info(rs.camera_info.name)} "
            f"({width}x{height}@{fps}, depth={'on' if enable_depth else 'off'}{flip_note})"
        )

        # --- Scan-scoped AE/AWB lock (health rPPG, Task 16c) ---
        # This node owns the colour sensor, so it applies the lock and reports the
        # VERIFIED result back. The lock is requested only for the duration of a health
        # scan (the colour stream is shared with fall detection), and the D415 persists
        # AE/AWB across restarts -- so we start from a known AUTO state and only lock on
        # request.
        self._color_sensor = self._find_color_sensor()
        self._lock_state = self._apply_lock(False)  # force AUTO at startup
        self._lock_req_t = 0.0  # time of the last lock request; drives the lease
        # Latched QoS so a late-joining perception node gets the current state at once.
        latched = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
        )
        self.lock_state_pub = self.create_publisher(
            String, "/health/camera_lock_state", latched
        )
        self.lock_req_sub = self.create_subscription(
            Bool, "/health/camera_lock", self._on_lock_request, latched
        )
        self._publish_lock_state()
        # 1 Hz housekeeping: enforce the lock lease and republish state (keeps the
        # perception node's freshness check satisfied even with no state changes).
        self.create_timer(1.0, self._lock_housekeeping)

        # Drive publishing from a wall timer; pulling is non-blocking-ish.
        self._frame_count = 0
        self.timer = self.create_timer(1.0 / max(fps, 1), self._tick)

    def _find_color_sensor(self):
        for sensor in self.profile.get_device().query_sensors():
            if sensor.get_info(rs.camera_info.name) == "RGB Camera":
                return sensor
        return None

    def _apply_lock(self, lock: bool):
        """Lock (or restore auto on) the colour sensor and return the verified state.

        Verification lives in lock_color_sensor(): a set_option can be silently ignored,
        and a lock we believe in but do not have is worse than none -- it would mark a
        scan window stable while the camera keeps hunting."""
        if self._color_sensor is None:
            return {"locked": False, "failures": ["no RGB Camera sensor found"]}
        if lock:
            result = lock_color_sensor(
                self._color_sensor,
                rs.option.enable_auto_exposure,
                rs.option.enable_auto_white_balance,
            )
            if not result.locked:
                self.get_logger().warning(f"camera lock FAILED: {result.failures}")
            return result.as_dict()
        # Restore auto, VERIFIED by read-back. A silently-ignored set here would leave
        # the shared stream locked while we report it free -- so restore_auto_on_sensor
        # reads both controls back and reports a failure unless auto actually took, which
        # keeps lock_satisfied(False, ...) retrying instead of latching a stuck lock.
        result = restore_auto_on_sensor(
            self._color_sensor,
            rs.option.enable_auto_exposure,
            rs.option.enable_auto_white_balance,
        )
        if not result["auto"]:
            self.get_logger().warning(f"auto-restore FAILED: {result['failures']}")
        return result

    def _now(self) -> float:
        return self.get_clock().now().nanoseconds / 1e9

    def _lock_housekeeping(self) -> None:
        # Lease: if the camera is not verified-auto and no fresh request has arrived,
        # the requester is gone -- restore auto so fall detection is not left on a frozen
        # exposure. Guard on `not auto` so we do not re-set the sensor every idle second.
        if not self._lock_state.get("auto") and (self._now() - self._lock_req_t) > LOCK_LEASE_S:
            self.get_logger().warning(
                "camera lock lease expired (no fresh request) -- restoring auto"
            )
            self._lock_state = self._apply_lock(False)
        self._publish_lock_state()

    def _on_lock_request(self, msg: Bool) -> None:
        want = bool(msg.data)
        self._lock_req_t = self._now()  # refresh the lease on EVERY request, even a skip
        # Skip only when the VERIFIED physical state already matches -- never on
        # want==last_want alone, or a transient failure would latch forever and the
        # camera could get stuck (see lock_satisfied). Perception republishes at 1 Hz,
        # so an unsatisfied request is retried on the next tick.
        if lock_satisfied(want, self._lock_state):
            return
        was_locked = bool((self._lock_state or {}).get("locked"))
        self._lock_state = self._apply_lock(want)
        now_locked = bool(self._lock_state.get("locked"))
        if now_locked != was_locked:  # log real transitions, not every retry
            self.get_logger().info(
                f"camera lock {'ENGAGED' if now_locked else 'released'}"
            )
        self._publish_lock_state()

    def _publish_lock_state(self) -> None:
        msg = String()
        msg.data = json.dumps(self._lock_state)
        self.lock_state_pub.publish(msg)

    def _build_camera_info(self) -> CameraInfo:
        color_profile = self.profile.get_stream(
            rs.stream.color
        ).as_video_stream_profile()
        intr = color_profile.get_intrinsics()
        info = CameraInfo()
        info.width = intr.width
        info.height = intr.height
        info.distortion_model = "plumb_bob"
        info.d = list(intr.coeffs) + [0.0] * (5 - len(intr.coeffs))
        info.k = [
            intr.fx, 0.0, intr.ppx,
            0.0, intr.fy, intr.ppy,
            0.0, 0.0, 1.0,
        ]
        info.r = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0]
        info.p = [
            intr.fx, 0.0, intr.ppx, 0.0,
            0.0, intr.fy, intr.ppy, 0.0,
            0.0, 0.0, 1.0, 0.0,
        ]
        return info

    def _tick(self) -> None:
        try:
            frames = self.pipeline.wait_for_frames(2000)
        except RuntimeError as exc:
            self.get_logger().warn(f"wait_for_frames timed out: {exc}")
            return

        if self.align is not None:
            frames = self.align.process(frames)

        color_frame = frames.get_color_frame()
        if not color_frame:
            return

        stamp = self.get_clock().now().to_msg()
        color_image = np.asanyarray(color_frame.get_data())
        if self.flip_180:
            color_image = _flip_image_180(color_image)
        color_msg = self.bridge.cv2_to_imgmsg(color_image, encoding="bgr8")
        color_msg.header.stamp = stamp
        color_msg.header.frame_id = self.frame_id
        self.color_pub.publish(color_msg)

        self._camera_info.header.stamp = stamp
        self._camera_info.header.frame_id = self.frame_id
        self.info_pub.publish(self._camera_info)

        if self.depth_pub is not None:
            depth_frame = frames.get_depth_frame()
            if depth_frame:
                depth_image = np.asanyarray(depth_frame.get_data())
                if self.flip_180:
                    depth_image = _flip_image_180(depth_image)
                depth_msg = self.bridge.cv2_to_imgmsg(
                    depth_image, encoding="16UC1"
                )
                depth_msg.header.stamp = stamp
                depth_msg.header.frame_id = self.frame_id
                self.depth_pub.publish(depth_msg)

        self._frame_count += 1

    def destroy_node(self):
        # Restore auto exposure/WB before we go, so a scan interrupted by a crash or
        # Ctrl+C does not leave fall detection running on a locked-exposure image.
        try:
            self._apply_lock(False)
        except Exception:
            pass
        try:
            self.pipeline.stop()
        except Exception:
            pass
        super().destroy_node()


@click.command()
@click.option("--width", type=int, default=640)
@click.option("--height", type=int, default=480)
@click.option("--fps", type=int, default=30)
@click.option("--enable-depth", is_flag=True, default=False)
@click.option("--align-depth/--no-align-depth", default=True)
@click.option(
    "--flip-180/--no-flip-180",
    default=False,
    help="Rotate color/depth 180° for upside-down camera mount.",
)
def main(
    width: int,
    height: int,
    fps: int,
    enable_depth: bool,
    align_depth: bool,
    flip_180: bool,
):
    rclpy.init(args=None)
    node = RealSensePublisherNode(
        width=width,
        height=height,
        fps=fps,
        enable_depth=enable_depth,
        align_depth=align_depth,
        flip_180=flip_180,
    )
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    except Exception as exc:
        if exc.__class__.__name__ != "ExternalShutdownException":
            raise
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
