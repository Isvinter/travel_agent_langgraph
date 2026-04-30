# app/nodes/persist_article.py
from app.state import AppState
from app.services.persist_article import persist_article


def persist_article_node(state: AppState) -> AppState:
    """Persistiert den generierten Blogpost in der Datenbank."""
    print("💾 Persisting article to database...")

    if not state.blog_post:
        print("⚠️ No blog post to persist.")
        return state

    article_id = persist_article(
        blog_post=state.blog_post,
        gpx_stats=state.gpx_stats,
        images=state.images,
        gpx_file=state.gpx_file,
        model=state.model,
        notes=state.notes,
    )

    if article_id:
        print(f"✅ Article persisted with ID: {article_id}")
        state.metadata["article_id"] = article_id
    else:
        print("⚠️ Article was not persisted (generation failed or DB error).")
        state.metadata["article_id"] = None

    return state
