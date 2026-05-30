# orchestrator/http/routers/events.py
from fastapi import APIRouter
from ..schemas import FallEvent
from ..domain import safety

router = APIRouter()


@router.post("/fall_detected")
async def fall_detected(event: FallEvent):
    """
    Called by fall detection service.

    Example from perception node:
        POST http://orchestrator:8002/events/fall_detected
        {
          "confidence": 0.92,
          "ts": 1736092345.12
        }
    """
    print(f"[events] fall_detected: conf={event.confidence}, ts={event.ts}")
    safety.handle_fall_event(event)
    return {"status": "ok"}
