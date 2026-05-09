# app/nodes/enrich_weather_node.py
import logging

from app.state import AppState
from app.services.weather_enricher import fetch_historical_weather

logger = logging.getLogger(__name__)


def enrich_weather_node(state: AppState) -> AppState:
    """Reichert den State mit historischen Wetterdaten an.

    Nutzt Open-Meteo zum Abruf der Daten für den Track-Zeitraum.
    """
    logger.info("Fetching historical weather data...")

    if not state.gpx_stats:
        logger.warning("No GPX stats available — skipping weather enrichment")
        return state

    try:
        state.weather = fetch_historical_weather(
            track_points=state.gpx_stats.points,
            pauses=state.gpx_pauses,
        )
    except Exception as e:
        logger.error("Weather enrichment failed: %s — continuing without weather data", e)
        state.weather = None

    if state.weather:
        logger.info("Weather data fetched: %s days from %s", len(state.weather.daily), state.weather.source)
    else:
        logger.warning("Weather enrichment failed — continuing without weather data")

    return state
