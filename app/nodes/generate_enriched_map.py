# app/nodes/generate_enriched_map.py

from app.state import AppState
from app.services.generate_mapimage import generate_enriched_map_html, html_to_png
import os


def generate_enriched_map_node(state: AppState) -> AppState:
    if state.gpx_stats is None or not state.gpx_stats.points:
        print("⚠️  No GPX data available for enriched map generation.")
        return state

    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)

    html_path = os.path.join(output_dir, "enriched_map.html")
    png_path = os.path.join(output_dir, "enriched_map.png")

    generate_enriched_map_html(
        points=state.gpx_stats.points,
        pauses=state.gpx_pauses,
        images=state.selected_images,
        output_html=html_path,
    )

    html_to_png(html_path, png_path)

    state.metadata["enriched_map_image_path"] = png_path

    print(f"🗺️  Enriched map generated: {png_path}")
    return state
