# orchestrator/http/app.py
from fastapi import FastAPI
from ..routers import events, actions


def create_app() -> FastAPI:
    app = FastAPI(title="Dorabot Orchestrator")

    app.include_router(events.router, prefix="/events", tags=["events"])
    app.include_router(actions.router, prefix="/actions", tags=["actions"])

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app
