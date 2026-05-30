from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
import time
import uuid


class ActionType(str, Enum):
    # ROS / motion
    STOP_MOTION = "stop_motion"
    SET_MOTION_MODE = "set_motion_mode"

    # AI agent
    AI_SAY = "ai_say"
    AI_FALL_DIALOG = "ai_fall_dialog"  # “did you fall / need help?”
    SET_AGENT_STATUS = "set_agent_status"

    # Emergency
    CALL_EMERGENCY_CONTACT = "call_emergency_contact"


@dataclass(frozen=True)
class Action:
    type: ActionType
    payload: Dict[str, Any] = field(default_factory=dict)
    # optional metadata
    source: Optional[str] = None
    action_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    # whether the action is blocking the execution of the next action
    # if False, the action will be run asynchronously in the background
    is_blocking: bool = True


@dataclass(frozen=True)
class Decision:
    """
    A decision is just a plan: a sequence of actions to execute.
    It contains no side effects by itself.
    """

    actions: List[Action]
    reason: str = ""
    source: str = "unknown"
    ts: float = field(default_factory=time.time)
    decision_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    priority: int = 0  # higher = more important (e.g., safety)


@dataclass(frozen=True)
class ActionExecutorResult:
    action: Action
    is_success: bool
    error: Optional[str] = None


@dataclass(frozen=True)
class DecisionExecutorResult:
    decision: Decision
    actions_results: List[ActionExecutorResult]
    is_success: bool
    error: Optional[str] = None
