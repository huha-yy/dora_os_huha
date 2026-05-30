# orchestrator/execution/action_registry.py
from __future__ import annotations
from typing import Dict
from .types import Action, ActionType, Decision
from orchestrator.execution.types import ActionExecutorResult, DecisionExecutorResult


class ActionExecutorRegistry:
    def __init__(self, scheduler):
        self._handlers: Dict[ActionType, object] = {}
        self._scheduler = scheduler

    def register_executor(self, executor) -> None:
        if executor.action_type in self._handlers:
            raise ValueError(f"Duplicate executor for {executor.action_type}")
        self._handlers[executor.action_type] = executor

    def execute_action(self, action: Action) -> ActionExecutorResult:
        executor = self._handlers.get(action.type)
        if executor is None:
            raise KeyError(f"No executor registered for action type: {action.type}")

        if executor.is_async:
            # async executor
            coro = executor.execute_async(action)

            if action.is_blocking:
                fut = self._scheduler.submit(coro)
                try:
                    return fut.result(timeout=30)
                except Exception as e:
                    return ActionExecutorResult(
                        action=action, is_success=False, error=str(e)
                    )
            else:
                self._scheduler.submit(coro)
                return ActionExecutorResult(action=action, is_success=True)

        # sync executor
        try:
            return executor.execute(action)
        except Exception as e:
            return ActionExecutorResult(action=action, is_success=False, error=str(e))

    def execute(self, decision: Decision | None) -> DecisionExecutorResult:
        if decision is None:
            return DecisionExecutorResult(
                decision=None,
                actions_results=[],
                is_success=True,
                error="No decision to execute",
            )
        if len(decision.actions) == 0:
            return DecisionExecutorResult(
                decision=decision,
                actions_results=[],
                is_success=True,
                error="No actions to execute",
            )
        actions_results = [self.execute_action(action) for action in decision.actions]
        return DecisionExecutorResult(
            decision=decision,
            actions_results=actions_results,
            is_success=all(result.is_success for result in actions_results),
            error=(
                None
                if all(result.is_success for result in actions_results)
                else "One or more actions failed"
            ),
        )
