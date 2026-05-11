# app/services/persist_article.py
"""Service zum Persistieren generierter Blogposts in der Datenbank."""
import logging
from datetime import datetime
from typing import Optional, List

from app.db.connection import get_session
from app.db.repository import ArticleRepository
from app.state import BlogPostResult, ImageData
from app.services.gpx_analytics import GPXStats
from app.utils.html_sanitizer import sanitize_html
from app.utils.tour_metadata import compute_tour_date_and_duration, build_tour_stats

logger = logging.getLogger(__name__)


def _extract_title(markdown: str) -> Optional[str]:
    """Extrahiert den H1-Titel aus dem Markdown-Text."""
    for line in markdown.split("\n"):
        line = line.strip()
        if line.startswith("# ") and not line.startswith("## "):
            return line[2:].strip()
    return None


def persist_article(
    blog_post: BlogPostResult,
    gpx_stats: GPXStats,
    images: List[ImageData],
    gpx_file: str,
    model: str,
    notes: Optional[str] = None,
    status: str = "published",
) -> Optional[int]:
    """
    Persistiert einen generierten Blogpost in der Datenbank.

    Args:
        blog_post: Das Ergebnis von generate_blog_post (BlogPostResult)
        gpx_stats: GPXStats-Objekt aus dem State
        images: Liste der im Blog verwendeten Bilder (List[ImageData])
        gpx_file: Pfad zur GPX-Datei
        model: Verwendetes Modell
        notes: Optional: Notizen zur Tour
        status: Status des Artikels ("published" oder "draft")

    Returns:
        article_id oder None bei Fehler
    """
    if not blog_post or not blog_post.success:
        return None

    markdown = blog_post.markdown or ""
    html = blog_post.html or ""
    file_paths = blog_post.file_paths or {}
    selected_images = blog_post.selected_images or []

    tour_date, tour_duration_hours, tour_duration_source = compute_tour_date_and_duration(
        gpx_stats, [img.model_dump() for img in images] if images else []
    )

    tour_stats = build_tour_stats(gpx_stats)

    article_data = {
        "title": _extract_title(markdown),
        "tour_date": tour_date,
        "tour_duration_hours": round(tour_duration_hours, 2) if tour_duration_hours else None,
        "tour_duration_source": tour_duration_source,
        "generation_timestamp": datetime.now(),
        "gpx_file": gpx_file,
        "total_distance_km": tour_stats.get("total_distance_km"),
        "elevation_gain_m": tour_stats.get("elevation_gain_m"),
        "elevation_loss_m": tour_stats.get("elevation_loss_m"),
        "image_count": len(selected_images),
        "markdown_content": markdown,
        "html_content": sanitize_html(html),
        "markdown_path": file_paths.get("markdown", ""),
        "html_path": file_paths.get("html", ""),
        "model_used": model,
        "notes": notes,
        "status": status,
        "revision_round": 0,
    }

    image_records = []
    for img_path in selected_images:
        image_records.append({
            "image_path": img_path,
            "is_map": img_path.endswith("00_map.png"),
            "is_elevation_profile": img_path.endswith("00_elevation_profile.png"),
        })

    try:
        session = get_session()
        try:
            repo = ArticleRepository(session)
            article_id = repo.insert(article_data, image_records)
            return article_id
        finally:
            session.close()
    except Exception as e:
        logger.error("Fehler beim Persistieren des Artikels: %s", e)
        return None
