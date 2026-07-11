from body_tracking.health.scan import ScanController
from body_tracking.health.types import ScanState


def test_completes_after_enough_clean_seconds():
    sc = ScanController(target_clean_s=3.0, timeout_s=30.0)
    sc.start("m1", now=0.0)
    t = 0.0
    while sc.state not in (ScanState.COMPLETE, ScanState.FAILED):
        t += 0.5
        sc.update(now=t, gate_ok=True)
    assert sc.state == ScanState.COMPLETE
    assert sc.progress_clean_s >= 3.0
    assert sc.measurement_id == "m1"


def test_bad_quality_does_not_accrue_progress():
    sc = ScanController(target_clean_s=3.0, timeout_s=30.0)
    sc.start("m2", now=0.0)
    for i in range(1, 11):
        sc.update(now=i * 0.5, gate_ok=False)
    assert sc.progress_clean_s == 0.0
    assert sc.state in (ScanState.WARMING, ScanState.INSUFFICIENT_QUALITY)


def test_timeout_fails_the_scan():
    sc = ScanController(target_clean_s=30.0, timeout_s=5.0)
    sc.start("m3", now=0.0)
    sc.update(now=6.0, gate_ok=True)
    assert sc.state == ScanState.FAILED


def test_cancel_sets_state():
    sc = ScanController(target_clean_s=30.0, timeout_s=30.0)
    sc.start("m4", now=0.0)
    sc.cancel(now=1.0)
    assert sc.state == ScanState.CANCELLED
