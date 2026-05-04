"""FastAPI route definitions for the travel agent pipeline API."""
import asyncio
import os
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Literal, Optional

from fastapi import APIRouter, Cookie, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from app.api.events import event_manager
from app.state import AVAILABLE_MODELS, OutputConfig
from app.db.connection import get_session
from app.db.repository import ArticleRepository, ArticleFilters
from app.db.models import Article, ArticleImage
import shutil


def _article_to_summary(a: Article) -> dict:
    return {
        "id": a.id,
        "title": a.title,
        "tour_date": a.tour_date.isoformat() if a.tour_date else None,
        "tour_duration_hours": a.tour_duration_hours,
        "tour_duration_source": a.tour_duration_source,
        "generation_timestamp": a.generation_timestamp.isoformat() if a.generation_timestamp else None,
        "total_distance_km": a.total_distance_km,
        "elevation_gain_m": a.elevation_gain_m,
        "elevation_loss_m": a.elevation_loss_m,
        "image_count": a.image_count,
        "model_used": a.model_used,
        "notes": a.notes,
    }


def _rewrite_html_content(html_content: str | None, article_id: int) -> str | None:
    """Passt HTML-Inhalt für das Frontend an:
    - Ersetzt relative ./images/ Pfade mit API-URLs
    - Erhöht max-width im eingebetteten CSS für breitere Darstellung
    """
    if not html_content:
        return html_content
    html_content = html_content.replace(
        "./images/",
        f"/api/articles/{article_id}/images/",
    )
    html_content = html_content.replace(
        "max-width: 780px",
        "max-width: 1400px",
    )
    return html_content


def _article_to_detail(a: Article) -> dict:
    return {
        **_article_to_summary(a),
        "markdown_content": a.markdown_content,
        "html_content": _rewrite_html_content(a.html_content, a.id),
        "markdown_path": a.markdown_path,
        "html_path": a.html_path,
        "gpx_file": a.gpx_file,
        "images": [
            {
                "image_path": img.image_path,
                "is_map": img.is_map,
                "is_elevation_profile": img.is_elevation_profile,
            }
            for img in a.images
        ],
    }


router = APIRouter(prefix="/api")

PROJECT_ROOT = Path(__file__).parent.parent.parent
UPLOADS_DIR = PROJECT_ROOT / "data" / "uploads"


def _safe_join(base_dir: Path, *parts: str) -> Path:
    """Join path parts and validate the result stays within base_dir."""
    resolved = (base_dir / Path(*parts)).resolve()
    if not str(resolved).startswith(str(base_dir.resolve())):
        raise HTTPException(status_code=400, detail="Invalid path: traverses outside upload directory")
    return resolved


def _get_session_dir(session_id: str) -> Path:
    """Return and create the upload directory for a session."""
    if not session_id or ".." in session_id or "/" in session_id:
        raise HTTPException(status_code=400, detail="Invalid session_id")
    d = _safe_join(UPLOADS_DIR, session_id)
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
    file_path = _safe_join(session_dir, file.filename)
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
    file_path = _safe_join(_get_session_dir(session_id), filename)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    file_path.unlink()
    return {"deleted": filename}


# ── Pipeline Run ───────────────────────────────────────

class RunPipelineRequest(BaseModel):
    model: str
    output_dir: str = "output"
    notes: str = ""
    txt_file: str = ""
    gpx_file: str = ""
    image_files: list[str] = []
    wildcard_max: int = Field(default=12, ge=1, le=50)
    article_length: Literal["short", "normal", "detailed"] = "normal"
    style_persona: Literal["mountain_veteran", "field_reporter"] = "mountain_veteran"


