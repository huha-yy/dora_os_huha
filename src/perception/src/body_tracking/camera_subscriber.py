#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge

import cv2  # from opencv-python
import numpy as np
import os


class CameraSubscriber(Node):
    def __init__(self):
        super().__init__("camera_subscriber")

        # Bridge ROS Image <-> OpenCV
        self.bridge = CvBridge()
        self.headless = not bool(os.environ.get("DISPLAY"))

        # Subscribe to RealSense color stream
        self.subscription = self.create_subscription(
            Image,
            "/camera/camera/color/image_raw",  # or /d415/color/image_raw if you changed camera_name
            self.image_callback,
            10,
        )
        if self.headless:
            self.get_logger().info("Running in headless mode (no DISPLAY).")
        else:
            self.get_logger().info("GUI mode enabled; will show OpenCV window.")

    def image_callback(self, msg: Image):
        # Convert ROS Image → OpenCV BGR image
        cv_image = self.bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")

        if not self.headless:
            cv2.imshow("RealSense Color", cv_image)
            cv2.waitKey(1)
        else:
            # headless debug
            self.get_logger().info_once(
                f"Receiving frames: shape={cv_image.shape}"
            )

def main(args=None):
    rclpy.init(args=args)
    node = CameraSubscriber()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
