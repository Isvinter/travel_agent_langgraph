"""Gemeinsame Tour-Metadaten-Extraktion (Datum, Dauer).

Wird sowohl von persist_article.py als auch persist_photobook.py verwendet,
um doppelte _compute_tour_date_and_duration-Implementierungen zu eliminieren.
"""

from datetime import date, datetime
from typing import Any, Optional


def compute_tour_date_and_duration(
    gpx_stats: Any,
    images: list,
) -> tuple[Optional[date], Optional[float], Optional[str]]:
    """Berechnet tour_date und tour_duration aus GPX oder Foto-Timestamps.

    Primaerquelle: GPX-Track-Daten (points[0].time → points[-1].time).
    Fallback:    EXIF-Timestamps der geladenen Bilder (min → max).

    Args:
        gpx_stats: GPXStats-Objekt mit .points Attribut (kann None sein)
        images:    Liste von dicts oder Pydantic-Objekten mit .timestamp / ["timestamp"]

    Returns:
        (tour_date, tour_duration_hours, source) als Tuple.
        source ist "gpx", "photos" oder None (keine Daten).
    """
    if gpx_stats and hasattr(gpx_stats, "points") and gpx_stats.points:
        points = gpx_stats.points
        if len(points) >= 2 and points[0].time and points[-1].time:
            start = points[0].time
            end = points[-1].time
            duration_hours = (end - start).total_seconds() / 3600.0
            return start.date(), abs(duration_hours), "gpx"

    if images:
        timestamps: list[datetime] = []
        for img in images:
            if isinstance(img, dict):
                ts = img.get("timestamp")
            elif hasattr(img, "timestamp"):
                ts = img.timestamp
            else:
                continue
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
