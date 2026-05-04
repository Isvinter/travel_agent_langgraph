import folium
import math
from typing import List
from app.services.gpx_analytics import TrackPoint


def generate_map_html(points: List[TrackPoint], output_html: str):
    # Mittelpunkt
    avg_lat = sum(p.lat for p in points) / len(points)
    avg_lon = sum(p.lon for p in points) / len(points)

    # Bounding Box
    min_lat = min(p.lat for p in points)
    max_lat = max(p.lat for p in points)
    min_lon = min(p.lon for p in points)
    max_lon = max(p.lon for p in points)

    # Padding (Meter)
    padding_m = 500

    # Meter → Grad
    lat_pad = padding_m / 111000
    lon_pad = padding_m / (111000 * math.cos(math.radians(avg_lat)))

    # Erweiterte Bounds
    south = min_lat - lat_pad
    north = max_lat + lat_pad
    west = min_lon - lon_pad
    east = max_lon + lon_pad

    # Map
    m = folium.Map(
    location=[avg_lat, avg_lon],
    tiles="https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png",
    attr="© OpenTopoMap"
    )

    coords = [(p.lat, p.lon) for p in points]

    folium.PolyLine(coords, weight=4).add_to(m)

    # Start / Ende Marker (optional aber nice)
    folium.Marker(coords[0], tooltip="Start").add_to(m)
    folium.Marker(coords[-1], tooltip="Ende").add_to(m)

    # Auto-Zoom mit Padding
    m.fit_bounds([[south, west], [north, east]])

    m.save(output_html)

def html_to_png(html_path: str, output_png: str):
    import os
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    import time

    options = Options()
    options.add_argument("--headless")
    options.add_argument("--window-size=1200,800")

    driver = webdriver.Chrome(options=options)

    abs_path = os.path.abspath(html_path)
    driver.get(f"file:///{abs_path}")

    time.sleep(2)  # Karte laden lassen

    driver.save_screenshot(output_png)
    driver.quit()


def _haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distanz in Metern zwischen zwei Koordinaten (Haversine-Formel)."""
    R = 6371000  # Erdradius in Metern
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def _match_photos_to_pauses(images, pauses, distance_m: float = 50.0):
    """Ordnet Fotos Pausen zu (räumlich + zeitlich).

    Kriterien (beide müssen erfüllt sein):
      1. Haversine-Distanz Foto-Pause <= distance_m
      2. Foto-Timestamp liegt zwischen Pausen-Start und Pausen-Ende

    Rückgabe: {pause_index: [foto_index, ...]}
    Nur Pausen mit mindestens einem zugeordneten Foto erscheinen im Dict.
    Ein Foto kann mehreren Pausen zugeordnet sein (Überlappung).
    """
    from datetime import datetime as _dt

    result: dict[int, list[int]] = {}

    for pause_idx, pause in enumerate(pauses):
        loc = pause.get("location", {})
        p_lat = loc.get("lat")
        p_lon = loc.get("lon")
        if p_lat is None or p_lon is None:
            continue

        start = pause.get("start_time")
        end = pause.get("end_time")

        for foto_idx, img in enumerate(images):
            f_lat = img.latitude if hasattr(img, "latitude") else img.get("latitude")
            f_lon = img.longitude if hasattr(img, "longitude") else img.get("longitude")
            if f_lat is None or f_lon is None:
                continue

            # Räumliche Prüfung
            if _haversine_distance(p_lat, p_lon, f_lat, f_lon) > distance_m:
                continue

            # Zeitliche Prüfung
            ts_str = img.timestamp if hasattr(img, "timestamp") else img.get("timestamp")
            if not ts_str or not start or not end:
                continue

            try:
                ts = _dt.fromisoformat(ts_str) if isinstance(ts_str, str) else ts_str
            except (ValueError, TypeError):
                continue

            # Normalisiere Zeitzonen: GPX-Zeiten können tz-aware sein, EXIF ist naiv
            if start.tzinfo is not None:
                start = start.replace(tzinfo=None)
            if end.tzinfo is not None:
                end = end.replace(tzinfo=None)

            if start <= ts <= end:
                result.setdefault(pause_idx, []).append(foto_idx)

    return result


def generate_enriched_map_html(
    points: List[TrackPoint],
    pauses: list,
    images: list,
    output_html: str,
):
    """Generiert eine Folium-Karte mit Route, Pausen-Markern und Bild-Markern."""
    # Mittelpunkt und Bounding Box (wie generate_map_html)
    avg_lat = sum(p.lat for p in points) / len(points)
    avg_lon = sum(p.lon for p in points) / len(points)

    min_lat = min(p.lat for p in points)
    max_lat = max(p.lat for p in points)
    min_lon = min(p.lon for p in points)
    max_lon = max(p.lon for p in points)

    padding_m = 500
    lat_pad = padding_m / 111000
    lon_pad = padding_m / (111000 * math.cos(math.radians(avg_lat)))

    south = min_lat - lat_pad
    north = max_lat + lat_pad
    west = min_lon - lon_pad
    east = max_lon + lon_pad

    m = folium.Map(
        location=[avg_lat, avg_lon],
        tiles="https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png",
        attr="© OpenTopoMap",
    )

    coords = [(p.lat, p.lon) for p in points]
    folium.PolyLine(coords, weight=4).add_to(m)

    # Start / Ende Marker
    folium.Marker(
        coords[0],
        tooltip="Start",
        icon=folium.Icon(color="green", icon="flag", prefix="fa"),
    ).add_to(m)
    folium.Marker(
        coords[-1],
        tooltip="Ende",
        icon=folium.Icon(color="red", icon="flag-checkered", prefix="fa"),
    ).add_to(m)

    # Pausen-Marker
    for pause in pauses:
        loc = pause.get("location", {})
        lat = loc.get("lat")
        lon = loc.get("lon")
        if lat is None or lon is None:
            continue
        duration = pause.get("duration_minutes", 0)
        start = pause.get("start_time", "")
        end = pause.get("end_time", "")
        popup_text = f"{start} – {end}" if start and end else ""
        folium.Marker(
            [lat, lon],
            tooltip=f"Pause: {duration} min",
            popup=folium.Popup(popup_text, max_width=200) if popup_text else None,
            icon=folium.Icon(color="orange", icon="pause", prefix="fa"),
        ).add_to(m)

    # Bild-Marker
    for idx, img in enumerate(images, 1):
        lat = img.latitude if hasattr(img, "latitude") else img.get("latitude")
        lon = img.longitude if hasattr(img, "longitude") else img.get("longitude")
        if lat is None or lon is None:
            continue
        timestamp = img.timestamp if hasattr(img, "timestamp") else img.get("timestamp", "")
        folium.Marker(
            [lat, lon],
            tooltip=f"Bild {idx}: {timestamp}",
            icon=folium.Icon(color="blue", icon="camera", prefix="fa"),
        ).add_to(m)

    m.fit_bounds([[south, west], [north, east]])
    m.save(output_html)