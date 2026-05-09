# app/nodes/save_draft.py
"""Node: Speichert den generierten Blogpost als Draft in der Datenbank."""
import logging

from app.state import AppState
from app.services.persist_article import persist_article

logger = logging.getLogger(__name__)


def save_draft_node(state: AppState) -> AppState:
    """Speichert den generierten Blogpost als Draft in der Datenbank."""
    blog_post = state.blog_post
    if not blog_post:
        return state

    try:
        article_id = persist_article(
            blog_post=blog_post,
            gpx_stats=state.gpx_stats,
            images=state.selected_images,
            gpx_file=state.gpx_file,
            model=state.model,
            notes=state.notes,
            status="draft",
        )

        if article_id:
            state.metadata["article_id"] = article_id
    except Exception as e:
        logger.error("Draft-Persistierung fehlgeschlagen: %s", e)

    return state
