# orchestrator/execution/executors/stop_motion.py
from ..execution.types import Action, ActionType
from orchestrator.execution.types import ActionExecutorResult
from .executor_base import ActionExecutor


class SetMotionModeExecutor(ActionExecutor):
    action_type = ActionType.SET_MOTION_MODE
    is_async = False

    def execute(self, action: Action) -> ActionExecutorResult:
        # TODO: Implement set motion mode
        self.ctx.logger.info(f"Setting motion mode to {action.payload['motion_mode']}")
        self.ctx.robot_state.update_motion_mode_state(action.payload["motion_mode"])
        return ActionExecutorResult(action=action, is_success=True)
