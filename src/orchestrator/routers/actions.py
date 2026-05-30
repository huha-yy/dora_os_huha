# orchestrator/http/routers/actions.py
from fastapi import APIRouter
from ..schemas import FallDialogResult, CallEmergencyContactRequest
from ..domain import safety

router = APIRouter()


@router.post("/fall_dialog_result")
async def fall_dialog_result(body: FallDialogResult):
    """
    Called by AI agent after it has asked the user:
      'Did you fall? Do you need help?'

    Example payload from AI agent:
      {
        "needs_help": true,
        "user_text": "Yes, I fell and my leg hurts."
      }
    """
    print(
        f"[actions] fall_dialog_result: needs_help={body.needs_help}, "
        f"user_text={body.user_text!r}"
    )
    safety.handle_fall_dialog_result(body.needs_help, body.user_text)
    return {"status": "ok"}


@router.post("/call_emergency_contact")
async def call_emergency_contact(req: CallEmergencyContactRequest):
    """
    Optional: 'direct' call entrypoint if AI agent wants to skip the
    /fall_dialog_result contract and just say 'call now'.
    """
    print(f"[actions] call_emergency_contact: reason={req.reason!r}")
    safety.handle_fall_dialog_result(needs_help=True, reason=req.reason)
    return {"status": "calling"}
