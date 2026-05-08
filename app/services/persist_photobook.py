# app/services/persist_photobook.py
"""Service zum Persistieren generierter Fotobücher in der Datenbank."""
import os
import re
from datetime import datetime, date
from typing import Optional, List

from app.db.connection import get_session
from app.db.photobook_repository import PhotobookRepository


def _extract_photobook_title(photobook_pages: List, gpx_file: str) -> Optional[str]:
    """Extrahiert den Fotobuch-Titel aus der Titelseite des LLM-Generats."""
    if photobook_pages:
        cover_page = photobook_pages[0]
        for slot in (cover_page.slots if hasattr(cover_page, "slots") else cover_page.get("slots", [])):
            if slot.get("slot_id") == "title" and slot.get("text", "").strip():
                return slot["text"]

    if gpx_file:
        base = os.path.splitext(os.path.basename(gpx_file))[0].strip()
        if base:
            return base

    return None


def _sanitize_html(html: str) -> str:
    """Entfernt potenziell gefährliche Inhalte aus LLM-generiertem HTML.

    Style-Tags werden NICHT entfernt — das Fotobuch-CSS wird für das
    Layout im iframe benötigt.
    """
    if not html:
        return html
    html = re.sub(r'<script[^>]*>.*?</script\s*>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<script[^>]*/>', '', html, flags=re.IGNORECASE)
    html = re.sub(r'\s+on\w+\s*=\s*"[^"]*"', '', html, flags=re.IGNORECASE)
    html = re.sub(r"\s+on\w+\s*=\s*'[^']*'", '', html, flags=re.IGNORECASE)
    html = re.sub(r'\s+on\w+\s*=\s*\S+', '', html, flags=re.IGNORECASE)
    html = re.sub(r'(href|src)\s*=\s*"[^"]*javascript:[^"]*"', r'\1="#"', html, flags=re.IGNORECASE)
    html = re.sub(r"(href|src)\s*=\s*'[^']*javascript:[^']*'", r"\1='#'", html, flags=re.IGNORECASE)
    return html


def _compute_tour_date_and_duration(gpx_stats, photobook_images) -> tuple:
    """Berechnet tour_date und tour_duration aus GPX oder Foto-Timestamps."""
    if gpx_stats and hasattr(gpx_stats, "points") and gpx_stats.points:
        points = gpx_stats.points
        if len(points) >= 2 and points[0].time and points[-1].time:
            start = points[0].time
            end = points[-1].time
            duration_hours = (end - start).total_seconds() / 3600.0
            return start.date(), abs(duration_hours), "gpx"

    if photobook_images:
        timestamps = []
        for img in photobook_images:
            ts = img.timestamp if hasattr(img, "timestamp") else img.get("timestamp")
            if not ts:
                continue
            try:
                timestamps.append(datetime.fromisoformat(str(ts)))
            except (ValueError, TypeError):
                continue
        if len(timestamps) >= 2:
            start = min(timestamps)
            end = max(timestamps)
            duration_hours = (end - start).total_seconds() / 3600.0
            return start.date(), abs(duration_hours), "photos"

    return None, None, None


def _count_images_in_pages(photobook_pages: List) -> int:
    """Zaehlt die tatsaechlich im Fotobuch verwendeten Bilder (unique image_index)."""
    used = set()
    for page in photobook_pages:
        slots = page.slots if hasattr(page, "slots") else page.get("slots", []) if isinstance(page, dict) else []
        for slot in slots:
            idx = slot.get("image_index") if isinstance(slot, dict) else getattr(slot, "image_index", None)
            if idx is not None and idx >= 0:
                used.add(idx)
    return len(used)


def persist_photobook(
    gpx_stats,
    photobook_images: List,
    photobook_pages: List,
    photobook_html: Optional[str],
    photobook_html_path: Optional[str],
    photobook_pdf_path: Optional[str],
    photobook_size: Optional[str],
    gpx_file: str,
    model: str,
    notes: Optional[str] = None,
) -> Optional[int]:
    """Persistiert ein generiertes Fotobuch in der Datenbank."""
    tour_date, tour_duration_hours, tour_duration_source = _compute_tour_date_and_duration(
        gpx_stats, photobook_images
    )

    distance_m = gpx_stats.total_distance_m if gpx_stats else None
    gain_m = gpx_stats.elevation_gain_m if gpx_stats else None
    loss_m = gpx_stats.elevation_loss_m if gpx_stats else None

    title = _extract_photobook_title(photobook_pages, gpx_file)

    photobook_data = {
        "title": title,
        "tour_date": tour_date,
        "tour_duration_hours": round(tour_duration_hours, 2) if tour_duration_hours else None,
        "tour_duration_source": tour_duration_source,
        "generation_timestamp": datetime.now(),
        "gpx_file": gpx_file,
        "total_distance_km": round(distance_m / 1000.0, 2) if distance_m else None,
        "elevation_gain_m": round(gain_m, 0) if gain_m else None,
        "elevation_loss_m": round(loss_m, 0) if loss_m else None,
        "image_count": _count_images_in_pages(photobook_pages),
        "html_content": _sanitize_html(photobook_html or ""),
        "html_path": photobook_html_path or "",
        "model_used": model,
        "notes": notes,
        "pdf_path": photobook_pdf_path,
        "page_count": len(photobook_pages),
        "photobook_size": photobook_size,
    }

    image_records = []
    for img in photobook_images:
        path = img.path if hasattr(img, "path") else img.get("path", "")
        image_records.append({
            "image_path": path,
            "is_map": path.endswith("00_map.png"),
            "is_elevation_profile": path.endswith("00_elevation_profile.png"),
        })

    try:
        session = get_session()
        try:
            repo = PhotobookRepository(session)
            photobook_id = repo.insert(photobook_data, image_records)
            return photobook_id
        finally:
            session.close()
    except Exception as e:
        print(f"❌ Fehler beim Persistieren des Fotobuchs: {e}")
        return None
