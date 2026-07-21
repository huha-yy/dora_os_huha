# orchestrator/http/app.py
import asyncio
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from ..routers import events, actions, health
from .frame_bus import frame_bus

UI_DIR = Path(__file__).parent / "ui"

# 1x1 gray JPEG placeholder shown before the first camera frame arrives.
_PLACEHOLDER_JPEG = bytes.fromhex(
    "ffd8ffe000104a46494600010100000100010000ffdb004300080606070605080707"
    "07090908"
    + "0a" * 8
    + "ffc0000b080001000101011100ffc4001f0000010501010101010100000000000000"
    "000102030405060708090a0bffda0008010100003f00d2cf20ffd9"
)


def _mjpeg_generator():
    boundary = b"--frame"
    while True:
        jpeg = frame_bus.get_jpeg() or _PLACEHOLDER_JPEG
        yield (
            boundary
            + b"\r\nContent-Type: image/jpeg\r\nContent-Length: "
            + str(len(jpeg)).encode()
            + b"\r\n\r\n"
            + jpeg
            + b"\r\n"
        )
        frame_bus.wait_for_new(timeout=0.1)


def create_app() -> FastAPI:
    app = FastAPI(title="Dorabot Orchestrator")

    app.include_router(events.router, prefix="/events", tags=["events"])
    app.include_router(actions.router, prefix="/actions", tags=["actions"])
    app.include_router(health.router, prefix="/health", tags=["health"])

    @app.get("/health")
    async def health_check():
        return {"status": "ok"}

    @app.get("/video/status")
    async def video_status():
        age = frame_bus.age
        return {
            "has_frame": frame_bus.get_jpeg() is not None,
            "age_seconds": round(age, 2) if age is not None else None,
        }

    @app.get("/video/snapshot")
    async def snapshot():
        jpeg = frame_bus.get_jpeg() or _PLACEHOLDER_JPEG
        return Response(content=jpeg, media_type="image/jpeg")

    @app.get("/video/stream")
    async def video_stream():
        return StreamingResponse(
            _mjpeg_generator(),
            media_type="multipart/x-mixed-replace; boundary=frame",
            headers={"Cache-Control": "no-cache, no-store", "Pragma": "no-cache"},
        )

    # Serve the unified UI (live camera + chatbot sidebar).
    if UI_DIR.exists():
        @app.get("/", response_class=HTMLResponse)
        async def index():
            return (UI_DIR / "index.html").read_text(encoding="utf-8")

        app.mount("/ui", StaticFiles(directory=str(UI_DIR), html=True), name="ui")

    return app
