"""FastAPI route definitions for the travel agent pipeline API."""
import asyncio
import logging
import os
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Literal, Optional

from fastapi import APIRouter, Cookie, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from app.api.events import event_manager
from app.state import AVAILABLE_MODELS, OutputConfig
from app.utils.html_sanitizer import sanitize_html
from app.db.connection import get_session
from app.db.repository import ArticleRepository, ArticleFilters
from app.db.models import Article
from app.db.models import Calendar
from app.db.models import Photobook
from app.db.photobook_repository import PhotobookRepository, PhotobookFilters
from app.db.calendar_repository import CalendarRepository, CalendarFilters
import re
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
    - Entfernt gefährliche Elemente (Scripts, Event-Handler, javascript:-URIs)
    - Entfernt <style>-Tags (würden global im SPA leaken)
    - Entfernt strukturelle HTML-Tags (<html>, <head>, <body>)
    - Extrahiert nur den Body-Inhalt
    - Ersetzt relative ./images/ Pfade mit API-URLs
    """
    if not html_content:
        return html_content

    # Sicherheitssanitisierung (defense-in-depth)
    html_content = sanitize_html(html_content, keep_style=False)

    # Body-Inhalt extrahieren
    body_match = re.search(
        r"<body[^>]*>(.*?)</body\s*>",
        html_content,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if body_match:
        html_content = body_match.group(1).strip()
    else:
        # Fallback: strukturelle Tags einzeln entfernen
        html_content = re.sub(r"<!DOCTYPE[^>]*>", "", html_content, flags=re.IGNORECASE)
        html_content = re.sub(r"<html[^>]*>", "", html_content, flags=re.IGNORECASE)
        html_content = re.sub(r"</html\s*>", "", html_content, flags=re.IGNORECASE)
        html_content = re.sub(
            r"<head[^>]*>.*?</head\s*>",
            "",
            html_content,
            flags=re.DOTALL | re.IGNORECASE,
        )

    # Bildpfade umschreiben
    html_content = html_content.replace(
        "./images/",
        f"/api/articles/{article_id}/images/",
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


def _photobook_to_summary(p: Photobook) -> dict:
    return {
        "id": p.id,
        "title": p.title,
        "tour_date": p.tour_date.isoformat() if p.tour_date else None,
        "tour_duration_hours": p.tour_duration_hours,
        "tour_duration_source": p.tour_duration_source,
        "generation_timestamp": p.generation_timestamp.isoformat() if p.generation_timestamp else None,
        "total_distance_km": p.total_distance_km,
        "elevation_gain_m": p.elevation_gain_m,
        "elevation_loss_m": p.elevation_loss_m,
        "image_count": p.image_count,
        "model_used": p.model_used,
        "notes": p.notes,
        "photobook_size": p.photobook_size,
        "page_count": p.page_count,
    }


def _photobook_to_detail(p: Photobook) -> dict:
    return {
        **_photobook_to_summary(p),
        "html_content": _rewrite_photobook_html(p.html_content, p.id),
        "html_path": p.html_path,
        "pdf_path": p.pdf_path,
        "gpx_file": p.gpx_file,
        "images": [
            {
                "image_path": img.image_path,
                "is_map": img.is_map,
                "is_elevation_profile": img.is_elevation_profile,
            }
            for img in p.images
        ],
    }


def _rewrite_photobook_html(html_content: str | None, photobook_id: int) -> str | None:
    """Bereitet Fotobuch-HTML für die Anzeige im iframe vor.

    - Sicherheitssanitisierung (scripts, event handler; style-tags bleiben erhalten)
    - Vollständiges HTML-Dokument wird beibehalten (für iframe srcdoc)
    - file:/// Bildpfade werden auf API-URLs umgeschrieben
    """
    if not html_content:
        return html_content

    # Zuerst file:/// URLs umschreiben, BEVOR der Sanitizer sie entfernt
    html_content = re.sub(
        r'file:///[^"]*?/images/([^"]+)',
        f'/api/photobooks/{photobook_id}/images/\\1',
        html_content,
    )

    # Dann Sicherheitssanitisierung (relative URLs sind unkritisch)
    html_content = sanitize_html(html_content, keep_style=True)

    return html_content


def _calendar_to_summary(c: "Calendar") -> dict:
    return {
        "id": c.id,
        "preset": c.preset,
        "year": c.year,
        "custom_instructions": c.custom_instructions,
        "status": c.status,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


def _calendar_to_detail(c: "Calendar") -> dict:
    return {
        **_calendar_to_summary(c),
        "html_content": _rewrite_calendar_html(c.html_content, c.id),
        "html_path": c.html_path,
        "pdf_path": c.pdf_path,
        "images": [
            {"image_path": img.image_path, "month_index": img.month_index, "slot_index": img.slot_index}
            for img in c.images
        ],
    }


def _rewrite_calendar_html(html_content: str | None, calendar_id: int) -> str | None:
    if not html_content:
        return html_content
    html_content = re.sub(
        r'file:///[^"]*?/images/([^"]+)',
        f'/api/calendars/{calendar_id}/images/\\1',
        html_content,
    )
    html_content = sanitize_html(html_content, keep_style=True)
    return html_content


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

ALLOWED_EXTENSIONS = {
    ".gpx", ".txt", ".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic", ".heif",
    ".csv", ".json", ".md",
}
MAX_UPLOAD_SIZE = 100 * 1024 * 1024  # 100 MB


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

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail=f"Dateityp {ext} nicht erlaubt. Erlaubt: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"Datei zu gross ({len(content) / (1024*1024):.1f} MB). Maximum: {MAX_UPLOAD_SIZE / (1024*1024):.0f} MB",
        )

    session_dir = _get_session_dir(session_id)
    file_path = _safe_join(session_dir, file.filename)
    with open(file_path, "wb") as f:
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
    pdf_export: bool = False
    review_enabled: bool = False
    mode: Literal["blog", "photobook"] = "blog"
    photobook_size: Literal["short", "normal", "detailed"] | None = None
    photobook_preset: Literal[
        "nature_outdoor", "culture_architecture", "people", "nature_collage", "mixed"
    ] = "mixed"


class RunCalendarRequest(BaseModel):
    preset: Literal["mixed", "nature_landscape", "people", "culture"] = "mixed"
    year: int = Field(default=2026, ge=2000, le=2100)
    custom_instructions: Optional[str] = None
    model: str = "gemma4:26b-ctx128k"
    image_files: list[str] = []


class RevisionItem(BaseModel):
    element_type: Literal["paragraph", "image"]
    element_index: int
    original_content: str
    instruction: str = ""


class RevisionRequest(BaseModel):
    changes: list[RevisionItem]


@router.post("/pipeline/run")
async def run_pipeline(body: RunPipelineRequest, session_id: str = Cookie(default="")):
    """Start a pipeline run and return a run_id for SSE streaming."""
    if body.mode == "blog" and not body.gpx_file:
        raise HTTPException(status_code=422, detail="gpx_file is required for blog mode")
    if body.mode != "blog" and not body.gpx_file and not body.image_files:
        raise HTTPException(status_code=422, detail="Mindestens Bilder oder GPX erforderlich")

    if body.model not in AVAILABLE_MODELS:
        raise HTTPException(status_code=422, detail=f"Unbekanntes Modell: {body.model}")

    run_id = str(uuid.uuid4())
    event_manager.create_run(run_id)

    # Pfad-Auflösung: relativ zum Session-Upload-Verzeichnis oder
    # absolute Pfade, die innerhalb des UPLOADS_DIR liegen (vom Upload-Endpoint).
    session_dir = _get_session_dir(session_id) if session_id else PROJECT_ROOT

    gpx_path = ""
    if body.gpx_file:
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
    task = asyncio.create_task(
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
    task.add_done_callback(
        lambda t: t.exception() and logging.getLogger("api").error(
            "Pipeline task %s failed: %s", run_id, t.exception()
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
                    logging.getLogger("api").warning("Konnte txt_file nicht lesen: %s", e)
            else:
                logging.getLogger("api").warning("txt_file nicht gefunden: %s", txt_file)

        # Fotobuch-Konfiguration aus Grössenstufe ableiten
        from app.state import apply_photobook_size
        photobook_config = apply_photobook_size(body.photobook_size or "normal")

        state = AppState(
            gpx_file=gpx_file,
            model=model or AppState.model_fields["model"].default,
            output_dir=output_dir or "output",
            notes=combined_notes,
            output_config=OutputConfig(
                mode=body.mode,
                wildcard_max=body.wildcard_max,
                article_length=body.article_length,
                style_persona=body.style_persona,
                pdf_export=body.pdf_export,
                review_enabled=body.review_enabled,
                photobook=photobook_config,
                photobook_preset=body.photobook_preset,
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

        # "start" und "pipeline" als abgeschlossen markieren
        emit_fn("start", "done", "Pipeline gestartet.")
        emit_fn("pipeline", "done", "LangGraph-Pipeline abgeschlossen.")

        # Extract output paths
        blog_post = result.blog_post if hasattr(result, "blog_post") else None
        photobook_pdf_path = result.photobook_pdf_path if hasattr(result, "photobook_pdf_path") else None

        output_paths = {}
        if blog_post:
            output_paths = blog_post.file_paths

        event_manager.store_result(run_id, {
            "markdown": blog_post.markdown if blog_post else "",
            "html": blog_post.html if blog_post else "",
            "file_paths": output_paths,
            "success": True,
            "photobook_pdf_path": photobook_pdf_path,
        })

        output_path = output_paths.get("markdown", output_dir)

        article_id = None
        photobook_id = None
        draft_id = None
        pdf_available = False
        if isinstance(result, dict):
            aid = result.get("article_id")
            photobook_id = result.get("photobook_id")
        else:
            aid = getattr(result, "article_id", None)
            photobook_id = getattr(result, "photobook_id", None)
        if aid is not None:
            if body.review_enabled:
                draft_id = aid
            else:
                article_id = aid
        if blog_post and blog_post.pdf_bytes is not None:
            pdf_available = True

        # Fotobuch: PDF verfügbar wenn Pfad gesetzt ist
        if photobook_pdf_path:
            pdf_available = True

        event_manager.complete_run(
            run_id, "success", output_path,
            article_id=article_id,
            photobook_id=photobook_id,
            draft_id=draft_id,
            pdf_available=pdf_available,
        )

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
    status: Optional[str] = None,
    generated_from: Optional[str] = None,
    generated_to: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
):
    """Liste aller persistierten Artikel mit optionalen Filtern."""
    filters = ArticleFilters(limit=limit, offset=offset, status=status)

    if tour_date_from:
        try:
            filters.tour_date_from = date.fromisoformat(tour_date_from)
        except ValueError:
            raise HTTPException(status_code=422, detail=f"Ungültiges Datum: {tour_date_from}")
    if tour_date_to:
        try:
            filters.tour_date_to = date.fromisoformat(tour_date_to)
        except ValueError:
            raise HTTPException(status_code=422, detail=f"Ungültiges Datum: {tour_date_to}")
    if duration_min is not None:
        filters.duration_min = duration_min
    if duration_max is not None:
        filters.duration_max = duration_max
    if generated_from:
        try:
            filters.generated_from = datetime.fromisoformat(generated_from)
        except ValueError:
            raise HTTPException(status_code=422, detail=f"Ungültiger Zeitstempel: {generated_from}")
    if generated_to:
        try:
            filters.generated_to = datetime.fromisoformat(generated_to)
        except ValueError:
            raise HTTPException(status_code=422, detail=f"Ungültiger Zeitstempel: {generated_to}")

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
                logging.getLogger("api").warning("Konnte Output-Verzeichnis nicht löschen: %s", e)

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
                    logging.getLogger("api").warning("Konnte Output-Verzeichnis nicht löschen: %s", e)

        return {"deleted": deleted}
    finally:
        session.close()


@router.post("/articles/{article_id}/revise")
async def revise_article(article_id: int, body: RevisionRequest):
    """Überarbeitet einen Draft-Artikel via LLM und speichert die neue Version."""
    from app.services.revise_blogpost import revise_blog_post
    from app.services.design_blogpost import design_blogpost_service

    session = get_session()
    try:
        repo = ArticleRepository(session)
        article = repo.get_by_id(article_id)
        if article is None:
            raise HTTPException(status_code=404, detail="Article not found")
        if article.status != "draft":
            raise HTTPException(status_code=400, detail="Article is not a draft")

        full_context = {
            "notes": article.notes,
            "gpx_stats": {
                "total_distance_km": article.total_distance_km,
                "elevation_gain_m": article.elevation_gain_m,
                "elevation_loss_m": article.elevation_loss_m,
            },
        }

        output_config = OutputConfig(
            style_persona="mountain_veteran",
            article_length="normal",
        )

        changes_dicts = [c.model_dump() for c in body.changes]

        result = revise_blog_post(
            current_markdown=article.markdown_content or "",
            changes=changes_dicts,
            full_context=full_context,
            available_images=[],
            output_config=output_config,
            model=article.model_used or "gemma4:26b-ctx128k",
        )

        if not result["success"]:
            raise HTTPException(status_code=500, detail="LLM revision failed")

        try:
            import markdown
            html_body = markdown.markdown(result["markdown"], extensions=["fenced_code", "tables", "sane_lists"])
            html = design_blogpost_service(html_body)
        except Exception:
            html = result["markdown"]

        new_round = (article.revision_round or 0) + 1
        repo.update(article_id, {
            "markdown_content": result["markdown"],
            "html_content": html,
            "revision_round": new_round,
        })

        return {
            "markdown": result["markdown"],
            "html": _rewrite_html_content(html, article_id),
            "revision_round": new_round,
            "paragraph_count_changed": result.get("paragraph_count_changed", False),
        }
    finally:
        session.close()


@router.post("/articles/{article_id}/publish")
async def publish_article(article_id: int):
    """Veröffentlicht einen Draft-Artikel (status: draft -> published)."""
    session = get_session()
    try:
        repo = ArticleRepository(session)
        article = repo.get_by_id(article_id)
        if article is None:
            raise HTTPException(status_code=404, detail="Article not found")
        if article.status != "draft":
            raise HTTPException(status_code=400, detail="Article is not a draft")

        repo.update(article_id, {"status": "published"})
        return {"status": "published", "article_id": article_id}
    finally:
        session.close()


# ── PDF Export ─────────────────────────────────────────

@router.get("/articles/{article_id}/pdf")
async def export_article_pdf(article_id: int):
    """Generiert PDF für einen Artikel und liefert es als Download aus."""
    from app.services.generate_pdf import generate_pdf

    session = get_session()
    try:
        repo = ArticleRepository(session)
        article = repo.get_by_id(article_id)
        if article is None:
            raise HTTPException(status_code=404, detail="Artikel nicht gefunden")
        if not article.html_content:
            raise HTTPException(status_code=400, detail="Artikel hat keinen HTML-Inhalt")

        # Output-Verzeichnis aus html_path ableiten
        output_dir = str(Path(article.html_path).parent) if article.html_path else ""

        try:
            pdf_bytes = generate_pdf(article.html_content, output_dir)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"PDF-Generierung fehlgeschlagen: {e}")

        # Dateiname: Titel ohne Sonderzeichen, Fallback "artikel"
        safe_title = re.sub(r"[^\w\- ]", "", article.title or "artikel").strip()[:100]
        filename = f"{safe_title}.pdf"

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Cache-Control": "no-cache",
            },
        )
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
            image_path = _safe_join(Path(output_dir), "images", filename)
            if image_path.is_file():
                return FileResponse(image_path)

        raise HTTPException(status_code=404, detail="Image not found")
    finally:
        session.close()


@router.get("/photobooks")
async def get_photobooks(
    tour_date_from: Optional[str] = None,
    tour_date_to: Optional[str] = None,
    duration_min: Optional[float] = None,
    duration_max: Optional[float] = None,
    generated_from: Optional[str] = None,
    generated_to: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
):
    """Liste aller persistierten Fotobücher mit optionalen Filtern."""
    filters = PhotobookFilters(limit=limit, offset=offset)

    if tour_date_from:
        try:
            filters.tour_date_from = date.fromisoformat(tour_date_from)
        except ValueError:
            raise HTTPException(status_code=422, detail=f"Ungültiges Datum: {tour_date_from}")
    if tour_date_to:
        try:
            filters.tour_date_to = date.fromisoformat(tour_date_to)
        except ValueError:
            raise HTTPException(status_code=422, detail=f"Ungültiges Datum: {tour_date_to}")
    if duration_min is not None:
        filters.duration_min = duration_min
    if duration_max is not None:
        filters.duration_max = duration_max
    if generated_from:
        try:
            filters.generated_from = datetime.fromisoformat(generated_from)
        except ValueError:
            raise HTTPException(status_code=422, detail=f"Ungültiger Zeitstempel: {generated_from}")
    if generated_to:
        try:
            filters.generated_to = datetime.fromisoformat(generated_to)
        except ValueError:
            raise HTTPException(status_code=422, detail=f"Ungültiger Zeitstempel: {generated_to}")

    session = get_session()
    try:
        repo = PhotobookRepository(session)
        records, total = repo.list(filters)
        return {
            "photobooks": [_photobook_to_summary(p) for p in records],
            "total": total,
        }
    finally:
        session.close()


@router.get("/photobooks/{photobook_id}")
async def get_photobook(photobook_id: int):
    """Einzelnes Fotobuch mit vollständigem Inhalt abrufen."""
    session = get_session()
    try:
        repo = PhotobookRepository(session)
        record = repo.get_by_id(photobook_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Photobook not found")
        return {"photobook": _photobook_to_detail(record)}
    finally:
        session.close()


@router.delete("/photobooks/{photobook_id}")
async def delete_photobook(photobook_id: int):
    """Fotobuch und zugehörige Dateien löschen."""
    session = get_session()
    try:
        repo = PhotobookRepository(session)
        record = repo.get_by_id(photobook_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Photobook not found")

        output_dir = os.path.dirname(record.html_path) if record.html_path else None
        repo.delete(photobook_id)

        if output_dir and os.path.exists(output_dir):
            try:
                shutil.rmtree(output_dir)
            except OSError as e:
                logging.getLogger("api").warning("Konnte Output-Verzeichnis nicht löschen: %s", e)

        return {"deleted": photobook_id}
    finally:
        session.close()


@router.post("/photobooks/delete-batch")
async def delete_photobooks_batch(body: DeleteBatchRequest):
    """Mehrere Fotobücher und deren Dateien auf einmal löschen."""
    if not body.ids:
        raise HTTPException(status_code=400, detail="No photobook IDs provided")

    session = get_session()
    try:
        repo = PhotobookRepository(session)

        output_dirs: list[str] = []
        for pb_id in body.ids:
            record = repo.get_by_id(pb_id)
            if record and record.html_path:
                d = os.path.dirname(record.html_path)
                if d not in output_dirs:
                    output_dirs.append(d)

        deleted = repo.delete_batch(body.ids)

        for d in output_dirs:
            if os.path.exists(d):
                try:
                    shutil.rmtree(d)
                except OSError as e:
                    logging.getLogger("api").warning("Konnte Output-Verzeichnis nicht löschen: %s", e)

        return {"deleted": deleted}
    finally:
        session.close()


@router.get("/photobooks/{photobook_id}/pdf")
async def get_photobook_pdf(photobook_id: int):
    """PDF eines persistierten Fotobuchs ausliefern."""
    session = get_session()
    try:
        repo = PhotobookRepository(session)
        record = repo.get_by_id(photobook_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Fotobuch nicht gefunden")
        if not record.pdf_path:
            raise HTTPException(status_code=400, detail="Fotobuch hat kein PDF")

        path = Path(record.pdf_path)
        if not path.exists():
            raise HTTPException(status_code=404, detail="PDF-Datei nicht gefunden")

        return FileResponse(
            path,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{path.name}"',
                "Cache-Control": "no-cache",
            },
        )
    finally:
        session.close()


@router.get("/photobooks/{photobook_id}/images/{filename}")
async def get_photobook_image(photobook_id: int, filename: str):
    """Bilddatei eines Fotobuchs ausliefern."""
    session = get_session()
    try:
        repo = PhotobookRepository(session)
        record = repo.get_by_id(photobook_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Photobook not found")

        for img in record.images:
            if os.path.basename(img.image_path) == filename:
                if os.path.isfile(img.image_path):
                    return FileResponse(img.image_path)
                break

        output_dir = None
        if record.html_path:
            output_dir = os.path.dirname(record.html_path)

        if output_dir:
            image_path = _safe_join(Path(output_dir), "images", filename)
            if image_path.is_file():
                return FileResponse(image_path)

        raise HTTPException(status_code=404, detail="Image not found")
    finally:
        session.close()


# ── Calendar ───────────────────────────────────────────

@router.post("/calendar/generate")
async def generate_calendar(body: RunCalendarRequest, session_id: str = Cookie(default="")):
    """Startet die Kalender-Generierung und gibt eine run_id für SSE-Streaming zurück."""
    if body.model not in AVAILABLE_MODELS:
        raise HTTPException(status_code=422, detail=f"Unbekanntes Modell: {body.model}")
    if not body.image_files:
        raise HTTPException(status_code=422, detail="Mindestens ein Bild erforderlich")

    run_id = str(uuid.uuid4())
    event_manager.create_run(run_id)

    session_dir = _get_session_dir(session_id) if session_id else PROJECT_ROOT

    image_paths = []
    for img in body.image_files:
        if os.path.isabs(img):
            resolved = Path(img).resolve()
            if not str(resolved).startswith(str(UPLOADS_DIR.resolve())) and \
               not str(resolved).startswith(str(PROJECT_ROOT.resolve())):
                raise HTTPException(status_code=400, detail="Absolute path outside allowed directories.")
            image_paths.append(str(resolved))
        else:
            image_paths.append(str(_safe_join(session_dir, img)))

    task = asyncio.create_task(
        _run_calendar_in_background(
            run_id=run_id,
            image_files=image_paths,
            body=body,
        )
    )
    return {"run_id": run_id}


async def _run_calendar_in_background(
    run_id: str,
    image_files: list[str],
    body: RunCalendarRequest,
):
    """Führt die Kalender-Pipeline als Hintergrund-Task aus."""
    from app.calendar.pipeline import run_calendar_pipeline
    from app.calendar.models import CalendarConfig
    from app.state import ImageData
    from app.shared.pdf_generator import generate_pdf
    from app.db.connection import get_session
    from app.db.calendar_repository import CalendarRepository

    loop = asyncio.get_running_loop()

    def emit_fn(stage: str, status: str, message: str):
        event_manager.emit(run_id, stage, status, message)

    try:
        emit_fn("start", "running", "Kalender-Generierung gestartet…")

        # Output-Verzeichnis und Bilder-Komprimierung VOR dem Rendering (wie Photobuch)
        output_base = os.path.join("output", f"calendar_{run_id[:8]}")
        images_dir = os.path.join(output_base, "images")
        os.makedirs(images_dir, exist_ok=True)

        # Bilder komprimieren und ins Output-Verzeichnis kopieren (max 1200px, max 1 MB)
        from app.utils.image_utils import compress_image_to_jpeg
        compressed_files = []
        for idx, p in enumerate(image_files):
            if os.path.isfile(p):
                basename = os.path.splitext(os.path.basename(p))[0]
                out_name = f"{idx:02d}_{basename}.jpg"
                out_path = os.path.join(images_dir, out_name)
                result = compress_image_to_jpeg(p, out_path)
                if result:
                    compressed_files.append(result)
                else:
                    # Fallback: Original kopieren wenn Kompression fehlschlägt
                    import shutil as _shutil
                    dest = os.path.join(images_dir, os.path.basename(p))
                    _shutil.copy2(p, dest)
                    compressed_files.append(dest)

        emit_fn("calendar_selecting_images", "running", "Wähle beste Bilder aus…")
        images = [ImageData(path=p) for p in compressed_files]

        config = CalendarConfig(
            preset=body.preset,
            year=body.year,
            custom_instructions=body.custom_instructions,
            model=body.model,
        )

        result = await loop.run_in_executor(
            None, lambda: run_calendar_pipeline(images=images, config=config)
        )
        emit_fn("calendar_selecting_images", "done", f"{result.selected_image_count} Bilder ausgewählt")
        emit_fn("calendar_assigning_months", "done", "Fotos auf Monate verteilt")

        # HTML speichern (Bilder sind bereits in ./images/, file:/// URLs zeigen dorthin)
        html_path = os.path.join(output_base, f"{run_id[:8]}_calendar.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(result.html_content)
        emit_fn("calendar_rendering", "done", "HTML gerendert")

        # PDF generieren (gleicher Flow wie Photobuch)
        emit_fn("calendar_generating_pdf", "running", "PDF wird generiert…")
        pdf_path = None
        try:
            pdf_bytes = await loop.run_in_executor(
                None, lambda: generate_pdf(result.html_content, paper_size="landscape", source_path=html_path)
            )
            pdf_path = os.path.join(output_base, f"{run_id[:8]}_calendar.pdf")
            with open(pdf_path, "wb") as f:
                f.write(pdf_bytes)
            emit_fn("calendar_generating_pdf", "done", "PDF generiert")
        except Exception as e:
            logger = logging.getLogger("api")
            logger.warning("PDF-Generierung fehlgeschlagen: %s", e)
            emit_fn("calendar_generating_pdf", "error", f"PDF fehlgeschlagen: {e}")

        # Persistieren
        session = get_session()
        calendar_id = None
        try:
            repo = CalendarRepository(session)
            image_entries = []
            selected_paths = getattr(result, "selected_image_paths", []) or compressed_files
            for page in result.pages:
                month_idx = page.month
                for slot_idx, slot in enumerate(page.slots):
                    if 0 <= slot.image_index < len(selected_paths):
                        image_entries.append({
                            "image_path": selected_paths[slot.image_index],
                            "month_index": month_idx,
                            "slot_index": slot_idx,
                        })
            cal = repo.create(
                preset=result.preset,
                year=result.year,
                custom_instructions=body.custom_instructions,
                html_content=result.html_content,
                html_path=html_path,
                pdf_path=pdf_path,
                model_used=body.model,
                image_entries=image_entries,
            )
            calendar_id = cal.id
        finally:
            session.close()

        emit_fn("start", "done", "Kalender-Generierung abgeschlossen.")
        event_manager.complete_run(
            run_id, "success", output_base,
            calendar_id=calendar_id,
            pdf_available=pdf_path is not None,
        )

    except Exception as e:
        emit_fn("error", "error", str(e))
        event_manager.complete_run(run_id, "failed", "")


@router.get("/calendars")
async def get_calendars(
    year: Optional[int] = None,
    preset: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
):
    """Liste aller persistierten Kalender."""
    filters = CalendarFilters(limit=limit, offset=offset)
    if year:
        filters.year = year
    if preset:
        filters.preset = preset

    session = get_session()
    try:
        repo = CalendarRepository(session)
        records, total = repo.list(filters)
        return {"calendars": [_calendar_to_summary(c) for c in records], "total": total}
    finally:
        session.close()


@router.get("/calendars/{calendar_id}")
async def get_calendar(calendar_id: int):
    """Einzelnen Kalender mit vollständigem Inhalt abrufen."""
    session = get_session()
    try:
        repo = CalendarRepository(session)
        record = repo.get_by_id(calendar_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Calendar not found")
        return {"calendar": _calendar_to_detail(record)}
    finally:
        session.close()


@router.delete("/calendars/{calendar_id}")
async def delete_calendar(calendar_id: int):
    """Kalender und zugehörige Dateien löschen."""
    session = get_session()
    try:
        repo = CalendarRepository(session)
        record = repo.get_by_id(calendar_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Calendar not found")

        output_dir = os.path.dirname(record.html_path) if record.html_path else None
        repo.delete(calendar_id)

        if output_dir and os.path.exists(output_dir):
            try:
                shutil.rmtree(output_dir)
            except OSError as e:
                logging.getLogger("api").warning("Konnte Output-Verzeichnis nicht löschen: %s", e)

        return {"deleted": calendar_id}
    finally:
        session.close()


@router.get("/calendars/{calendar_id}/pdf")
async def get_calendar_pdf(calendar_id: int):
    """PDF eines Kalenders ausliefern."""
    session = get_session()
    try:
        repo = CalendarRepository(session)
        record = repo.get_by_id(calendar_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Kalender nicht gefunden")
        if not record.pdf_path:
            raise HTTPException(status_code=400, detail="Kalender hat kein PDF")

        path = Path(record.pdf_path)
        if not path.exists():
            raise HTTPException(status_code=404, detail="PDF-Datei nicht gefunden")

        return FileResponse(
            path,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{path.name}"',
                "Cache-Control": "no-cache",
            },
        )
    finally:
        session.close()


@router.get("/calendars/{calendar_id}/images/{filename}")
async def get_calendar_image(calendar_id: int, filename: str):
    """Bilddatei eines Kalenders ausliefern."""
    session = get_session()
    try:
        repo = CalendarRepository(session)
        record = repo.get_by_id(calendar_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Calendar not found")

        for img in record.images:
            if os.path.basename(img.image_path) == filename:
                if os.path.isfile(img.image_path):
                    return FileResponse(img.image_path)
                break

        output_dir = None
        if record.html_path:
            output_dir = os.path.dirname(record.html_path)

        if output_dir:
            image_path = _safe_join(Path(output_dir), "images", filename)
            if image_path.is_file():
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
