# orchestrator/execution/executor_base.py
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import ClassVar

from ..execution.types import Action, ActionType
from orchestrator.execution.types import ActionExecutorResult


class ActionExecutor(ABC):
    action_type: ClassVar[ActionType]
    is_async: ClassVar[bool] = False

    def __init__(self, ctx):
        """
        ctx: the 'tool context' (for MVP, pass your ROS node),
        so executors can call ctx.ros, ctx.ai, ctx.emergency, ctx.state_store, etc.
        """
        self.ctx = ctx

    def register(self, registry) -> None:
        registry.register(self)

    # sync path
    def execute(self, action: Action) -> ActionExecutorResult:
        raise NotImplementedError("Sync executor must implement execute()")

    # async path
    async def execute_async(self, action: Action) -> ActionExecutorResult:
        raise NotImplementedError("Async executor must implement execute_async()")