@router.post("/pipeline/run")
async def run_pipeline(body: RunPipelineRequest, session_id: str = Cookie(default="")):
    """Start a pipeline run and return a run_id for SSE streaming."""
    if not body.gpx_file:
        raise HTTPException(status_code=422, detail="gpx_file is required")

    run_id = str(uuid.uuid4())
    event_manager.create_run(run_id)

    # Pfad-Auflösung: relativ zum Session-Upload-Verzeichnis oder
    # absolute Pfade, die innerhalb des UPLOADS_DIR liegen (vom Upload-Endpoint).
    session_dir = _get_session_dir(session_id) if session_id else PROJECT_ROOT

    if os.path.isabs(body.gpx_file):
        # Nur absolute Pfade innerhalb UPLOADS_DIR oder PROJECT_ROOT erlauben
        resolved = Path(body.gpx_file).resolve()
        if not str(resolved).startswith(str(UPLOADS_DIR.resolve())) and \
           not str(resolved).startswith(str(PROJECT_ROOT.resolve())):
            raise HTTPException(
                status_code=400,
                detail="Absolute path outside allowed directories.",
            )
        gpx_path = str(resolved)
    else:
        gpx_path = str(_safe_join(session_dir, body.gpx_file))

    image_paths = []
    for img in body.image_files:
        if os.path.isabs(img):
            resolved = Path(img).resolve()
            if not str(resolved).startswith(str(UPLOADS_DIR.resolve())) and \
               not str(resolved).startswith(str(PROJECT_ROOT.resolve())):
                raise HTTPException(
                    status_code=400,
                    detail="Absolute path outside allowed directories.",
                )
            image_paths.append(str(resolved))
        else:
            image_paths.append(str(_safe_join(session_dir, img)))

    # Defer pipeline execution to background task
    asyncio.create_task(
        _run_pipeline_in_background(
            run_id=run_id,
            gpx_file=gpx_path,
            image_files=image_paths,
            txt_file=body.txt_file,
            model=body.model,
            output_dir=body.output_dir,
            notes=body.notes,
            body=body,
        )
    )

    return {"run_id": run_id}


