# app/nodes/enrich_poi_node.py
import logging

from app.state import AppState
from app.services.poi_enricher import fetch_pois

logger = logging.getLogger(__name__)


def enrich_poi_node(state: AppState) -> AppState:
    """Reichert den State mit Points of Interest an.

    Nutzt Overpass API zum Finden von POIs in der Nähe von Pause-Orten.
    Optional angereichert mit Wikipedia-Lead-Paragraphs.
    """
    logger.info("Searching for Points of Interest near pause locations...")

    if not state.gpx_pauses:
        logger.warning("No pause data available — skipping POI enrichment")
        return state

    try:
        state.poi_list = fetch_pois(pauses=state.gpx_pauses)
    except Exception as e:
        logger.error("POI enrichment failed: %s — continuing without POI data", e)
        state.poi_list = []

    if state.poi_list:
        logger.info("Found %s POIs along the route", len(state.poi_list))
    else:
        logger.warning("No POIs found — continuing without POI data")

    return state
