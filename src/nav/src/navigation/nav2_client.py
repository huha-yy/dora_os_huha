import math
from typing import Optional, Callable

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient

from geometry_msgs.msg import PoseStamped
from nav2_msgs.action import NavigateToPose


class Nav2Client:
    def __init__(self, node: Node, action_name: str = "/navigate_to_pose"):
        self.node = node
        self._client = ActionClient(node, NavigateToPose, action_name)

        self._goal_handle = None
        self._active_goal_id = 0  # local counter to disambiguate callbacks

    def wait_ready(self, timeout_sec: float = 5.0) -> bool:
        self.node.get_logger().info(
            f"Waiting for Nav2 action server: {self._client.action_name}"
        )
        return self._client.wait_for_server(timeout_sec=timeout_sec)

    def is_navigating(self) -> bool:
        return self._goal_handle is not None

    def cancel(self) -> None:
        if self._goal_handle is None:
            return
        self.node.get_logger().info("Canceling current Nav2 goal...")
        future = self._goal_handle.cancel_goal_async()

        def _done(_fut):
            self.node.get_logger().info("Cancel request sent.")

        future.add_done_callback(_done)

        # For MVP we clear local state immediately; Nav2 will handle cancellation.
        self._goal_handle = None

    def send_goal(
        self,
        goal_pose: PoseStamped,
        feedback_cb: Optional[Callable] = None,
        result_cb: Optional[Callable[[bool, str], None]] = None,
    ) -> None:
        """Send a NavigateToPose goal. Cancels local handle tracking when result arrives."""
        goal_msg = NavigateToPose.Goal()
        goal_msg.pose = goal_pose

        self._active_goal_id += 1
        my_goal_id = self._active_goal_id

        def _feedback(feedback_msg):
            if feedback_cb:
                feedback_cb(feedback_msg)

        send_future = self._client.send_goal_async(
            goal_msg, feedback_callback=_feedback
        )

        def _goal_response(fut):
            if my_goal_id != self._active_goal_id:
                return  # stale
            goal_handle = fut.result()
            if not goal_handle.accepted:
                self.node.get_logger().warn("Nav2 goal rejected.")
                if result_cb:
                    result_cb(False, "rejected")
                return

            self.node.get_logger().info("Nav2 goal accepted.")
            self._goal_handle = goal_handle

            result_future = goal_handle.get_result_async()

            def _result_done(rf):
                if my_goal_id != self._active_goal_id:
                    return
                status = rf.result().status
                # status is an int (GoalStatus). Keep MVP simple:
                ok = (status == 4) or (
                    status == 0
                )  # NOTE: depends on RMW; we’ll print anyway
                self.node.get_logger().info(f"Nav2 result status={status}")
                self._goal_handle = None
                if result_cb:
                    result_cb(ok, f"status={status}")

            result_future.add_done_callback(_result_done)

        send_future.add_done_callback(_goal_response)
