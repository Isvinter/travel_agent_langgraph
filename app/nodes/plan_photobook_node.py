import logging

from app.state import AppState
from app.photobook.plan import plan_photobook_layout
from app.photobook.presets import get_photobook_preset

logger = logging.getLogger(__name__)


def _get_photobook_context(state: AppState):
    """Extrahiert gpx_dict und preset aus AppState (gemeinsam fuer Photobook-Nodes)."""
    try:
        gpx_dict = state.gpx_stats.model_dump() if state.gpx_stats else {}
    except Exception:
        gpx_dict = {}
    preset = get_photobook_preset(state.output_config.photobook_preset)
    return gpx_dict, preset


def plan_photobook_node(state: AppState) -> AppState:
    logger.info("Plane Fotobuch-Layout (LLM Pass 1)...")
    if not state.photobook_images:
        logger.warning("Keine Bilder fuer Fotobuch-Planung vorhanden.")
        return state
    gpx_dict, preset = _get_photobook_context(state)
    try:
        plan = plan_photobook_layout(
            images=state.photobook_images,
            gpx_stats=gpx_dict,
            tour_summary=state.tour_summary,
            model=state.model,
            page_range=state.output_config.photobook.page_range,
            preset=preset,
        )
        state.photobook_plan = plan
        logger.info("Layout-Planung abgeschlossen: %s Seiten geplant.", len(plan.pages))
    except Exception as e:
        logger.error("Fotobuch-Planung fehlgeschlagen: %s", e)
        from app.state import PhotobookPlan
        state.photobook_plan = PhotobookPlan(pages=[])
    return state
