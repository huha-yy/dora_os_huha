"""Camera health-metrics (rPPG) core. Pure Python, no ROS imports."""

from .config import HealthConfig, Gates
from .types import RgbSample, PulseEstimate, ScanState, GateResult
from .estimator import RPPGEstimator
from .scan import ScanController
from .messages import build_metrics, SCHEMA_VERSION
from .complexion import describe_complexion
from .quality import evaluate_gates

__all__ = [
    "HealthConfig", "Gates", "RgbSample", "PulseEstimate", "ScanState", "GateResult",
    "RPPGEstimator", "ScanController", "build_metrics", "SCHEMA_VERSION",
    "describe_complexion", "evaluate_gates",
]
