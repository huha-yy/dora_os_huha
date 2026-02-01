import os
from pathlib import Path
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from routes import init_ws_routes, init_webtool_routes
from service_context import default_service_context
from starlette.staticfiles import StaticFiles as StarletteStaticFiles

ROOT_DIR = Path(__file__).parent


# Create a custom StaticFiles class that adds CORS headers
class CORSStaticFiles(StarletteStaticFiles):
    """
    Static files handler that adds CORS headers to all responses.
    Needed because Starlette StaticFiles might bypass standard middleware.
    """

    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)

        # Add CORS headers to all responses
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "*"

        if path.endswith(".js"):
            response.headers["Content-Type"] = "application/javascript"

        return response


class WebSocketServer:
    def __init__(self, config: dict):
        self.app = FastAPI(title="Demo Server")
        self.config = config
        # Add global CORS middleware
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        ws_router, self.ws_handler = init_ws_routes()
        self.app.include_router(ws_router)
        self.app.include_router(init_webtool_routes(default_service_context))
        cache_dir = str(ROOT_DIR / "cache")
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)
        self.app.mount(
            "/cache",
            CORSStaticFiles(directory=cache_dir),
            name="cache",
        )
        # Mount web tool directory separately from frontend
        self.app.mount(
            "/web-tool",
            CORSStaticFiles(directory=str(ROOT_DIR / "web_tool"), html=True),
            name="web_tool",
        )

        # Mount main frontend last (as catch-all)
        self.app.mount(
            "/",
            CORSStaticFiles(directory=str(ROOT_DIR / "frontend"), html=True),
            name="frontend",
        )

    def run(self):
        print("Running chatbot...")

    def clean_cache(self):
        print("Cleaning cache...")
