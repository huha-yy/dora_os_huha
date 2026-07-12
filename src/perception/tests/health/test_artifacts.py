"""Task 15b: motion and illumination artifact metrics.

These two metrics are the primary defence against publishing a plausible-but-wrong
heart rate. Head motion aliases directly into the 0.7-4 Hz pulse band, so a moving
subject does not yield *no* reading -- it yields a *confident wrong* one.

Every degenerate input must fail CLOSED (return a gate-failing value), never 0.0.
"""

import math

import numpy as np
import pytest

from body_tracking.health.artifacts import (
    FAIL_CLOSED,
    illumination_metric,
    motion_metric,
)
from body_tracking.health.config import Gates
from body_tracking.health.types import RgbSample

GATES = Gates()  # max_motion=0.05, max_illum_delta=0.15


def _samples(centroids, widths, lums=None):
    """Build a sample window. `lums` defaults to a constant grey."""
    n = len(centroids)
    if lums is None:
        lums = [100.0] * n
    return [
        RgbSample(t=float(i) / 30.0, r=lums[i], g=lums[i], b=lums[i],
                  cx=centroids[i][0], cy=centroids[i][1], w=widths[i])
        for i in range(n)
    ]


# --------------------------------------------------------------------------
# motion
# --------------------------------------------------------------------------

def test_still_subject_passes_the_motion_gate():
    """A still face still jitters a pixel or two from detector noise."""
    rng = np.random.default_rng(0)
    jitter = rng.uniform(-1.5, 1.5, size=(60, 2))
    centroids = [(320.0 + dx, 240.0 + dy) for dx, dy in jitter]
    win = _samples(centroids, [150.0] * 60)

    motion = motion_metric(win)

    assert motion < GATES.max_motion
    assert motion < 0.02  # ~1.5px jitter on a 150px face


def test_subject_drifting_half_a_face_width_fails_the_motion_gate():
    """The exact case the gate exists for: the subject moves during the window."""
    centroids = [(320.0 + 75.0 * i / 59.0, 240.0) for i in range(60)]
    win = _samples(centroids, [150.0] * 60)

    motion = motion_metric(win)

    assert motion > GATES.max_motion


def test_motion_is_scale_invariant():
    """Same motion, twice the face size and twice the pixels, must score the same.

    Guards the normalisation: an implementation that returns raw pixel dispersion
    would double here, and would then gate a close-up subject differently from a
    distant one performing identical movement.
    """
    near = _samples([(100.0 + 2.0 * i, 50.0) for i in range(30)], [200.0] * 30)
    far = _samples([(50.0 + 1.0 * i, 25.0) for i in range(30)], [100.0] * 30)

    assert motion_metric(near) == pytest.approx(motion_metric(far), rel=1e-9)


def test_motion_counts_vertical_displacement_too():
    """A nod must be caught, not just a side-to-side turn."""
    horizontal = _samples([(320.0 + 75.0 * i / 59.0, 240.0) for i in range(60)], [150.0] * 60)
    vertical = _samples([(320.0, 240.0 + 75.0 * i / 59.0) for i in range(60)], [150.0] * 60)

    assert motion_metric(vertical) == pytest.approx(motion_metric(horizontal), rel=1e-9)
    assert motion_metric(vertical) > GATES.max_motion


# --------------------------------------------------------------------------
# illumination
# --------------------------------------------------------------------------

def test_constant_illumination_passes():
    win = _samples([(320.0, 240.0)] * 30, [150.0] * 30, lums=[100.0] * 30)

    assert illumination_metric(win) == pytest.approx(0.0, abs=1e-12)


def test_pulse_modulation_does_not_trip_the_illumination_gate():
    """DISCRIMINATIVE: the pulse *is* a luminance modulation (~0.1-1%).

    An implementation that thresholds absolute luminance change, or that forgets
    to normalise by the mean, gates out the very signal we are trying to measure.
    """
    lums = [100.0 * (1.0 + 0.005 * math.sin(2 * math.pi * 1.2 * i / 30.0)) for i in range(300)]
    win = _samples([(320.0, 240.0)] * 300, [150.0] * 300, lums=lums)

    illum = illumination_metric(win)

    assert illum < GATES.max_illum_delta
    assert illum < 0.01  # a 0.5% modulation must stay ~0.5%-ish, not blow up


