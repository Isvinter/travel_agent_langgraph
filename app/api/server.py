"""FastAPI application factory with optional Svelte static file serving."""
import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.events import event_manager
from app.api.routes import router
from app.logging_setup import setup_logging

setup_logging()

PROJECT_ROOT = Path(__file__).parent.parent.parent
FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Store the event loop reference on startup for thread-safe SSE queue access."""
    event_manager.set_loop(asyncio.get_running_loop())
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Travel Agent API", lifespan=lifespan)

    # CORS: allow dev server (Vite on :5173) and same-origin
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://localhost:8000",
            "http://127.0.0.1:5173",
            "http://127.0.0.1:8000",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # API-Key-(optional) Authentifizierung für Produktions-Deployments
    api_key = os.getenv("API_KEY", "").strip()

    @app.middleware("http")
    async def api_key_middleware(request: Request, call_next):
        if api_key and request.url.path.startswith("/api"):
            provided = request.headers.get("X-API-Key", "")
            if provided != api_key:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Ungültiger API-Key"},
                )
        return await call_next(request)

    # Security-Headers Middleware
    @app.middleware("http")
    async def security_headers_middleware(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-XSS-Protection"] = "0"
        response.headers["Permissions-Policy"] = (
            "accelerometer=(), camera=(), geolocation=(), "
            "gyroscope=(), magnetometer=(), microphone=(), "
            "payment=(), usb=()"
        )
        if request.url.scheme == "https" or request.headers.get("X-Forwarded-Proto") == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

    app.include_router(router)

    # In production, serve the built Svelte frontend
    if FRONTEND_DIST.exists():
        app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")

    return app


app = create_app()


def main():
    """Entry point for `travel-agent-api` console script."""
    import uvicorn
    uvicorn.run("app.api.server:app", host="0.0.0.0", port=8000, reload=False)
