import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1]
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fastapi.testclient import TestClient

from orchestrator.web_server.app import create_app
from orchestrator.web_server.health_bus import health_bus


def test_scan_and_live_roundtrip():
    app = create_app()
    client = TestClient(app)

    r = client.post("/health/scan", json={"window_s": 30})
    assert r.status_code == 200
    mid = r.json()["measurement_id"]
    assert mid

    cmd = health_bus.take_cmd()
    assert cmd["action"] == "start" and cmd["measurement_id"] == mid

    health_bus.set_metrics({"schema_version": 1, "hr_bpm": 71.0, "state": "collecting"})
    live = client.get("/health/live").json()
    assert live["hr_bpm"] == 71.0
