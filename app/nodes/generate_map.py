# app/nodes/generate_map.py

import logging
from typing import Callable
from app.state import AppState
from app.services.generate_mapimage import generate_map_html, html_to_png
import os

logger = logging.getLogger(__name__)


def _generate_map(
    state: AppState,
    html_gen_fn: Callable,
    html_name: str,
    png_name: str,
    state_key: str,
    display_name: str,
    **html_kwargs,
) -> AppState:
    """Generischer Helper: generiert HTML, konvertiert zu PNG, speichert im State."""
    if state.gpx_stats is None or not state.gpx_stats.points:
        logger.warning("No GPX data for %s generation.", display_name)
        return state

    output_dir = getattr(state, "output_dir", None) or "output"
    os.makedirs(output_dir, exist_ok=True)

    html_path = os.path.join(output_dir, html_name)
    png_path = os.path.join(output_dir, png_name)

    try:
        html_gen_fn(output_html=html_path, **html_kwargs)
        html_to_png(html_path, png_path)
        state.map_image_path = png_path
        logger.info("%s: %s", display_name, png_path)
    except Exception as e:
        logger.error("%s failed: %s — continuing", display_name, e)

    return state


def generate_map_image_node(state: AppState) -> AppState:
    return _generate_map(
        state,
        html_gen_fn=generate_map_html,
        html_name="map.html",
        png_name="map.png",
        state_key="map_image_path",
        display_name="Map generated",
        points=state.gpx_stats.points if state.gpx_stats else [],
    )
