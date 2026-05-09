# app/nodes/review_content_node.py
import logging

from app.state import AppState
from app.services.content_reviewer import review_enrichment

logger = logging.getLogger(__name__)


def review_content_node(state: AppState) -> AppState:
    """Prüft angereicherte Inhalte auf Qualität und thematische Passung.

    Filtert zudem überzählige Bilder anhand der LLM-Qualitätsbewertung
    auf maximal wildcard_max (≥33% der oversampled Bilder werden verworfen).
    """
    logger.info("Running content quality review...")

    try:
        ctx = review_enrichment(
            weather=state.weather,
            poi_list=state.poi_list,
            selected_images=state.selected_images,
            gpx_stats=state.gpx_stats,
            notes=state.notes,
            model=state.model,
        )
    except Exception as e:
        logger.error("Content review failed: %s — skipping review", e)
        ctx = {"filtered_images": state.selected_images, "coherence_score": 0}

    # Auf wildcard_max kappen — die ≥33% Discard-Quote ist automatisch
    # erfüllt, da select_images ceil(N*1.5) liefert und hier auf N gekappt wird.
    filtered = ctx.get("filtered_images", state.selected_images)
    before = len(state.selected_images)
    state.selected_images = filtered[:state.output_config.wildcard_max]
    after = len(state.selected_images)
    state.enrichment_context = ctx

    score = ctx.get("coherence_score", 0)
    discarded = before - after
    logger.info("Content review complete (coherence: %s/10, images: %s kept, %s discarded)", score, after, discarded)

    return state
