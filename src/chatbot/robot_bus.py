"""
机器人总线 — 通过 ros2 topic pub 发送指令
简单可靠, 通过 subprocess 调用 ros2 CLI
"""

import subprocess
import shlex

from loguru import logger

_ROS2_SETUP = "/opt/ros/humble/setup.bash"


def _ros2_cmd(args: str) -> None:
    """在已 source ROS2 的 bash 里执行 ros2 命令"""
    cmd = f"bash -c 'source {shlex.quote(_ROS2_SETUP)} && {args} 2>/dev/null'"
    subprocess.run(cmd, shell=True, timeout=5)


def publish_cmd_vel(vx: float, vy: float, wz: float):
    twist = f"{{linear: {{x: {vx}, y: {vy}}}, angular: {{z: {wz}}}}}"
    _ros2_cmd(f"ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist \"{twist}\"")
    logger.debug(f"[RobotBus] /cmd_vel: vx={vx}, vy={vy}, wz={wz}")


def publish_head_cmd(action: str):
    _ros2_cmd(f"ros2 topic pub --once /head_cmd std_msgs/msg/String \"{{data: '{action}'}}\"")
    logger.debug(f"[RobotBus] /head_cmd: {action}")


def publish_arm_cmd(action: str):
    _ros2_cmd(f"ros2 topic pub --once /arm_cmd std_msgs/msg/String \"{{data: '{action}'}}\"")
    logger.debug(f"[RobotBus] /arm_cmd: {action}")
