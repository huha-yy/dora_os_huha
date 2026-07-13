import math

from fastapi import APIRouter, HTTPException

from ..web_server.health_bus import health_bus

router = APIRouter()

DEFAULT_WINDOW_S = 30.0
MIN_WINDOW_S = 5.0
MAX_WINDOW_S = 120.0


def _idle() -> dict:
    """The payload served when there is no reading -- no data yet, or perception has
    gone quiet and its last metrics have expired.

    A fresh dict each call: a module-level constant would be handed out by reference
    and could be mutated by a caller.

    The unsupported metrics are present and null, exactly as build_metrics() emits
    them. v1 is heart rate only, and the contract is that these keys ALWAYS exist and
    are ALWAYS null -- a client must be able to distinguish "not supported" from "key
    missing because this code path forgot about it".
    """
    return {
        "schema_version": 1,
        "state": "idle",
        "hr_bpm": None,
        "hr_confidence": None,
        "resp_bpm": None,
        "hrv_sdnn_ms": None,
        "spo2_pct": None,
    }


def _parse_window(body: dict | None) -> float:
    """Validate at the system boundary. `float("abc")` used to raise straight out of
    the handler as a 500; NaN and negatives were accepted and forwarded to the
    perception node."""
    raw = (body or {}).get("window_s", DEFAULT_WINDOW_S)
    try:
        window_s = float(raw)
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail=f"window_s must be a number, got {raw!r}")
    if not math.isfinite(window_s):
        raise HTTPException(status_code=422, detail="window_s must be finite")
    if not (MIN_WINDOW_S <= window_s <= MAX_WINDOW_S):
        raise HTTPException(
            status_code=422,
            detail=f"window_s must be between {MIN_WINDOW_S} and {MAX_WINDOW_S}, got {window_s}",
        )
    return window_s


@router.get("/live")
async def live():
    # get_metrics() returns None once perception goes quiet, so a stale heart rate is
    # never served as live -- it degrades to "idle, no reading".
    return health_bus.get_metrics() or _idle()


@router.post("/scan")
async def start_scan(body: dict | None = None):
    window_s = _parse_window(body)
    mid = health_bus.request_scan(window_s)
    return {"measurement_id": mid, "window_s": window_s}


@router.get("/scan/status")
async def scan_status():
    return health_bus.get_metrics() or _idle()


@router.post("/scan/cancel")
async def cancel_scan():
    health_bus.request_cancel()
    return {"status": "ok"}
