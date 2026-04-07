# app/nodes/generate_map.py

from app.state import AppState
from app.services.generate_mapimage import generate_map_html, html_to_png
import os


def generate_map_image_node(state: AppState) -> AppState:
    if state.gpx_stats is None or not state.gpx_stats.points:
        print("⚠️ No GPX data available for map generation.")
        return state

    # Output-Verzeichnis
    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)

    html_path = os.path.join(output_dir, "map.html")
    png_path = os.path.join(output_dir, "map.png")

    # 1. HTML generieren
    generate_map_html(state.gpx_stats.points, html_path)

    # 2. PNG erzeugen
    html_to_png(html_path, png_path)

    # 3. im State speichern
    state.metadata["map_image_path"] = png_path

    return state
