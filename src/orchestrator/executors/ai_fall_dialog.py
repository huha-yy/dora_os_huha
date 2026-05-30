# orchestrator/execution/executors/ai_fall_dialog.py
from ..execution.types import Action, ActionType
from orchestrator.execution.types import ActionExecutorResult
from .executor_base import ActionExecutor
from perception.src.body_tracking.state import HumanStatus
import requests


class AIFallDialogExecutor(ActionExecutor):
    action_type = ActionType.AI_FALL_DIALOG
    is_async = True

    async def execute_async(self, action: Action) -> ActionExecutorResult:
        # requires your ai client to be async; if it's sync today, we can wrap it later
        try:
            human_status = action.payload.get("human_status", "")
        except Exception as e:
            self.ctx.logger.error(f"Failed to parse human status: {e}")
            return ActionExecutorResult(action=action, is_success=False, error=str(e))
        if human_status == "falling_candidate":
            print(f"Sending fall candidate to AI agent")
            print(f"Posting to {self.ctx.ai_agent_url}/vision/fall-candidate")
            response = requests.post(f"{self.ctx.ai_agent_url}/vision/fall-candidate")
            if response.status_code != 200:
                self.ctx.logger.error(
                    f"Failed to notify fall candidate: {response.status_code}"
                )
                return ActionExecutorResult(
                    action=action, is_success=False, error=response.text
                )

        return ActionExecutorResult(action=action, is_success=True)
