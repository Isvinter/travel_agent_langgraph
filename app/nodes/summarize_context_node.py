import logging
from app.state import AppState
from app.services.summarize_context import summarize_context

logger = logging.getLogger(__name__)


def summarize_context_node(state: AppState) -> AppState:
    logger.info("Erstelle Tour-Zusammenfassung...")
    distance_km = None
    elevation_m = None
    if state.gpx_stats:
        distance_km = state.gpx_stats.total_distance_m / 1000.0
        elevation_m = state.gpx_stats.elevation_gain_m

    state.tour_summary = summarize_context(
        notes=state.notes,
        gpx_distance_km=distance_km,
        gpx_elevation_m=elevation_m,
        preset=state.output_config.photobook_preset,
        model=state.model,
    )
    logger.info("Tour-Summary: %s", state.tour_summary[:100] if state.tour_summary else "None")
    return state
