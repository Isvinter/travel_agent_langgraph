"""FastAPI route definitions for the travel agent pipeline API."""
import os
import shutil
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Cookie, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from app.api.events import event_manager
from app.state import AVAILABLE_MODELS

router = APIRouter(prefix="/api")

PROJECT_ROOT = Path(__file__).parent.parent.parent
UPLOADS_DIR = PROJECT_ROOT / "data" / "uploads"


def _get_session_dir(session_id: str) -> Path:
    """Return and create the upload directory for a session."""
    d = UPLOADS_DIR / session_id
    d.mkdir(parents=True, exist_ok=True)
    return d


# ── Models ────────────────────────────────────────────

@router.get("/models")
async def get_models():
    """List available Ollama models."""
    return {"models": AVAILABLE_MODELS}


# ── File Management ───────────────────────────────────

@router.post("/files/upload")
async def upload_file(
    file: UploadFile = File(...),
    session_id: str = Cookie(default=""),
):
    """Upload a file to the session-specific staging directory."""
    if not session_id:
        raise HTTPException(status_code=400, detail="No session_id cookie")
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    session_dir = _get_session_dir(session_id)
    file_path = session_dir / file.filename
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)

    return {"filename": file.filename, "path": str(file_path.absolute())}


@router.delete("/files/{filename}")
async def delete_file(
    filename: str,
    session_id: str = Cookie(default=""),
):
    """Remove a previously uploaded file from the session directory."""
    if not session_id:
        raise HTTPException(status_code=400, detail="No session_id cookie")
    file_path = _get_session_dir(session_id) / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    file_path.unlink()
    return {"deleted": filename}


# ── Pipeline Run ───────────────────────────────────────

class RunPipelineRequest(BaseModel):
    model: str
    output_dir: str = "output"
    notes: str = ""
    gpx_file: str = ""
    image_files: list[str] = []


@router.post("/pipeline/run")
async def run_pipeline(body: RunPipelineRequest, session_id: str = Cookie(default="")):
    """Start a pipeline run and return a run_id for SSE streaming."""
    if not body.gpx_file:
        raise HTTPException(status_code=422, detail="gpx_file is required")

    valid_models = AVAILABLE_MODELS + [body.model]  # accept custom model name
    # (model validation is lenient — Ollama will return an error if unknown)

    run_id = str(uuid.uuid4())
    event_manager.create_run(run_id)

    # Resolve paths relative to session upload dir if not absolute
    session_dir = _get_session_dir(session_id) if session_id else PROJECT_ROOT

    gpx_path = body.gpx_file
    if not os.path.isabs(gpx_path):
        gpx_path = str(session_dir / gpx_path)

    image_paths = []
    for img in body.image_files:
        if os.path.isabs(img):
            image_paths.append(img)
        else:
            image_paths.append(str(session_dir / img))

    # Defer pipeline execution to background task
    import asyncio
    asyncio.create_task(
        _run_pipeline_in_background(
            run_id=run_id,
            gpx_file=gpx_path,
            image_files=image_paths,
            model=body.model,
            output_dir=body.output_dir,
            notes=body.notes,
        )
    )

    return {"run_id": run_id}


async def _run_pipeline_in_background(
    run_id: str,
    gpx_file: str,
    image_files: list[str],
    model: str,
    output_dir: str,
    notes: str,
):
    """Execute the LangGraph pipeline in a thread, emitting progress events."""
    from app.graph import build_graph
    from app.state import AppState, ImageData

    loop = asyncio.get_running_loop()

    def emit_fn(stage: str, status: str, message: str):
        event_manager.emit(run_id, stage, status, message)

    try:
        emit_fn("start", "running", "Pipeline wird gestartet…")

        # Build state from the provided inputs
        state = AppState(
            gpx_file=gpx_file,
            model=model,
            notes=notes if notes else None,
        )

        # If images provided, pre-populate ImageData list
        if image_files:
            state.images = [
                ImageData(path=p) for p in image_files if os.path.exists(p)
            ]

        # Run the graph in a thread executor (graph.invoke is sync)
        emit_fn("pipeline", "running", "LangGraph-Pipeline wird ausgeführt…")
        graph = build_graph(event_emitter=emit_fn)
        result = await loop.run_in_executor(None, graph.invoke, state)

        # Extract output paths
        blog_post = result.blog_post if hasattr(result, "blog_post") else None
        output_paths = {}
        if blog_post and isinstance(blog_post, dict):
            output_paths = blog_post.get("file_paths", {})

        event_manager.store_result(run_id, {
            "markdown": blog_post.get("markdown", "") if blog_post else "",
            "html": blog_post.get("html", "") if blog_post else "",
            "file_paths": output_paths,
            "success": True,
        })

        output_path = output_paths.get("markdown", output_dir)
        event_manager.complete_run(run_id, "success", output_path)

    except Exception as e:
        emit_fn("error", "error", str(e))
        event_manager.store_result(run_id, {
            "success": False,
            "error": str(e),
        })
        event_manager.complete_run(run_id, "failed", "")


# ── SSE Streaming ──────────────────────────────────────

@router.get("/pipeline/stream/{run_id}")
async def stream_pipeline(run_id: str):
    """SSE endpoint: live progress events from a pipeline run."""
    return EventSourceResponse(event_manager.stream_events(run_id))


@router.get("/pipeline/result/{run_id}")
async def get_result(run_id: str):
    """Retrieve the final result of a completed pipeline run."""
    result = event_manager.get_result(run_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Run not found or not yet completed")
    return result
