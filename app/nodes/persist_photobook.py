# app/nodes/persist_photobook.py
import logging

from app.state import AppState
from app.services.persist_photobook import persist_photobook

logger = logging.getLogger(__name__)


def persist_photobook_node(state: AppState) -> AppState:
    """Persistiert das generierte Fotobuch in der Datenbank."""
    logger.info("Persisting photobook to database...")

    try:
        photobook_id = persist_photobook(
            gpx_stats=state.gpx_stats,
            photobook_images=state.photobook_images,
            photobook_pages=state.photobook_pages,
            photobook_html=state.photobook_html,
            photobook_html_path=state.photobook_html_path,
            photobook_pdf_path=state.photobook_pdf_path,
            photobook_size=state.output_config.photobook.size,
            gpx_file=state.gpx_file,
            model=state.model,
            notes=state.notes,
        )
    except Exception as e:
        logger.error("Photobook persistence failed: %s", e)
        photobook_id = None

    if photobook_id:
        logger.info("Photobook persisted with ID: %s", photobook_id)
        state.metadata["photobook_id"] = photobook_id
    else:
        logger.warning("Photobook was not persisted (DB error).")
        state.metadata["photobook_id"] = None

    return state
