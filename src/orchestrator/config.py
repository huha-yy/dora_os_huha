# orchestrator/config.py
import os
from orchestrator.execution.action_registry import ActionExecutorRegistry
from orchestrator.executors.ai_fall_dialog import AIFallDialogExecutor
from orchestrator.executors.set_motion_mode import SetMotionModeExecutor
from orchestrator.executors.set_agent_status import SetAgentStatusExecutor
from typing import Any

# Where orchestrator listens
ORCHESTRATOR_PORT: int = int(os.getenv("ORCHESTRATOR_PORT", "8002"))

# Where the AI agent HTTP API lives
AI_AGENT_URL: str = os.getenv("AI_AGENT_URL", "http://localhost:12393")

# Debounce fall events
FALL_COOLDOWN_SEC: int = int(os.getenv("FALL_COOLDOWN_SEC", "60"))


def register_executors(action_registry: ActionExecutorRegistry, ctx: Any) -> None:
    action_registry.register_executor(AIFallDialogExecutor(ctx))
    action_registry.register_executor(SetMotionModeExecutor(ctx))
    action_registry.register_executor(SetAgentStatusExecutor(ctx))
