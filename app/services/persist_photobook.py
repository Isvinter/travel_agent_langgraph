# app/services/persist_photobook.py
"""Service zum Persistieren generierter Fotobücher in der Datenbank."""
import logging
import os
from datetime import datetime
from typing import Optional, List

from app.db.connection import get_session
from app.db.photobook_repository import PhotobookRepository
from app.utils.html_sanitizer import sanitize_html
from app.utils.tour_metadata import compute_tour_date_and_duration, build_tour_stats

logger = logging.getLogger(__name__)


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
    tour_date, tour_duration_hours, tour_duration_source = compute_tour_date_and_duration(
        gpx_stats, photobook_images
    )

    tour_stats = build_tour_stats(gpx_stats)

    title = _extract_photobook_title(photobook_pages, gpx_file)

    photobook_data = {
        "title": title,
        "tour_date": tour_date,
        "tour_duration_hours": round(tour_duration_hours, 2) if tour_duration_hours else None,
        "tour_duration_source": tour_duration_source,
        "generation_timestamp": datetime.now(),
        "gpx_file": gpx_file,
        "total_distance_km": tour_stats.get("total_distance_km"),
        "elevation_gain_m": tour_stats.get("elevation_gain_m"),
        "elevation_loss_m": tour_stats.get("elevation_loss_m"),
        "image_count": _count_images_in_pages(photobook_pages),
        "html_content": sanitize_html(photobook_html or "", keep_style=True),
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
        logger.error("Fehler beim Persistieren des Fotobuchs: %s", e)
        return None
