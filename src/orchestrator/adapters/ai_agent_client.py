# orchestrator/adapters/ai_agent_client.py
import requests
from ..config import AI_AGENT_URL
from ..schemas import FallEvent


def notify_fall_detected(event: FallEvent) -> None:
    """
    Tell the AI agent: 'I detected a possible fall'.
    The AI agent should then ask the user: 'Did you fall? Do you need help?'
    """
    url = f"{AI_AGENT_URL}/events/fall_detected"
    payload = event.dict()
    try:
        resp = requests.post(url, json=payload, timeout=2.0)
        print(f"[ai_agent_client] POST {url} -> {resp.status_code}")
    except Exception as e:
        print(f"[ai_agent_client] Error notifying AI agent: {e}")
