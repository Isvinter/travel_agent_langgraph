import logging
from pathlib import Path

from app.state import AppState
from app.services.load_tour_notes import load_tour_notes

logger = logging.getLogger(__name__)


def load_tour_notes_node(state: AppState) -> AppState:
    """Liest optionale Tour-Notizen.

    Wenn state.notes bereits gesetzt ist (z.B. über API-Request), bleibt
    es erhalten. Andernfalls wird aus dem data/notes/-Verzeichnis geladen.
    """
    if state.notes:
        logger.info("Using notes from request (%s chars)", len(state.notes))
        return state

    notes_dir = str(Path(__file__).resolve().parent.parent.parent / "data" / "notes")
    try:
        state.notes = load_tour_notes(notes_dir) or None
    except Exception as e:
        logger.error("Loading tour notes failed: %s — continuing without notes", e)
        state.notes = None
    if state.notes:
        logger.info("Loaded notes (%s chars)", len(state.notes))
    else:
        logger.info("No notes found (optional)")
    return state
