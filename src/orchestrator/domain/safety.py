# orchestrator/domain/safety.py
from ..config import FALL_COOLDOWN_SEC
from .state import RobotState, MotionMode, now_ts, AgentStatus
from ..schemas import FallEvent
from ..adapters import ros2_adapter, ai_agent_client, emergency_contact_client
from ..execution.types import Action, ActionType, Decision
import logging

logger = logging.getLogger(__name__)

FALL_PRIORITY = 100


def decide_on_fall(event: FallEvent) -> Decision:
    # Keep this pure: just decide; no ROS publishes, no HTTP calls.
    actions = [
        Action(
            ActionType.SET_MOTION_MODE,
            {"motion_mode": MotionMode.STOPPED.value, "reason": "Fall detected"},
            source="safety",
        ),
        Action(
            ActionType.SET_AGENT_STATUS,
            {"agent_status": AgentStatus.FALLING_HANDLING.value},
            source="safety",
        ),
        Action(
            ActionType.AI_FALL_DIALOG,
            {
                "context": "fall_detected",
                "confidence": event.confidence,
                "ts": event.ts,
                "human_status": event.event,
            },
            source="safety",
        ),
    ]
    return Decision(
        actions=actions,
        reason=f"Fall detected (confidence={event.confidence})",
        source="safety",
        priority=FALL_PRIORITY,
    )


def handle_fall_event(event: FallEvent, robot_state: RobotState) -> Decision | None:
    """
    Called when fall detection reports a possible fall.
    Responsibilities:
    - Debounce repeated events.
    - Stop robot motion.
    - Notify AI agent to ask the user.
    """
    now = now_ts()
    if robot_state.agent_status_state.agent_status == AgentStatus.FALLING_HANDLING:
        logger.debug("[safety] Fall event already being handled, ignoring.")
        return
    if (
        robot_state.agent_status_state.agent_status
        == AgentStatus.TRIGGER_FALLING_HANDLING
    ):
        if (
            now - robot_state.agent_status_state.last_agent_status_ts
            < FALL_COOLDOWN_SEC
        ):
            logger.debug("[safety] Fall event within cooldown, ignoring.")
            return

    return decide_on_fall(event)


def decide_on_fall_dialog_result(needs_help: bool, user_text: str | None) -> Decision:
    actions = []
    if needs_help:
        actions.append(
            Action(
                ActionType.CALL_EMERGENCY_CONTACT,
                {"reason": user_text},
                source="safety",
            )
        )
    actions.append(
        Action(
            ActionType.SET_AGENT_STATUS,
            {"agent_status": AgentStatus.FALLING_HANDLING.value},
            source="safety",
        )
    )
    return Decision(
        actions=actions,
        reason="Fall dialog result",
        source="safety",
        priority=FALL_PRIORITY,
    )


def complete_fall_handling(content: str) -> Decision:
    actions = [
        Action(
            ActionType.AI_SAY,
            {"content": content},
            source="safety",
        ),
        Action(
            ActionType.SET_AGENT_STATUS,
            {"agent_status": AgentStatus.IDLE},
            source="safety",
        ),
    ]
    return Decision(
        actions=actions,
        reason="Fall handling completed",
        source="safety",
        priority=FALL_PRIORITY,
    )
