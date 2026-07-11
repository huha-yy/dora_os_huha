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


def test_large_gap_credits_at_most_max_dt_s():
    # A single update() call 25s after start must not "complete" a scan
    # that only requires 3.0s of clean time — it should credit at most
    # max_dt_s (default 2.0s), not the full elapsed gap.
    sc = ScanController(target_clean_s=3.0, timeout_s=30.0)
    sc.start("m5", now=0.0)
    sc.update(now=25.0, gate_ok=True)
    assert sc.progress_clean_s == 2.0
    assert sc.state == ScanState.COLLECTING


def test_custom_max_dt_s_is_respected():
    sc = ScanController(target_clean_s=3.0, timeout_s=30.0, max_dt_s=0.5)
    sc.start("m6", now=0.0)
    sc.update(now=10.0, gate_ok=True)
    assert sc.progress_clean_s == 0.5
    assert sc.state == ScanState.COLLECTING


def test_backwards_now_is_ignored_and_does_not_corrupt_baseline():
    sc = ScanController(target_clean_s=3.0, timeout_s=30.0)
    sc.start("m7", now=10.0)
    sc.update(now=12.0, gate_ok=True)
    assert sc.progress_clean_s == 2.0

    # Stale/out-of-order timestamp: must not accrue and must not rewind
    # the internal time baseline.
    sc.update(now=5.0, gate_ok=True)
    assert sc.progress_clean_s == 2.0
    assert sc.state != ScanState.COMPLETE

    # A subsequent normal call must compute dt against the un-rewound
    # baseline (12.0), not the stale one (5.0).
    sc.update(now=13.0, gate_ok=True)
    assert sc.progress_clean_s == 3.0
    assert sc.state == ScanState.COMPLETE


def test_recovery_from_insufficient_quality_resumes_prior_progress():
    sc = ScanController(target_clean_s=3.0, timeout_s=30.0)
    sc.start("m8", now=0.0)
    sc.update(now=1.0, gate_ok=True)
    sc.update(now=2.0, gate_ok=True)
    assert sc.state == ScanState.COLLECTING
    assert sc.progress_clean_s == 2.0

    # Transient occlusion/poor lighting: quality drops.
    sc.update(now=2.5, gate_ok=False)
    assert sc.state == ScanState.INSUFFICIENT_QUALITY
    assert sc.progress_clean_s == 2.0

    # Quality recovers: accrual resumes from prior progress, not from 0.
    sc.update(now=3.0, gate_ok=True)
    assert sc.state == ScanState.COLLECTING
    assert sc.progress_clean_s == 2.5

    sc.update(now=3.5, gate_ok=True)
    assert sc.state == ScanState.COMPLETE
    assert sc.progress_clean_s == 3.0


def test_timeout_wins_over_completion_in_same_update():
    # Target is reachable in the same call that also exceeds the timeout;
    # FAILED must take precedence over COMPLETE.
    sc = ScanController(target_clean_s=3.0, timeout_s=5.0)
    sc.start("m9", now=0.0)
    sc.update(now=6.0, gate_ok=True)
    assert sc.state == ScanState.FAILED
    assert sc.progress_clean_s == 0.0


def test_restart_while_running_resets_progress_and_adopts_new_id():
    sc = ScanController(target_clean_s=3.0, timeout_s=30.0)
    sc.start("m10", now=0.0)
    sc.update(now=1.0, gate_ok=True)
    sc.update(now=2.0, gate_ok=True)
    assert sc.progress_clean_s == 2.0
    assert sc.state == ScanState.COLLECTING

    # User presses Scan again mid-run: restart discards prior progress.
    sc.start("m11", now=100.0)
    assert sc.progress_clean_s == 0.0
    assert sc.measurement_id == "m11"
    assert sc.state == ScanState.WARMING
