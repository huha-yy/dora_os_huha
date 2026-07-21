"""HealthBus: the orchestrator's cache of the last metrics published by perception.

The critical property is STALENESS. The bus is the only thing between a dead
perception node and a heart rate rendered in the UI. If perception crashes, the
camera is unplugged, or ROS disconnects, nothing arrives -- and a bus that keeps
serving its last value will show a heart rate from minutes ago as if it were live.

The perception node's own 5s frame-staleness guard does not help here: it only runs
while that node is alive and publishing. Node death defeats it entirely.

A stale vital sign presented as current is exactly the plausible-but-wrong number
AGENTS.md section 5 forbids. Withhold it instead.
"""

import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1]
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from orchestrator.web_server.health_bus import METRICS_TTL_S, HealthBus  # noqa: E402


class FakeClock:
    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def bus(clock):
    return HealthBus(clock=clock)


# --------------------------------------------------------------------------
# staleness -- the reason this class needs tests at all
# --------------------------------------------------------------------------

def test_fresh_metrics_are_served(bus, clock):
    bus.set_metrics({"hr_bpm": 72.0})
    clock.advance(METRICS_TTL_S / 2)

    assert bus.get_metrics()["hr_bpm"] == 72.0


def test_stale_metrics_are_withheld(bus, clock):
    """Perception died. The last reading must NOT keep being served as live."""
    bus.set_metrics({"hr_bpm": 72.0})

    clock.advance(METRICS_TTL_S + 0.1)

    assert bus.get_metrics() is None


def test_metrics_go_stale_exactly_once_past_the_ttl(bus, clock):
    bus.set_metrics({"hr_bpm": 72.0})

    clock.advance(METRICS_TTL_S - 0.01)
    assert bus.get_metrics() is not None, "withheld too early"

    clock.advance(0.02)
    assert bus.get_metrics() is None, "still served past the TTL"


def test_a_fresh_publish_revives_a_stale_bus(bus, clock):
    """Perception comes back. The bus must start serving again."""
    bus.set_metrics({"hr_bpm": 72.0})
    clock.advance(METRICS_TTL_S + 5.0)
    assert bus.get_metrics() is None

    bus.set_metrics({"hr_bpm": 65.0})

    assert bus.get_metrics()["hr_bpm"] == 65.0


def test_empty_bus_returns_none(bus):
    assert bus.get_metrics() is None


# --------------------------------------------------------------------------
# defensive copying -- the bus is shared across threads (ROS executor + FastAPI)
# --------------------------------------------------------------------------

def test_caller_cannot_mutate_the_stored_metrics(bus):
    payload = {"hr_bpm": 72.0}
    bus.set_metrics(payload)

    payload["hr_bpm"] = 999.0  # caller keeps its reference and scribbles on it

    assert bus.get_metrics()["hr_bpm"] == 72.0


def test_reader_cannot_mutate_the_stored_metrics(bus):
    bus.set_metrics({"hr_bpm": 72.0})

    bus.get_metrics()["hr_bpm"] = 999.0

    assert bus.get_metrics()["hr_bpm"] == 72.0


# --------------------------------------------------------------------------
# scan commands
# --------------------------------------------------------------------------

def test_take_cmd_consumes_the_command(bus):
    bus.request_scan(30.0)

    assert bus.take_cmd()["action"] == "start"
    assert bus.take_cmd() is None, "the same command was delivered twice"


def test_request_scan_returns_a_unique_measurement_id(bus):
    a = bus.request_scan(30.0)
    bus.take_cmd()
    b = bus.request_scan(30.0)

    assert a != b


def test_scan_command_carries_the_window(bus):
    bus.request_scan(45.0)

    assert bus.take_cmd()["window_s"] == 45.0


def test_cancel_supersedes_a_pending_start(bus):
    """Both queued before the 5 Hz drain runs: the user's LAST intent must win.
    Delivering the stale `start` would kick off a scan the user just cancelled."""
    bus.request_scan(30.0)
    bus.request_cancel()

    assert bus.take_cmd()["action"] == "cancel"


def test_empty_bus_has_no_command(bus):
    assert bus.take_cmd() is None
