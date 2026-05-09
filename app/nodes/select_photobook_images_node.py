import logging

from app.state import AppState
from app.photobook.image_selector import select_photobook_images
from app.nodes.plan_photobook_node import _get_photobook_context

logger = logging.getLogger(__name__)


def select_photobook_images_node(state: AppState) -> AppState:
    logger.info("Waehle Bilder fuer das Fotobuch aus...")
    if not state.images:
        logger.warning("Keine Bilder fuer Fotobuch-Auswahl vorhanden.")
        return state
    gpx_dict, preset = _get_photobook_context(state)
    try:
        selected = select_photobook_images(
            images=state.images, gpx_stats=gpx_dict, notes=state.notes,
            model=state.model, photo_count=state.output_config.photobook.photo_count,
            preset=preset,
        )
        state.photobook_images = selected
        logger.info("%s Bilder fuer das Fotobuch ausgewaehlt.", len(selected))
    except Exception as e:
        logger.error("Fotobuch-Bildauswahl fehlgeschlagen: %s — verwende alle Bilder", e)
        max_count = state.output_config.photobook.photo_count
        state.photobook_images = state.images[:max_count]
    return state
