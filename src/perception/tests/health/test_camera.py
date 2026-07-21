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


# --------------------------------------------------------------------------
# exposure_stable_for -- how the lock feeds the quality gate (Task 16c)
#
# The lock is scan-scoped (the colour stream is shared with fall detection). So:
#   - ambient: no lock; delegate drift-rejection to chroma_drift / illum_delta,
#     so exposure_stable must NOT block the best-effort live overlay.
#   - scan: exposure_stable is True ONLY with a verified lock. A pending or failed
#     lock withholds the scan rather than trusting the auto-regulating camera.
# --------------------------------------------------------------------------

from body_tracking.health.camera import exposure_stable_for


def test_ambient_is_always_stable_regardless_of_lock():
    assert exposure_stable_for(scan_active=False, camera_locked=False)
    assert exposure_stable_for(scan_active=False, camera_locked=True)


def test_a_scan_is_stable_only_when_the_camera_is_verified_locked():
    assert exposure_stable_for(scan_active=True, camera_locked=True)


def test_a_scan_without_a_confirmed_lock_is_not_stable():
    """Lock pending, failed, or the other process silent -> withhold the scan.
    This is the whole point: a scan promises a locked camera."""
    assert not exposure_stable_for(scan_active=True, camera_locked=False)


# --------------------------------------------------------------------------
# lock_satisfied -- the retry decision (Task 16c)
#
# Codex [P1]: skipping a repeated request on want==last_want alone latches a transient
# failure forever. If a lock or an auto-restore fails once, the RealSense publisher
# would never retry -- a scan could not lock (times out), or the camera stays stuck
# locked while idle and fall detection runs on a frozen exposure. Satisfaction must be
# judged on the VERIFIED physical state, so an unsatisfied request retries next tick.
# --------------------------------------------------------------------------

from body_tracking.health.camera import is_scan_locked, lock_satisfied

_LOCKED = {"locked": True, "auto_exposure_off": True,
           "auto_white_balance_off": True, "failures": []}


def test_lock_satisfied_when_both_controls_verified_off():
    assert lock_satisfied(True, _LOCKED)


def test_lock_not_satisfied_when_lock_attempt_failed():
    """The retry case. Lock requested, sensor did not lock -> must retry, not latch."""
    assert not lock_satisfied(True, {"locked": False, "auto_exposure_off": True,
                                     "auto_white_balance_off": False,
                                     "failures": ["device busy"]})


def test_lock_not_satisfied_with_no_state_yet():
    assert not lock_satisfied(True, None)
    assert not lock_satisfied(True, {})


def test_a_partial_auto_restore_is_NOT_a_scan_lock():
    """THE bug. A partial release (AE back on auto, AWB stuck off) sets `locked: True`
    meaning only 'not fully auto'. It must NOT count as a scan lock, or a scan would
    pass exposure_stable while auto-exposure is still running."""
    partial_restore = {"locked": True, "auto": False,
                       "failures": ["auto_white_balance: did not take effect"]}
    assert not is_scan_locked(partial_restore)
    assert not lock_satisfied(True, partial_restore)


def test_is_scan_locked_ignores_the_overloaded_locked_field():
    # locked=True but no verified _off readbacks -> not a scan lock.
    assert not is_scan_locked({"locked": True})
    assert is_scan_locked(_LOCKED)


def test_unlock_satisfied_only_when_auto_restored_cleanly():
    assert lock_satisfied(False, {"locked": False, "auto": True, "failures": []})


def test_unlock_not_satisfied_when_restore_failed():
    """Auto-restore threw: the camera may still be locked. Retry, do not latch idle."""
    assert not lock_satisfied(False, {"auto": True, "failures": ["set_option: busy"]})


def test_unlock_not_satisfied_while_still_locked():
    """locked=True means the restore never took -- unlock is not done."""
    assert not lock_satisfied(False, {"locked": True})
    assert not lock_satisfied(False, None)


