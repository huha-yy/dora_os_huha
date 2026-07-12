"""Motion and illumination artifact metrics for the rPPG quality gates.

Both are computed over the whole analysis window rather than frame-to-frame. That
is the physically meaningful quantity -- rPPG needs the ROI stationary and the
lighting steady across the window being transformed -- and a per-frame delta would
be frame-rate dependent and far too noisy to threshold.

Every degenerate input returns FAIL_CLOSED. Returning 0.0 for "cannot tell" would
*pass* the gate, which is precisely the defect this module exists to fix: head
motion aliases into the 0.7-4 Hz pulse band, so an ungated moving subject produces
a confident wrong heart rate rather than no heart rate.

Pure Python + numpy. No ROS.
"""

from typing import Optional, Sequence

import numpy as np

from .types import RgbSample

# Far above any real threshold, so a degenerate window always fails the gate.
FAIL_CLOSED = 1e9

MIN_SAMPLES = 2  # dispersion is undefined below this


def _finite(*values: Optional[float]) -> bool:
    return all(v is not None and np.isfinite(v) for v in values)


def motion_metric(samples: Sequence[RgbSample]) -> float:
    """Spatial dispersion of the ROI centroid over the window, in face widths.

        motion = sqrt(var(cx) + var(cy)) / mean(face_width)

    Normalising by face width makes this scale- and distance-invariant, so the
    same head movement scores the same close-up as far away. Compare against
    Gates.max_motion (0.05): a still subject with a pixel or two of detector
    jitter lands near 0.01; a subject drifting half a face width lands near 0.15.
    """
    if len(samples) < MIN_SAMPLES:
        return FAIL_CLOSED

    cx, cy, widths = [], [], []
    for s in samples:
        if not _finite(s.cx, s.cy, s.w):
            return FAIL_CLOSED
        if s.w <= 0.0:
            return FAIL_CLOSED
        cx.append(s.cx)
        cy.append(s.cy)
        widths.append(s.w)

    mean_w = float(np.mean(widths))
    if mean_w <= 0.0:
        return FAIL_CLOSED

    dispersion = float(np.sqrt(np.var(cx) + np.var(cy)))
    motion = dispersion / mean_w
    return motion if np.isfinite(motion) else FAIL_CLOSED


def illumination_metric(samples: Sequence[RgbSample]) -> float:
    """Coefficient of variation of ROI luminance over the window.

        illum_delta = std(luminance) / mean(luminance)

    Relative, not absolute: dividing by the mean keeps a dim scene and a bright
    scene with the same proportional swing scoring alike, and -- critically --
    keeps the pulse itself (a ~0.1-1% luminance modulation) far below
    Gates.max_illum_delta (0.15). An absolute threshold here would gate out the
    very signal we are trying to measure.
    """
    if len(samples) < MIN_SAMPLES:
        return FAIL_CLOSED

    lums = []
    for s in samples:
        if not _finite(s.r, s.g, s.b):
            return FAIL_CLOSED
        lums.append((s.r + s.g + s.b) / 3.0)

    mean_lum = float(np.mean(lums))
    if mean_lum <= 0.0:  # black ROI -- would divide by zero
        return FAIL_CLOSED

    illum = float(np.std(lums)) / mean_lum
    return illum if np.isfinite(illum) else FAIL_CLOSED
