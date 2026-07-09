# orchestrator/adapters/ros2_adapter.py
"""ROS 2 底层控制适配器"""

import logging

logger = logging.getLogger(__name__)

# 模块级引用, 由 ros_node.py 在初始化时注入
_cmd_vel_publisher = None


def set_cmd_vel_publisher(publisher):
    """注入 /cmd_vel 发布者 (由 DorabotOrchestratorNode 调用)"""
    global _cmd_vel_publisher
    _cmd_vel_publisher = publisher


def stop_robot() -> None:
    """发布零速度到 /cmd_vel, 紧急停止底盘"""
    if _cmd_vel_publisher is None:
        logger.warning("[ros2_adapter] stop_robot() 未注入 /cmd_vel publisher, 无法发送停止指令")
        return

    from geometry_msgs.msg import Twist
    stop_msg = Twist()
    stop_msg.linear.x = 0.0
    stop_msg.linear.y = 0.0
    stop_msg.angular.z = 0.0
    _cmd_vel_publisher.publish(stop_msg)
    logger.info("[ros2_adapter] 已发送 /cmd_vel 零速度 (急停)")