# --------------------------------------------------------------------------
# restore_auto_on_sensor -- the release path, verified (Codex [P1])
#
# Symmetric with the lock path: a set_option to re-enable auto can be silently ignored,
# and reporting "auto restored" without reading it back leaves the shared colour stream
# locked while claiming it is free -- fall detection then runs on a frozen exposure and
# lock_satisfied stops retrying the release.
# --------------------------------------------------------------------------

from body_tracking.health.camera import restore_auto_on_sensor


def test_restore_auto_succeeds_from_locked():
    s = FakeSensor()
    s.values[AE] = 0.0
    s.values[AWB] = 0.0                    # camera currently locked

    r = restore_auto_on_sensor(s, AE, AWB)

    assert r["auto"] and not r["locked"]
    assert r["failures"] == []
    assert s.get_option(AE) == 1.0 and s.get_option(AWB) == 1.0


def test_restore_reports_failure_when_a_control_is_silently_ignored():
    """The bug: AWB restore accepted but ignored. Must NOT report auto=True, or the
    lease/retry would stop while the camera stays locked."""
    s = FakeSensor(sticky=(AWB,))
    s.values[AE] = 0.0
    s.values[AWB] = 0.0

    r = restore_auto_on_sensor(s, AE, AWB)

    assert not r["auto"], "reported auto restored when AWB was silently ignored"
    assert r["locked"], "AWB still off -> camera is still (partly) locked"
    assert any("did not take effect" in f for f in r["failures"])


def test_restore_reports_failure_on_driver_error():
    s = FakeSensor(raises=(AE,))
    s.values[AE] = 0.0

    r = restore_auto_on_sensor(s, AE, AWB)

    assert not r["auto"]
    assert r["failures"]


def test_restore_then_lock_satisfied_agree():
    """The whole point: a failed restore must keep lock_satisfied(False) retrying."""
    s = FakeSensor(sticky=(AWB,))
    s.values[AWB] = 0.0

    r = restore_auto_on_sensor(s, AE, AWB)

    assert not lock_satisfied(False, r), "a failed restore was treated as done"


# --------------------------------------------------------------------------
# window_captured_under_lock -- the lock must cover the FULL analysis window (Codex [P1])
#
# A per-instant lock check is not enough: the estimator transforms a window_s window, and
# for the first window_s after a lock (or a relock after a drop) that window still holds
# pre-lock, auto-AE/AWB frames. A short scan would otherwise complete on a mostly-pre-lock
# window. The window is trustworthy only once the lock has held continuously >= window_s.
# --------------------------------------------------------------------------

from body_tracking.health.camera import window_captured_under_lock

WINDOW = 10.0


def test_not_covered_immediately_after_the_lock_engages():
    """t=0 lock; at t=1 the 10s window is 9s pre-lock. Must NOT be trusted."""
    assert not window_captured_under_lock(True, lock_since=0.0, now=1.0, window_s=WINDOW)


def test_not_covered_until_a_full_window_has_elapsed():
    assert not window_captured_under_lock(True, lock_since=0.0, now=9.9, window_s=WINDOW)


def test_covered_once_a_full_window_under_lock_has_elapsed():
    assert window_captured_under_lock(True, lock_since=0.0, now=10.0, window_s=WINDOW)
    assert window_captured_under_lock(True, lock_since=0.0, now=25.0, window_s=WINDOW)


def test_not_covered_when_not_locked_now():
    """Even with an old lock_since, a dropped lock means the newest frames are unlocked."""
    assert not window_captured_under_lock(False, lock_since=0.0, now=100.0, window_s=WINDOW)


def test_not_covered_with_no_lock_start():
    assert not window_captured_under_lock(True, lock_since=None, now=100.0, window_s=WINDOW)


def test_a_relock_restarts_the_window_clock():
    """After a drop the node resets lock_since; a short scan must not immediately trust
    the window again -- it still contains frames from the unlocked gap."""
    # relocked at t=50; at t=55 only 5s of the 10s window is post-relock.
    assert not window_captured_under_lock(True, lock_since=50.0, now=55.0, window_s=WINDOW)
    assert window_captured_under_lock(True, lock_since=50.0, now=60.0, window_s=WINDOW)
