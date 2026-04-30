# app/services/weather_enricher.py
"""Weather enrichment via Open-Meteo Historical Weather API.

Kostenlos, kein API-Key, keine Registrierung.
Ermittelt historisches Wetter für die GPX-Track-Koordinaten und den Zeitraum.
Schätzt die 0°C-Grenze aus Höhendaten und Temperatur (Lapse-Rate 6.5°C/km).
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

import requests

from app.services.gpx_analytics import TrackPoint
from app.state import DailyWeather, WeatherInfo


OPEN_METEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
LAPSE_RATE_C_PER_M = 0.0065  # Standard atmospheric lapse rate
MAX_COORDINATE_POINTS = 10
TRACK_POINT_SAMPLE_EVERY = 20


def _build_openmeteo_url(
    latitude: float,
    longitude: float,
    start_date: str,
    end_date: str,
) -> str:
    """Baut die Open-Meteo Archive API URL mit allen benötigten Parametern."""
    params = (
        f"latitude={latitude}"
        f"&longitude={longitude}"
        f"&start_date={start_date}"
        f"&end_date={end_date}"
        "&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,"
        "precipitation_hours,weather_code,wind_speed_10m_max,cloud_cover_mean"
        "&timezone=auto"
    )
    return f"{OPEN_METEO_ARCHIVE_URL}?{params}"


def _estimate_freezing_level(
    median_elevation: Optional[float],
    temperature_min: float,
) -> Optional[float]:
    """Schätzt die 0°C-Grenze aus Höhe und Temperatur (Lapse Rate).

    Formel: freezing_level ≈ elevation + (temperature / lapse_rate)
    Begrenzt auf 0–6000 m (sinnvoller Bereich in den Alpen).
    """
    if median_elevation is None or median_elevation <= 0:
        return None

    freezing = median_elevation + (temperature_min / LAPSE_RATE_C_PER_M)
    return max(0.0, min(6000.0, freezing))


def _aggregate_weather_results(
    daily_results: List[Dict[str, Any]],
    dates: List[str],
    median_elevation: Optional[float] = None,
) -> WeatherInfo:
    """Aggregiert mehrere Open-Meteo-Ergebnisse (verschiedene Koordinaten) zu einem WeatherInfo."""
    if not daily_results or not dates:
        return WeatherInfo(daily=[], summary="")

    num_days = len(dates)
    daily_entries: List[DailyWeather] = []

    for day_idx in range(num_days):
        temps_max = []
        temps_min = []
        precips = []
        precip_hours = []
        weather_codes = []
        winds = []
        clouds = []

        for result in daily_results:
            if day_idx < len(result.get("temperature_2m_max", [])):
                temps_max.append(result["temperature_2m_max"][day_idx])
                temps_min.append(result["temperature_2m_min"][day_idx])
                precips.append(result["precipitation_sum"][day_idx])
                precip_hours.append(result["precipitation_hours"][day_idx])
                weather_codes.append(result["weather_code"][day_idx])
                winds.append(result["wind_speed_10m_max"][day_idx])
                clouds.append(result["cloud_cover_mean"][day_idx])

        if not temps_max:
            continue

        # Median für Temperaturen, Max für Niederschlag
        sorted_tmax = sorted(temps_max)
        sorted_tmin = sorted(temps_min)
        n = len(sorted_tmax)
        median_tmax = sorted_tmax[n // 2]
        median_tmin = sorted_tmin[n // 2]

        freezing = _estimate_freezing_level(median_elevation, median_tmin)

        daily_entries.append(DailyWeather(
            date=dates[day_idx],
            temperature_max=median_tmax,
            temperature_min=median_tmin,
            precipitation_mm=max(precips),
            precipitation_hours=max(precip_hours),
            freezing_level_m=freezing,
            weather_code=max(set(weather_codes), key=weather_codes.count),
            wind_speed_kmh=max(winds),
            cloud_cover_pct=max(clouds),
        ))

    return WeatherInfo(daily=daily_entries)


def fetch_historical_weather(
    track_points: List[TrackPoint],
    pauses: List[dict],
) -> Optional[WeatherInfo]:
    """Holt historisches Wetter für den Track-Zeitraum und die Route.

    Args:
        track_points: Liste von TrackPoints mit lat, lon, elevation, time
        pauses: Liste von Pause-Dicts mit location.lat/lon und start_time/end_time

    Returns:
        WeatherInfo mit täglichen Wetterdaten oder None bei Fehler
    """
    # Zeitraum aus Track-Punkten extrahieren
    timed_points = [p for p in track_points if p.time is not None]
    if not timed_points:
        print("⚠️ Keine Zeitstempel in Track-Punkten — Wetter nicht abrufbar")
        return None

    start_time = timed_points[0].time
    end_time = timed_points[-1].time
    start_date = start_time.strftime("%Y-%m-%d")
    end_date = end_time.strftime("%Y-%m-%d")

    # Koordinaten-Punkte sammeln: jeden 20. Track-Punkt + alle Pause-Orte
    coords = set()

    for i, pt in enumerate(timed_points):
        if i % TRACK_POINT_SAMPLE_EVERY == 0 and pt.lat is not None and pt.lon is not None:
            coords.add((round(pt.lat, 2), round(pt.lon, 2)))

    for pause in pauses:
        loc = pause.get("location", {})
        lat, lon = loc.get("lat"), loc.get("lon")
        if lat is not None and lon is not None:
            coords.add((round(lat, 2), round(lon, 2)))

    if not coords:
        print("⚠️ Keine gültigen Koordinaten — Wetter nicht abrufbar")
        return None

    # Auf maximal N Punkte reduzieren
    coords = sorted(coords)[:MAX_COORDINATE_POINTS]

    # Mittlere Track-Höhe für Freezing-Level-Schätzung
    elevations = [pt.elevation for pt in timed_points
                  if pt.elevation is not None and pt.elevation > 0]
    median_elevation = sorted(elevations)[len(elevations) // 2] if elevations else None

    daily_data: List[Dict[str, Any]] = []

    for lat, lon in coords:
        url = _build_openmeteo_url(lat, lon, start_date, end_date)
        try:
            resp = requests.get(url, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                if "daily" in data:
                    daily_data.append(data["daily"])
            else:
                print(f"⚠️ Open-Meteo antwortete mit {resp.status_code} für ({lat}, {lon})")
        except Exception as e:
            print(f"⚠️ Open-Meteo nicht erreichbar für ({lat}, {lon}): {e}")
            continue

    if not daily_data:
        print("⚠️ Keine Wetterdaten von Open-Meteo erhalten")
        return None

    dates = daily_data[0].get("time", [])
    return _aggregate_weather_results(daily_data, dates, median_elevation)
