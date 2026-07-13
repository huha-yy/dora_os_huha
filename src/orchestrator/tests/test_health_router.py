"""HTTP surface for the camera health readout.

Two contracts matter here and are easy to break silently:

- A reading is WITHHELD (null), never guessed. When perception is dead or the gates
  fail, the API must say "no reading" -- not serve the last one it happened to see.
- v1 is heart rate ONLY. resp_bpm / hrv_sdnn_ms / spo2_pct exist in the schema and
  are always null. If one of them ever becomes a number, that is a product breach,
  not a feature.
"""

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

SRC = Path(__file__).resolve().parents[1]
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from orchestrator.web_server.app import create_app  # noqa: E402
from orchestrator.web_server.health_bus import health_bus  # noqa: E402


@pytest.fixture(autouse=True)
def _isolate_bus():
    """health_bus is a module-level singleton -- without this, state leaks between
    tests and the order they run in changes the result."""
    health_bus.reset()
    yield
    health_bus.reset()


@pytest.fixture
def client():
    return TestClient(create_app())


# --------------------------------------------------------------------------
# scan round trip
# --------------------------------------------------------------------------

def test_scan_and_live_roundtrip(client):
    r = client.post("/health/scan", json={"window_s": 30})
    assert r.status_code == 200
    mid = r.json()["measurement_id"]
    assert mid

    cmd = health_bus.take_cmd()
    assert cmd["action"] == "start" and cmd["measurement_id"] == mid

    health_bus.set_metrics({"schema_version": 1, "hr_bpm": 71.0, "state": "collecting"})
    assert client.get("/health/live").json()["hr_bpm"] == 71.0


def test_cancel_queues_a_cancel_command(client):
    client.post("/health/scan", json={"window_s": 30})
    health_bus.take_cmd()

    assert client.post("/health/scan/cancel").status_code == 200
    assert health_bus.take_cmd()["action"] == "cancel"


def test_requested_window_reaches_the_perception_node(client):
    """Regression: the API accepted window_s, plumbed it through the bus and the ROS
    topic, and perception then ignored it and used its configured default. A user who
    asked for a 60s scan silently got a 30s one."""
    client.post("/health/scan", json={"window_s": 60})

    assert health_bus.take_cmd()["window_s"] == 60.0


# --------------------------------------------------------------------------
# withheld, not guessed
# --------------------------------------------------------------------------

def test_live_reports_idle_with_no_data(client):
    body = client.get("/health/live").json()

    assert body["state"] == "idle"
    assert body["hr_bpm"] is None
    assert body["hr_confidence"] is None


def test_live_withholds_a_stale_reading(client, monkeypatch):
    """Perception publishes a heart rate, then dies. The API must stop serving it
    rather than show a minutes-old vital sign as if it were live."""
    import orchestrator.web_server.health_bus as hb

    now = [1000.0]
    monkeypatch.setattr(health_bus, "_clock", lambda: now[0])

    health_bus.set_metrics({"schema_version": 1, "hr_bpm": 71.0, "state": "collecting"})
    assert client.get("/health/live").json()["hr_bpm"] == 71.0

    now[0] += hb.METRICS_TTL_S + 1.0  # perception has gone quiet

    body = client.get("/health/live").json()
    assert body["hr_bpm"] is None, "a stale heart rate is still being served as live"
    assert body["state"] == "idle"


def test_hr_is_null_not_zero_when_there_is_no_reading(client):
    """0 bpm renders as a real number in the UI. It must be null."""
    health_bus.set_metrics({"schema_version": 1, "state": "insufficient_quality",
                            "hr_bpm": None, "hr_confidence": None})

    body = client.get("/health/scan/status").json()
    assert body["hr_bpm"] is None
    assert body["hr_bpm"] != 0


# --------------------------------------------------------------------------
# v1 is heart rate only
# --------------------------------------------------------------------------

@pytest.mark.parametrize("path", ["/health/live", "/health/scan/status"])
def test_unsupported_metrics_are_present_and_null(client, path):
    """The contract is that these keys ALWAYS exist and are ALWAYS null -- a client
    must be able to tell "not supported" apart from "this code path forgot the key".

    Asserting presence, not just `body.get(k) is None`: `.get()` returns None for a
    MISSING key too, so that weaker form passes against a payload that omits them
    entirely -- which is exactly the bug this guards."""
    body = client.get(path).json()

    for unsupported in ("resp_bpm", "hrv_sdnn_ms", "spo2_pct"):
        assert unsupported in body, f"{path} omits {unsupported}"
        assert body[unsupported] is None, f"{path} populated {unsupported}"


# --------------------------------------------------------------------------
# input validation at the system boundary
# --------------------------------------------------------------------------

@pytest.mark.parametrize("bad", [
    {"window_s": "abc"},      # was a 500
    {"window_s": None},
    {"window_s": -5},
    {"window_s": 0},
    {"window_s": 100000},
    {"window_s": [30]},
])
def test_invalid_window_is_rejected_not_crashed(client, bad):
    r = client.post("/health/scan", json=bad)

    assert r.status_code == 422, f"{bad} was accepted"
    assert health_bus.take_cmd() is None, f"{bad} still queued a scan"


@pytest.mark.parametrize("raw", ['{"window_s": NaN}', '{"window_s": Infinity}'])
def test_non_finite_window_is_rejected(client, raw):
    """Sent as a raw body on purpose: strict JSON cannot encode NaN/Infinity, so the
    test client refuses to build these -- but Python's json.loads accepts the literals
    happily, so a real client CAN send them and the server must reject them itself."""
    r = client.post("/health/scan", content=raw,
                    headers={"content-type": "application/json"})

    assert r.status_code == 422, f"{raw} was accepted"
    assert health_bus.take_cmd() is None, f"{raw} still queued a scan"


def test_missing_body_uses_the_default_window(client):
    r = client.post("/health/scan")

    assert r.status_code == 200
    assert health_bus.take_cmd()["window_s"] == 30.0
