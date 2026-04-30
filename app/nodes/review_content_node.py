# app/nodes/review_content_node.py
from app.state import AppState
from app.services.content_reviewer import review_enrichment


def review_content_node(state: AppState) -> AppState:
    """Prüft angereicherte Inhalte auf Qualität und thematische Passung.

    Single-Pass LLM Quality Gate — kein iterativer Loop.
    Interface ist für spätere Human-in-the-Loop-Erweiterung ausgelegt.
    """
    print("🔍 Running content quality review...")

    state.enrichment_context = review_enrichment(
        weather=state.weather,
        poi_list=state.poi_list,
        selected_images=state.selected_images,
        gpx_stats=state.gpx_stats,
        notes=state.notes,
        model=state.model,
    )

    score = state.enrichment_context.get("coherence_score", 0)
    print(f"✅ Content review complete (coherence: {score}/10)")

    return state
