"""Camera health-metrics (rPPG) core. Pure Python, no ROS imports."""

from .config import HealthConfig, Gates
from .types import RgbSample, PulseEstimate, ScanState, GateResult
from .estimator import RPPGEstimator
from .scan import ScanController
from .messages import build_metrics, SCHEMA_VERSION
from .complexion import describe_complexion
from .quality import evaluate_gates
from .artifacts import motion_metric, illumination_metric, FAIL_CLOSED

__all__ = [
    "HealthConfig", "Gates", "RgbSample", "PulseEstimate", "ScanState", "GateResult",
    "RPPGEstimator", "ScanController", "build_metrics", "SCHEMA_VERSION",
    "describe_complexion", "evaluate_gates",
    "motion_metric", "illumination_metric", "FAIL_CLOSED",
]
