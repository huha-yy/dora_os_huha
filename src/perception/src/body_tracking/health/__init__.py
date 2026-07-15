"""Camera health-metrics (rPPG) core. Pure Python, no ROS imports."""

from .config import HealthConfig, Gates
from .types import RgbSample, PulseEstimate, ScanState, GateResult
from .estimator import RPPGEstimator
from .scan import ScanController
from .messages import build_metrics, SCHEMA_VERSION
from .complexion import describe_complexion
from .quality import evaluate_gates
from .artifacts import motion_metric, illumination_metric, chroma_drift_metric, FAIL_CLOSED
from .camera import (
    lock_color_sensor, restore_auto_on_sensor, lock_satisfied, is_scan_locked,
    exposure_stable_for, window_captured_under_lock, LockResult,
)

__all__ = [
    "HealthConfig", "Gates", "RgbSample", "PulseEstimate", "ScanState", "GateResult",
    "RPPGEstimator", "ScanController", "build_metrics", "SCHEMA_VERSION",
    "describe_complexion", "evaluate_gates",
    "motion_metric", "illumination_metric", "chroma_drift_metric", "FAIL_CLOSED",
    "lock_color_sensor", "restore_auto_on_sensor", "lock_satisfied",
    "is_scan_locked", "exposure_stable_for", "window_captured_under_lock",
    "LockResult",
]
