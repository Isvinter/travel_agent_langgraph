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