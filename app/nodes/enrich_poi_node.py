# app/nodes/enrich_poi_node.py
from app.state import AppState
from app.services.poi_enricher import fetch_pois


def enrich_poi_node(state: AppState) -> AppState:
    """Reichert den State mit Points of Interest an.

    Nutzt Overpass API zum Finden von POIs in der Nähe von Pause-Orten.
    Optional angereichert mit Wikipedia-Lead-Paragraphs.
    """
    print("📍 Searching for Points of Interest near pause locations...")

    if not state.gpx_pauses:
        print("⚠️ No pause data available — skipping POI enrichment")
        return state

    state.poi_list = fetch_pois(pauses=state.gpx_pauses)

    if state.poi_list:
        print(f"✅ Found {len(state.poi_list)} POIs along the route")
    else:
        print("⚠️ No POIs found — continuing without POI data")

    return state
