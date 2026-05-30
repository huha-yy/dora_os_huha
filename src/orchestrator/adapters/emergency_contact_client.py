# orchestrator/adapters/emergency_contact_client.py
def call_emergency_contact(reason: str | None) -> None:
    """
    Real implementation: Twilio / SIP / phone call / SMS.
    For now we just log.
    """
    print(
        "[emergency_contact_client] CALL EMERGENCY CONTACT\n"
        f"  reason = {reason!r}\n"
        "  (TODO: integrate with Twilio / phone gateway)"
    )
