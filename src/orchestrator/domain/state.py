# orchestrator/domain/state.py
from typing import List
from dataclasses import dataclass, field, replace
from enum import Enum
import time
from copy import deepcopy
from collections import deque


def now_ts() -> float:
    return time.time()


class MotionMode(str, Enum):
    STOPPED = "stopped"
    FOLLOW_USER = "follow_user"
    NAV_GOAL = "nav_goal"
    OTHER = "other"


class AgentStatus(str, Enum):
    IDLE = "idle"
    ASKING_USER = "asking_user"
    RESPONDING = "responding"
    TRIGGER_FALLING_HANDLING = "triggered_falling_handling"
    FALLING_HANDLING = "falling_handling"
    OTHER = "other"


@dataclass
class MotionModeState:
    motion_mode: MotionMode = MotionMode.STOPPED
    last_motion_mode_ts: float = 0.0


@dataclass
class AgentStatusState:
    agent_status: AgentStatus = AgentStatus.IDLE
    last_agent_status_ts: float = 0.0


@dataclass
class RobotState:
    motion_mode_state: MotionModeState = field(default_factory=MotionModeState)
    agent_status_state: AgentStatusState = field(default_factory=AgentStatusState)
    motion_mode_history: List[MotionModeState] = field(default_factory=list)
    agent_status_history: List[AgentStatusState] = field(default_factory=list)
    max_history_size: int = 100

    def __post_init__(self):
        self.reset()

    def reset(self) -> None:
        self.motion_mode_state = MotionModeState()
        self.agent_status_state = AgentStatusState()
        self.motion_mode_history = deque(maxlen=self.max_history_size)
        self.agent_status_history = deque(maxlen=self.max_history_size)
        self.motion_mode_history.append(deepcopy(self.motion_mode_state))
        self.agent_status_history.append(deepcopy(self.agent_status_state))

    def update_motion_mode_state(self, motion_mode: MotionMode | str) -> None:
        if isinstance(motion_mode, str):
            motion_mode = MotionMode(motion_mode)
        if self.motion_mode_state.motion_mode == motion_mode:
            self.logger.info(f"Motion mode already set to {motion_mode}")
            return
        self.motion_mode_history.append(deepcopy(self.motion_mode_state))
        self.motion_mode_state.motion_mode = motion_mode
        self.motion_mode_state.last_motion_mode_ts = now_ts()

    def update_agent_status_state(self, agent_status: AgentStatus | str) -> None:
        if isinstance(agent_status, str):
            agent_status = AgentStatus(agent_status)
        if self.agent_status_state.agent_status == agent_status:
            self.logger.info(f"Agent status already set to {agent_status}")
            return
        self.agent_status_history.append(deepcopy(self.agent_status_state))
        self.agent_status_state.agent_status = agent_status
        self.agent_status_state.last_agent_status_ts = now_ts()

    def update_state(
        self,
        motion_mode: MotionMode | str | None = None,
        agent_status: AgentStatus | str | None = None,
    ) -> None:
        if motion_mode is not None:
            print(f"Updating motion mode to {motion_mode}")
            self.update_motion_mode_state(motion_mode)
        if agent_status is not None:
            print(f"Updating agent status to {agent_status}")
            self.update_agent_status_state(agent_status)
