# orchestrator/schemas.py
from enum import Enum
from typing import Optional
from pydantic import BaseModel

class EventType(str, Enum):
    FALL_DETECTED = "fall_detected"
    NAV_STATUS = "nav_status"
    USER_IDENTIFIED = "user_identified"
    USER_FOLLOW_STATUS = "user_follow_status"
    MUSIC_STATUS = "music_status"

class NavStatus(str, Enum):
    IDLE = "idle"
    MOVING = "moving"
    BLOCKED = "blocked"
    ERROR = "error"

class ActionType(str, Enum):
    CALL_EMERGENCY_CONTACT = "call_emergency_contact"
    STOP_MOVEMENT = "stop_movement"
    START_FOLLOW_USER = "start_follow_user"
    STOP_FOLLOW_USER = "stop_follow_user"
    PLAY_MUSIC = "play_music"
    STOP_MUSIC = "stop_music"

class FallEvent(BaseModel):
    event: str
    confidence: float
    ts: float  # unix timestamp


class FallDialogResult(BaseModel):
    needs_help: bool
    user_text: Optional[str] = None  # what the user said, optional


class CallEmergencyContactRequest(BaseModel):
    reason: Optional[str] = None