def test_lighting_step_change_fails_the_illumination_gate():
    lums = [100.0] * 30 + [150.0] * 30
    win = _samples([(320.0, 240.0)] * 60, [150.0] * 60, lums=lums)

    assert illumination_metric(win) > GATES.max_illum_delta


def test_illumination_is_brightness_invariant():
    """A dim scene and a bright scene with the same *relative* swing score alike."""
    dim = _samples([(320.0, 240.0)] * 40, [150.0] * 40,
                   lums=[40.0 + 4.0 * (i % 2) for i in range(40)])
    bright = _samples([(320.0, 240.0)] * 40, [150.0] * 40,
                      lums=[200.0 + 20.0 * (i % 2) for i in range(40)])

    assert illumination_metric(dim) == pytest.approx(illumination_metric(bright), rel=1e-9)


# --------------------------------------------------------------------------
# fail-closed  (0.0 would PASS the gate -- that is the bug being fixed)
#
# These assert the returned value FAILS ITS GATE, deliberately not that it equals
# FAIL_CLOSED. Asserting `>= FAIL_CLOSED` would be tautological: mutate the
# constant to 0.0 and `0.0 >= 0.0` still holds, so the test would survive exactly
# the regression it is meant to catch.
# --------------------------------------------------------------------------

def _assert_gate_fails(metric, win):
    threshold = GATES.max_motion if metric is motion_metric else GATES.max_illum_delta
    value = metric(win)
    assert not math.isnan(value), "NaN compares False against every threshold -- it would PASS"
    assert value > threshold, f"{value} does not fail the gate ({threshold})"


@pytest.mark.parametrize("metric", [motion_metric, illumination_metric])
def test_empty_window_fails_closed(metric):
    _assert_gate_fails(metric, [])


@pytest.mark.parametrize("metric", [motion_metric, illumination_metric])
def test_single_sample_fails_closed(metric):
    """One sample has no dispersion. Reporting 0.0 would silently pass the gate."""
    _assert_gate_fails(metric, _samples([(320.0, 240.0)], [150.0]))


def test_motion_fails_closed_when_roi_geometry_is_missing():
    """The node must populate cx/cy/w. If it ever regresses, withhold the reading."""
    win = [
        RgbSample(t=0.0, r=100.0, g=100.0, b=100.0),  # no cx/cy/w
        RgbSample(t=0.1, r=100.0, g=100.0, b=100.0),
    ]

    _assert_gate_fails(motion_metric, win)


def test_motion_fails_closed_when_geometry_is_partially_missing():
    win = _samples([(320.0, 240.0), (321.0, 240.0)], [150.0, 150.0])
    win[1] = RgbSample(t=win[1].t, r=100.0, g=100.0, b=100.0, cx=321.0, cy=240.0, w=None)

    _assert_gate_fails(motion_metric, win)


def test_motion_fails_closed_on_non_positive_face_width():
    _assert_gate_fails(motion_metric, _samples([(320.0, 240.0), (321.0, 240.0)], [150.0, 0.0]))


def test_motion_fails_closed_on_non_finite_geometry():
    _assert_gate_fails(
        motion_metric, _samples([(320.0, 240.0), (float("nan"), 240.0)], [150.0, 150.0])
    )


def test_illumination_fails_closed_on_black_roi():
    """mean(lum) == 0 would be a divide-by-zero; must not become 0.0 or nan."""
    _assert_gate_fails(
        illumination_metric, _samples([(320.0, 240.0)] * 10, [150.0] * 10, lums=[0.0] * 10)
    )


def test_illumination_fails_closed_on_non_finite_luminance():
    _assert_gate_fails(
        illumination_metric,
        _samples([(320.0, 240.0)] * 10, [150.0] * 10, lums=[100.0] * 9 + [float("nan")]),
    )


def test_fail_closed_constant_actually_fails_both_gates():
    """Pins the constant itself, so lowering it can never quietly open the gates."""
    assert FAIL_CLOSED > GATES.max_motion
    assert FAIL_CLOSED > GATES.max_illum_delta


@pytest.mark.parametrize("metric", [motion_metric, illumination_metric])
def test_metrics_never_return_nan(metric):
    """A NaN compares False against every threshold, so it would PASS the gate."""
    degenerate = [
        [],
        _samples([(320.0, 240.0)], [150.0]),
        _samples([(320.0, 240.0)] * 5, [0.0] * 5, lums=[0.0] * 5),
    ]
    for win in degenerate:
        assert not math.isnan(metric(win))
