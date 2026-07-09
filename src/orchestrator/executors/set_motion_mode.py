# orchestrator/execution/executors/set_motion_mode.py
from orchestrator.execution.types import Action, ActionType, ActionExecutorResult
from orchestrator.executors.executor_base import ActionExecutor
from orchestrator.domain.state import MotionMode


class SetMotionModeExecutor(ActionExecutor):
    action_type = ActionType.SET_MOTION_MODE
    is_async = False

    def execute(self, action: Action) -> ActionExecutorResult:
        motion_mode = action.payload.get("motion_mode", "")
        self.ctx.logger.info(f"Setting motion mode to {motion_mode}")
        self.ctx.robot_state.update_motion_mode_state(motion_mode)

        # 切换到 STOPPED 时实际发送 /cmd_vel 零速度
        if motion_mode == MotionMode.STOPPED.value:
            from orchestrator.adapters.ros2_adapter import stop_robot
            stop_robot()

        return ActionExecutorResult(action=action, is_success=True)
