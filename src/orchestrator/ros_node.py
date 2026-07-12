# orchestrator/ros_node.py
import json
import os
import sys

# Add src to path to enable absolute imports when running as script
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import time
from typing import Optional

import logging
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from std_msgs.msg import String
from sensor_msgs.msg import Image

# Configure logging format to include line numbers for ROS2 loggers
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(filename)s:%(lineno)d: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    force=True,  # Override any existing configuration
)

from orchestrator.schemas import FallEvent
from orchestrator.domain import safety
from orchestrator.domain.state import RobotState, AgentStatus
from orchestrator.config import AI_AGENT_URL, register_executors
from orchestrator.execution.action_registry import ActionExecutorRegistry
from orchestrator.execution.scheduler import AsyncScheduler
import threading
from typing import Tuple


class DorabotOrchestratorNode(Node):
    """
    Central ROS2 node for Dorabot:
    - Subscribes to fall detection events.
    - (Later: subscribes to SLAM, follow, wheel status, etc.)
    """

    def __init__(
        self,
        fall_topic_name: str = "fall_event",
        annotated_topic_name: str = "/body_tracking/image_annotated",
    ) -> None:
        super().__init__("dorabot_orchestrator")
        self.logger = self.get_logger()
        self.logger.info(
            f"Starting DorabotOrchestratorNode, listening on '{fall_topic_name}'"
        )

        self._fall_sub = self.create_subscription(
            String,
            fall_topic_name,
            self._fall_callback,
            10,
        )

        # Subscribe to annotated frames and feed the web MJPEG stream.
        self._bridge = None
        try:
            from cv_bridge import CvBridge

            self._bridge = CvBridge()
            image_qos = QoSProfile(
                reliability=ReliabilityPolicy.BEST_EFFORT,
                history=HistoryPolicy.KEEP_LAST,
                depth=2,
            )
            self._annotated_sub = self.create_subscription(
                Image,
                annotated_topic_name,
                self._annotated_callback,
                image_qos,
            )
            self.logger.info(
                f"Subscribed to annotated frames on '{annotated_topic_name}'"
            )
        except Exception as exc:  # pragma: no cover - defensive
            self.logger.warn(
                f"Annotated-frame bridge unavailable ({exc}); video stream disabled."
            )
        # Health metrics bridge.
        from orchestrator.web_server.health_bus import health_bus
        self._health_bus = health_bus

        self._health_sub = self.create_subscription(
            String, "/health/metrics", self._health_metrics_cb, 10
        )
        self._scan_cmd_pub = self.create_publisher(String, "/health/scan_cmd", 10)
        self.create_timer(0.2, self._drain_scan_cmd)

        self.robot_state = RobotState()
        self.scheduler = AsyncScheduler()
        self.scheduler.start()
        self.action_registry = ActionExecutorRegistry(self.scheduler)
        register_executors(self.action_registry, self)
        self.ai_agent_url = AI_AGENT_URL

    def _annotated_callback(self, msg: Image) -> None:
        """Encode the latest annotated frame as JPEG for the web MJPEG stream."""
        if self._bridge is None:
            return
        try:
            import cv2

            from orchestrator.web_server.frame_bus import frame_bus

            cv_image = self._bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
            ok, buf = cv2.imencode(".jpg", cv_image, [cv2.IMWRITE_JPEG_QUALITY, 75])
            if ok:
                frame_bus.set_jpeg(buf.tobytes())
        except Exception as exc:  # pragma: no cover - defensive
            self.logger.debug(f"Failed to encode annotated frame: {exc}")

    def _health_metrics_cb(self, msg: String) -> None:
        try:
            self._health_bus.set_metrics(json.loads(msg.data or "{}"))
        except (ValueError, TypeError):
            pass

    def _drain_scan_cmd(self) -> None:
        cmd = self._health_bus.take_cmd()
        if not cmd:
            return
        out = String()
        out.data = json.dumps(cmd)
        self._scan_cmd_pub.publish(out)

    def _fall_callback(self, msg: String) -> None:
        """
        Expects messages like "fallen:{timestamp}" (string).
        If timestamp is missing or malformed, we just use now().
        """
        text = msg.data or "{}"
        self.logger.debug(f"Received fall_msg: {text!r}")
        try:
            json_data = json.loads(text)
            event = json_data.get("status", "")
            confidence = json_data.get("confidence", 1.0)
            ts = json_data.get("timestamp", 0.0)
        except ValueError as e:
            self.logger.warn(f"Failed to parse fall_msg {text!r}: {e}")
            return
        # Delegate to domain safety logic
        decision = safety.handle_fall_event(
            event=FallEvent(event=event, confidence=confidence, ts=ts),
            robot_state=self.robot_state,
        )
        decision_result = self.action_registry.execute(decision)


def start_ros_node() -> Tuple[DorabotOrchestratorNode, threading.Thread]:
    rclpy.init(args=None)
    node = DorabotOrchestratorNode()
    t = threading.Thread(target=rclpy.spin, args=(node,), daemon=True)
    t.start()
    return node, t


def stop_ros_node(node: DorabotOrchestratorNode | None) -> None:
    if node is None:
        return
    try:
        node.destroy_node()
    finally:
        rclpy.shutdown()


def main() -> None:
    rclpy.init(args=None)
    node = DorabotOrchestratorNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        node.logger.error(f"Error in main: {e}")
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
