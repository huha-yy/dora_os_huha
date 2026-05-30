# orchestrator/adapters/ros2_adapter.py
def stop_robot() -> None:
    """
    For now, just log. Later:
    - publish geometry_msgs/Twist with zero velocities to /cmd_vel
    - or call nav2 cancel action.
    """
    print("[ros2_adapter] stop_robot() called (TODO: implement with ROS2)")
