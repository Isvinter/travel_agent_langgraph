# app/nodes/review_content_node.py
from app.state import AppState
from app.services.content_reviewer import review_enrichment


def review_content_node(state: AppState) -> AppState:
    """Prüft angereicherte Inhalte auf Qualität und thematische Passung.

    Filtert zudem überzählige Bilder anhand der LLM-Qualitätsbewertung
    auf maximal wildcard_max (≥33% der oversampled Bilder werden verworfen).
    """
    print("🔍 Running content quality review...")

    ctx = review_enrichment(
        weather=state.weather,
        poi_list=state.poi_list,
        selected_images=state.selected_images,
        gpx_stats=state.gpx_stats,
        notes=state.notes,
        model=state.model,
        output_config=state.output_config,
    )

    # Auf wildcard_max kappen — die ≥33% Discard-Quote ist automatisch
    # erfüllt, da select_images ceil(N*1.5) liefert und hier auf N gekappt wird.
    filtered = ctx.get("filtered_images", state.selected_images)
    before = len(state.selected_images)
    state.selected_images = filtered[:state.output_config.wildcard_max]
    after = len(state.selected_images)
    state.enrichment_context = ctx

    score = ctx.get("coherence_score", 0)
    discarded = before - after
    print(f"✅ Content review complete (coherence: {score}/10, images: {after} kept, {discarded} discarded)")

    return state
