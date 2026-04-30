# app/nodes/enrich_weather_node.py
from app.state import AppState
from app.services.weather_enricher import fetch_historical_weather


def enrich_weather_node(state: AppState) -> AppState:
    """Reichert den State mit historischen Wetterdaten an.

    Nutzt Open-Meteo zum Abruf der Daten für den Track-Zeitraum.
    """
    print("☀️  Fetching historical weather data...")

    if not state.gpx_stats:
        print("⚠️ No GPX stats available — skipping weather enrichment")
        return state

    state.weather = fetch_historical_weather(
        track_points=state.gpx_stats.points,
        pauses=state.gpx_pauses,
    )

    if state.weather:
        print(f"✅ Weather data fetched: {len(state.weather.daily)} days from {state.weather.source}")
    else:
        print("⚠️ Weather enrichment failed — continuing without weather data")

    return state
