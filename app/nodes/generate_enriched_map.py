# app/nodes/generate_enriched_map.py

from app.state import AppState
from app.nodes.generate_map import _generate_map
from app.services.generate_mapimage import generate_enriched_map_html, html_to_png  # noqa: F401 — für Test-Patches


def generate_enriched_map_node(state: AppState) -> AppState:
    return _generate_map(
        state,
        html_gen_fn=generate_enriched_map_html,
        html_name="enriched_map.html",
        png_name="enriched_map.png",
        state_key="enriched_map_image_path",
        display_name="Enriched map generated",
        points=state.gpx_stats.points if state.gpx_stats else [],
        pauses=state.gpx_pauses,
        images=state.selected_images,
    )
