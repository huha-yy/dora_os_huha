import rclpy
from rclpy.node import Node


class DorabotAutonomy(Node):
    def __init__(self):
        super().__init__("dorabot_autonomy")
        self.get_logger().info("dorabot_autonomy started (MVP skeleton).")


def main():
    rclpy.init()
    node = DorabotAutonomy()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()
