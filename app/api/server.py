"""FastAPI application factory with optional Svelte static file serving."""
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.events import event_manager
from app.api.routes import router

PROJECT_ROOT = Path(__file__).parent.parent.parent
FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Store the event loop reference on startup for thread-safe SSE queue access."""
    event_manager.set_loop(asyncio.get_running_loop())
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Travel Agent API", lifespan=lifespan)

    # CORS: allow dev server (Vite on :5173) and any local origin
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router)

    # In production, serve the built Svelte frontend
    if FRONTEND_DIST.exists():
        app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")

    return app


app = create_app()
