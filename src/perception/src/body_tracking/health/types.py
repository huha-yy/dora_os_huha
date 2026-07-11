from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


@dataclass(frozen=True)
class RgbSample:
    t: float  # seconds, real frame timestamp
    r: float
    g: float
    b: float


@dataclass(frozen=True)
class PulseEstimate:
    hr_bpm: Optional[float]
    confidence: float          # 0..1
    spectral_snr: float
    peak_dominance: float


class ScanState(str, Enum):
    IDLE = "idle"
    WARMING = "warming"
    COLLECTING = "collecting"
    INSUFFICIENT_QUALITY = "insufficient_quality"
    COMPLETE = "complete"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class GateResult:
    ok: bool
    reason: Optional[str]
    components: dict = field(default_factory=dict)
