from fastapi import APIRouter

from ..web_server.health_bus import health_bus

router = APIRouter()

_IDLE = {"schema_version": 1, "state": "idle", "hr_bpm": None, "hr_confidence": None}


@router.get("/live")
async def live():
    return health_bus.get_metrics() or _IDLE


@router.post("/scan")
async def start_scan(body: dict | None = None):
    window_s = float((body or {}).get("window_s", 30.0))
    mid = health_bus.request_scan(window_s)
    return {"measurement_id": mid}


@router.get("/scan/status")
async def scan_status():
    return health_bus.get_metrics() or _IDLE


@router.post("/scan/cancel")
async def cancel_scan():
    health_bus.request_cancel()
    return {"status": "ok"}
