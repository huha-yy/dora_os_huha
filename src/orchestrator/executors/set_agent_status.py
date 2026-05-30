# orchestrator/execution/executors/stop_motion.py
from ..execution.types import Action, ActionType
from orchestrator.execution.types import ActionExecutorResult
from .executor_base import ActionExecutor


class SetAgentStatusExecutor(ActionExecutor):
    action_type = ActionType.SET_AGENT_STATUS
    is_async = False

    def execute(self, action: Action) -> ActionExecutorResult:
        # TODO: Implement set agent status
        self.ctx.logger.info(
            f"Setting agent status to {action.payload['agent_status']}"
        )
        self.ctx.robot_state.update_agent_status_state(action.payload["agent_status"])
        return ActionExecutorResult(action=action, is_success=True)
