# app/services/persist_article.py
"""Service zum Persistieren generierter Blogposts in der Datenbank."""
from datetime import datetime, date
from typing import Optional, List, Dict, Any

from app.db.connection import get_session
from app.db.repository import ArticleRepository


def _extract_title(markdown: str) -> Optional[str]:
    """Extrahiert den H1-Titel aus dem Markdown-Text."""
    for line in markdown.split("\n"):
        line = line.strip()
        if line.startswith("# ") and not line.startswith("## "):
            return line[2:].strip()
    return None


def _compute_tour_date_and_duration(gpx_stats, images) -> tuple[Optional[date], Optional[float], Optional[str]]:
    """
    Berechnet tour_date und tour_duration aus GPX oder Foto-Timestamps.
    Gibt (tour_date, tour_duration_hours, tour_duration_source) zurück.
    """
    # GPX primary source
    if gpx_stats and hasattr(gpx_stats, "points") and gpx_stats.points:
        points = gpx_stats.points
        if len(points) >= 2 and points[0].time and points[-1].time:
            start = points[0].time
            end = points[-1].time
            duration_hours = (end - start).total_seconds() / 3600.0
            return start.date(), abs(duration_hours), "gpx"

    # Photos fallback
    if images:
        timestamps = [
            datetime.fromisoformat(img.get("timestamp"))
            for img in images
            if isinstance(img, dict) and img.get("timestamp")
        ]
        if len(timestamps) >= 2:
            start = min(timestamps)
            end = max(timestamps)
            duration_hours = (end - start).total_seconds() / 3600.0
            return start.date(), abs(duration_hours), "photos"

    return None, None, None


def persist_article(
    blog_post: Dict[str, Any],
    gpx_stats: Any,
    images: list,
    gpx_file: str,
    model: str,
    notes: Optional[str] = None,
) -> Optional[int]:
    """
    Persistiert einen generierten Blogpost in der Datenbank.

    Args:
        blog_post: Das Ergebnis von generate_blog_post (dict mit markdown, html, file_paths, selected_images)
        gpx_stats: GPXStats-Objekt aus dem State
        images: Liste der im Blog verwendeten Bilder (List[ImageData])
        gpx_file: Pfad zur GPX-Datei
        model: Verwendetes Modell
        notes: Optional: Notizen zur Tour

    Returns:
        article_id oder None bei Fehler
    """
    if not blog_post or not blog_post.get("success"):
        return None

    markdown = blog_post.get("markdown", "")
    html = blog_post.get("html", "")
    file_paths = blog_post.get("file_paths", {})
    selected_images = blog_post.get("selected_images", [])

    tour_date, tour_duration_hours, tour_duration_source = _compute_tour_date_and_duration(
        gpx_stats, [img.model_dump() for img in images] if images else []
    )

    distance_m = gpx_stats.total_distance_m if gpx_stats else None
    gain_m = gpx_stats.elevation_gain_m if gpx_stats else None
    loss_m = gpx_stats.elevation_loss_m if gpx_stats else None

    article_data = {
        "title": _extract_title(markdown),
        "tour_date": tour_date,
        "tour_duration_hours": round(tour_duration_hours, 2) if tour_duration_hours else None,
        "tour_duration_source": tour_duration_source,
        "generation_timestamp": datetime.now(),
        "gpx_file": gpx_file,
        "total_distance_km": round(distance_m / 1000.0, 2) if distance_m else None,
        "elevation_gain_m": round(gain_m, 0) if gain_m else None,
        "elevation_loss_m": round(loss_m, 0) if loss_m else None,
        "image_count": len(selected_images),
        "markdown_content": markdown,
        "html_content": html,
        "markdown_path": file_paths.get("markdown", ""),
        "html_path": file_paths.get("html", ""),
        "model_used": model,
        "notes": notes,
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
        print(f"❌ Fehler beim Persistieren des Artikels: {e}")
        return None