async def _run_pipeline_in_background(
    run_id: str,
    gpx_file: str,
    image_files: list[str],
    txt_file: str,
    model: str,
    output_dir: str,
    notes: str,
    body: RunPipelineRequest,
):
    """Execute the LangGraph pipeline in a thread, emitting progress events."""
    from app.graph import build_graph
    from app.state import AppState, ImageData

    loop = asyncio.get_running_loop()

    def emit_fn(stage: str, status: str, message: str):
        event_manager.emit(run_id, stage, status, message)

    try:
        emit_fn("start", "running", "Pipeline wird gestartet…")

        # Text-Notizen: aus Textfeld oder aus hochgeladener .txt-Datei laden
        combined_notes = notes if notes else None
        if not combined_notes and txt_file:
            if os.path.isfile(txt_file):
                try:
                    with open(txt_file, encoding="utf-8") as f:
                        combined_notes = f.read()
                    emit_fn("load_tour_notes", "info", f"Notizen aus {os.path.basename(txt_file)} geladen")
                except Exception as e:
                    print(f"⚠️  Konnte txt_file nicht lesen: {e}")
            else:
                print(f"⚠️  txt_file nicht gefunden: {txt_file}")

        state = AppState(
            gpx_file=gpx_file,
            model=model,
            notes=combined_notes,
            output_config=OutputConfig(
                wildcard_max=body.wildcard_max,
                article_length=body.article_length,
                style_persona=body.style_persona,
            ),
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


# ── Articles ──────────────────────────────────────────

@router.get("/articles")
async def get_articles(
    tour_date_from: Optional[str] = None,
    tour_date_to: Optional[str] = None,
    duration_min: Optional[float] = None,
    duration_max: Optional[float] = None,
    generated_from: Optional[str] = None,
    generated_to: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
):
    """Liste aller persistierten Artikel mit optionalen Filtern."""
    filters = ArticleFilters(limit=limit, offset=offset)

    if tour_date_from:
        filters.tour_date_from = date.fromisoformat(tour_date_from)
    if tour_date_to:
        filters.tour_date_to = date.fromisoformat(tour_date_to)
    if duration_min is not None:
        filters.duration_min = duration_min
    if duration_max is not None:
        filters.duration_max = duration_max
    if generated_from:
        filters.generated_from = datetime.fromisoformat(generated_from)
    if generated_to:
        filters.generated_to = datetime.fromisoformat(generated_to)

    session = get_session()
    try:
        repo = ArticleRepository(session)
        articles, total = repo.list(filters)
        return {
            "articles": [_article_to_summary(a) for a in articles],
            "total": total,
        }
    finally:
        session.close()


@router.get("/articles/{article_id}")
async def get_article(article_id: int):
    """Einzelnen Artikel mit vollständigem Inhalt abrufen."""
    session = get_session()
    try:
        repo = ArticleRepository(session)
        article = repo.get_by_id(article_id)
        if article is None:
            raise HTTPException(status_code=404, detail="Article not found")
        return {"article": _article_to_detail(article)}
    finally:
        session.close()


@router.delete("/articles/{article_id}")
async def delete_article(article_id: int):
    """Artikel und zugehörige Dateien löschen."""
    session = get_session()
    try:
        repo = ArticleRepository(session)
        article = repo.get_by_id(article_id)
        if article is None:
            raise HTTPException(status_code=404, detail="Article not found")

        output_dir = os.path.dirname(article.markdown_path) if article.markdown_path else None
        repo.delete(article_id)

        if output_dir and os.path.exists(output_dir):
            try:
                shutil.rmtree(output_dir)
            except OSError as e:
                print(f"⚠️ Konnte Output-Verzeichnis nicht löschen: {e}")

        return {"deleted": article_id}
    finally:
        session.close()


class DeleteBatchRequest(BaseModel):
    ids: list[int]


@router.post("/articles/delete-batch")
async def delete_articles_batch(body: DeleteBatchRequest):
    """Mehrere Artikel und deren Dateien auf einmal löschen."""
    if not body.ids:
        raise HTTPException(status_code=400, detail="No article IDs provided")

    session = get_session()
    try:
        repo = ArticleRepository(session)

        # Output-Verzeichnisse vor dem Löschen merken
        output_dirs: list[str] = []
        for article_id in body.ids:
            article = repo.get_by_id(article_id)
            if article and article.markdown_path:
                d = os.path.dirname(article.markdown_path)
                if d not in output_dirs:
                    output_dirs.append(d)

        deleted = repo.delete_batch(body.ids)

        # Dateien löschen
        for d in output_dirs:
            if os.path.exists(d):
                try:
                    shutil.rmtree(d)
                except OSError as e:
                    print(f"⚠️ Konnte Output-Verzeichnis nicht löschen: {e}")

        return {"deleted": deleted}
    finally:
        session.close()


# ── Image Serving ─────────────────────────────────────

@router.get("/articles/{article_id}/images/{filename}")
async def get_article_image(article_id: int, filename: str):
    """Bilddatei eines Artikels ausliefern."""
    session = get_session()
    try:
        repo = ArticleRepository(session)
        article = repo.get_by_id(article_id)
        if article is None:
            raise HTTPException(status_code=404, detail="Article not found")

        # 1) Exakte Übereinstimmung über den Dateinamen in ArticleImage
        for img in article.images:
            if os.path.basename(img.image_path) == filename:
                if os.path.isfile(img.image_path):
                    return FileResponse(img.image_path)
                break

        # 2) Fallback: images/-Verzeichnis neben html_path/markdown_path
        output_dir = None
        if article.html_path:
            output_dir = os.path.dirname(article.html_path)
        elif article.markdown_path:
            output_dir = os.path.dirname(article.markdown_path)

        if output_dir:
            image_path = os.path.join(output_dir, "images", filename)
            if os.path.isfile(image_path):
                return FileResponse(image_path)

        raise HTTPException(status_code=404, detail="Image not found")
    finally:
        session.close()


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
