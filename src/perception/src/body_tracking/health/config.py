from dataclasses import dataclass, field, fields


@dataclass(frozen=True)
class Gates:
    min_fps: float = 15.0
    max_drop_ratio: float = 0.2
    min_face_px: int = 120
    min_roi_px: int = 3000
    max_jitter_ms: float = 20.0
    max_motion: float = 0.05
    max_illum_delta: float = 0.15
    min_confidence: float = 0.5

    @classmethod
    def from_dict(cls, d: dict) -> "Gates":
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in (d or {}).items() if k in known})


@dataclass(frozen=True)
class HealthConfig:
    enabled: bool = True
    backend: str = "pos"
    detector: str = "mediapipe_face"   # or "pose_fallback"
    ambient_window_s: float = 10.0
    scan_window_s: float = 30.0        # target CLEAN seconds
    scan_timeout_s: float = 90.0       # wall-clock guard
    lock_camera_on_scan: bool = True
    complexion_enabled: bool = True
    gates: Gates = field(default_factory=Gates)

    @classmethod
    def default(cls) -> "HealthConfig":
        return cls()

    @classmethod
    def from_dict(cls, d: dict) -> "HealthConfig":
        d = dict(d or {})
        gates = Gates.from_dict(d.pop("gates", {}) or {})
        known = {f.name for f in fields(cls)} - {"gates"}
        kwargs = {k: v for k, v in d.items() if k in known}
        return cls(gates=gates, **kwargs)
