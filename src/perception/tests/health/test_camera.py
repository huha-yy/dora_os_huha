"""The camera lock, and the honesty of the lock report.

`exposure_stable` is set from `LockResult.locked`. A lock we *believe* in but do not
have is worse than no lock: it marks the window stable while the camera keeps hunting,
which is the exact failure the gate exists to prevent. So every path that cannot prove
the lock took effect must report False.
"""

import pytest

from body_tracking.health.camera import lock_color_sensor

AE = "ae"       # stand-ins for rs.option.enable_auto_exposure / ..._white_balance
AWB = "awb"


class FakeSensor:
    def __init__(self, supported=(AE, AWB), sticky=(), raises=()):
        # `sticky`: options whose set_option is accepted but silently ignored.
        # `raises`: options whose set_option throws.
        self.values = {AE: 1.0, AWB: 1.0}
        self.supported = set(supported)
        self.sticky = set(sticky)
        self.raises = set(raises)
        self.writes = []

    def supports(self, option):
        return option in self.supported

    def set_option(self, option, value):
        self.writes.append((option, value))
        if option in self.raises:
            raise RuntimeError("device busy")
        if option in self.sticky:
            return                      # accepted, ignored
        self.values[option] = value

    def get_option(self, option):
        return self.values[option]


def test_a_healthy_sensor_locks_both_controls():
    s = FakeSensor()

    r = lock_color_sensor(s, AE, AWB)

    assert r.locked
    assert r.auto_exposure_off and r.auto_white_balance_off
    assert r.failures == []
    assert s.get_option(AE) == 0.0 and s.get_option(AWB) == 0.0


def test_lock_actually_writes_zero_to_both():
    s = FakeSensor()

    lock_color_sensor(s, AE, AWB)

    assert (AE, 0.0) in s.writes
    assert (AWB, 0.0) in s.writes


def test_a_silently_ignored_write_is_not_a_lock():
    """THE important one. set_option can be accepted and do nothing -- unsupported
    control, firmware quirk, another process owning the device. Trusting the write
    would report exposure_stable=True while the camera carries on hunting."""
    s = FakeSensor(sticky=(AWB,))

    r = lock_color_sensor(s, AE, AWB)

    assert not r.locked, "a write that did not take effect was reported as a lock"
    assert r.auto_exposure_off
    assert not r.auto_white_balance_off
    assert any("did not take effect" in f for f in r.failures)


def test_an_unsupported_control_is_not_a_lock():
    s = FakeSensor(supported=(AE,))     # no AWB control at all

    r = lock_color_sensor(s, AE, AWB)

    assert not r.locked
    assert any("not supported" in f for f in r.failures)


def test_a_driver_error_is_not_a_lock():
    s = FakeSensor(raises=(AE,))

    r = lock_color_sensor(s, AE, AWB)

    assert not r.locked
    assert any("device busy" in f for f in r.failures)


def test_partial_lock_is_never_reported_as_locked():
    """AE off but AWB still hunting still scrambles the R/G/B ratios POS/CHROM read.
    Half a lock is not a lock."""
    for sticky in ((AE,), (AWB,)):
        r = lock_color_sensor(FakeSensor(sticky=sticky), AE, AWB)
        assert not r.locked, f"reported locked with {sticky} not actually locked"


def test_failures_are_reported_for_diagnosis():
    r = lock_color_sensor(FakeSensor(supported=()), AE, AWB)

    assert not r.locked
    assert len(r.failures) == 2, "both controls failed; both should be named"


def test_as_dict_is_json_safe_for_the_lock_state_topic():
    import json

    r = lock_color_sensor(FakeSensor(), AE, AWB)

    payload = json.dumps(r.as_dict())   # must not raise
    assert json.loads(payload)["locked"] is True
