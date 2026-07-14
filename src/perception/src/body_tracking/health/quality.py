from .config import Gates
from .types import GateResult

# Note: gates.min_confidence is NOT a hard gate here. Confidence is a separate
# graded score applied by the pulse estimator, not a binary quality check.


def evaluate_gates(components: dict, gates: Gates) -> GateResult:
    """Evaluate camera quality gates against component readings.

    This function enforces a fail-safe contract: the check order is intentionally
    stable, and the first failing gate's reason is returned. This means that a
    regression in check order would be immediately visible in test failures.

    Each component key uses a deliberately chosen default on the "reject" side
    (False for booleans, 1e9 for distances/times) so that an omitted key causes
    the reading to be withheld, never accepted. This is critical since the
    perception node builds the components dict by hand.

    Args:
        components: Dict of component readings (face_present, motion, etc).
        gates: Configuration thresholds (min_fps, max_motion, etc).

    Returns:
        GateResult with ok=True/False, reason (first failure or None), and
        a copy of the input components dict for debugging.
    """
    c = components
    checks = [
        (not c.get("face_present", False), "no_face"),
        (not c.get("single_target", False), "multiple_targets"),
        (not c.get("roi_in_bounds", False), "roi_out_of_bounds"),
        (c.get("face_px", 0) < gates.min_face_px, "face_too_small"),
        (c.get("roi_px", 0) < gates.min_roi_px, "roi_too_small"),
        (c.get("effective_fps", 0.0) < gates.min_fps, "low_fps"),
        (c.get("drop_ratio", 1.0) > gates.max_drop_ratio, "dropped_frames"),
        (c.get("jitter_ms", 1e9) > gates.max_jitter_ms, "timestamp_jitter"),
        (c.get("motion", 1e9) > gates.max_motion, "head_motion"),
        (c.get("illum_delta", 1e9) > gates.max_illum_delta, "illumination_change"),
        (c.get("chroma_drift", 1e9) > gates.max_chroma_drift, "white_balance_drift"),
        (not c.get("exposure_stable", False), "exposure_unstable"),
    ]
    for failed, reason in checks:
        if failed:
            return GateResult(ok=False, reason=reason, components=dict(c))
    return GateResult(ok=True, reason=None, components=dict(c))
