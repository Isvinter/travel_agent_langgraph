# app/nodes/persist_article.py
import logging

from app.state import AppState
from app.services.persist_article import persist_article

logger = logging.getLogger(__name__)


def persist_article_node(state: AppState) -> AppState:
    """Persistiert den generierten Blogpost in der Datenbank."""
    logger.info("Persisting article to database...")

    if not state.blog_post:
        logger.warning("No blog post to persist.")
        return state

    try:
        article_id = persist_article(
            blog_post=state.blog_post,
            gpx_stats=state.gpx_stats,
            images=state.images,
            gpx_file=state.gpx_file,
            model=state.model,
            notes=state.notes,
        )
    except Exception as e:
        logger.error("Article persistence failed: %s", e)
        article_id = None

    if article_id:
        logger.info("Article persisted with ID: %s", article_id)
        state.metadata["article_id"] = article_id
    else:
        logger.warning("Article was not persisted (generation failed or DB error).")
        state.metadata["article_id"] = None

    return state
