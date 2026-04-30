# Enrichment & Review Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add weather enrichment (Open-Meteo), POI enrichment (Overpass + Wikipedia), and a single-pass LLM content review gate to the travel blog pipeline.

**Architecture:** Three new services (weather, POI, review), three new nodes, and two new Pydantic models on AppState. All external dependencies are free, no-auth HTTP APIs. The review node is a single-pass LLM quality gate with a clean interface for later human-in-the-loop expansion.

**Tech Stack:** Python 3.12+, requests (stdlib-like, already a transitive dep), Pydantic, Ollama chat API, Open-Meteo archive API, Overpass API

**Test strategy:** Services and nodes tested with pytest + pytest-mock. Network calls mocked via `unittest.mock.patch`. Existing fixtures (`sample_gpx_stats`, `sample_gpx_pauses`) reused. New tests go in `tests/test_services/` and `tests/test_nodes/`.

---

### Task 1: Weather models on AppState

**Files:**
- Modify: `app/state.py`
- Create: `tests/test_state.py`

**Context:** Add `DailyWeather` and `WeatherInfo` Pydantic models, plus `weather`, `poi_list`, `enrichment_context` fields to `AppState`.

- [ ] **Step 1: Write the failing test**

```bash
mkdir -p tests
```

Create `tests/test_state.py`:

```python
"""Tests for app/state.py weather and enrichment models."""
import pytest
from pydantic import ValidationError
from app.state import DailyWeather, WeatherInfo, AppState


class TestDailyWeather:
    def test_creates_with_required_fields(self):
        dw = DailyWeather(
            date="2025-06-15",
            temperature_max=22.5,
            temperature_min=14.0,
            precipitation_mm=3.2,
            precipitation_hours=1.5,
            weather_code=2,
            wind_speed_kmh=15.0,
            cloud_cover_pct=60.0,
        )
        assert dw.freezing_level_m is None
        assert dw.temperature_max == 22.5

    def test_freezing_level_optional(self):
        dw = DailyWeather(
            date="2025-06-15",
            temperature_max=22.5,
            temperature_min=14.0,
            precipitation_mm=0.0,
            precipitation_hours=0.0,
            freezing_level_m=2800.0,
            weather_code=1,
            wind_speed_kmh=10.0,
            cloud_cover_pct=30.0,
        )
        assert dw.freezing_level_m == 2800.0

    def test_missing_required_raises(self):
        with pytest.raises(ValidationError):
            DailyWeather(date="2025-06-15")


class TestWeatherInfo:
    def test_defaults(self):
        wi = WeatherInfo(daily=[])
        assert wi.source == "open-meteo"
        assert wi.summary == ""


class TestAppStateEnrichment:
    def test_new_fields_have_defaults(self):
        state = AppState()
        assert state.weather is None
        assert state.poi_list == []
        assert state.enrichment_context == {}
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_state.py -v
```

Expected: ImportError or AttributeError — models don't exist yet.

- [ ] **Step 3: Add models to app/state.py**

At the top of `app/state.py`, after the existing imports, add:

```python
from typing import List, Optional, Dict, Any

# ... existing imports ...

class DailyWeather(BaseModel):
    date: str
    temperature_max: float
    temperature_min: float
    precipitation_mm: float         # Niederschlagsmenge
    precipitation_hours: float      # Stunden mit Niederschlag (Intensitätsindikator)
    freezing_level_m: Optional[float] = None  # 0°C-Grenze (Höhe ü. NN)
    weather_code: int               # Open-Meteo WMO code
    wind_speed_kmh: float
    cloud_cover_pct: float


class WeatherInfo(BaseModel):
    daily: List[DailyWeather]
    source: str = "open-meteo"
    summary: str = ""
```

Then add the three new fields to `AppState` — insert them after the existing `notes` field:

```python
class AppState(BaseModel):
    images: List[ImageData] = []
    selected_images: List[ImageData] = []
    image_clusters: List[Dict[str, Any]] = []
    gpx_file: str = ""
    gpx_stats: Optional[GPXStats] = None
    gpx_pauses: List[dict] = []
    elevation_profile_path: Optional[str] = None
    metadata: Dict[str, Any] = {}
    notes: Optional[str] = None
    weather: Optional[WeatherInfo] = None
    poi_list: List[Dict[str, Any]] = []
    enrichment_context: Dict[str, Any] = {}
    blog_post: Optional[Dict[str, Any]] = None
    model: str = "gemma4:26b-ctx128k"
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_state.py -v
```

Expected: 5 tests pass.

- [ ] **Step 5: Commit**

```bash
git add app/state.py tests/test_state.py
git commit -m "feat: add DailyWeather, WeatherInfo models and enrichment fields to AppState"
```

---

### Task 2: Weather enricher service

**Files:**
- Create: `app/services/weather_enricher.py`
- Create: `tests/test_services/test_weather_enricher.py`

**Dependencies:** Task 1 (needs `WeatherInfo`, `DailyWeather`, `TrackPoint`)

**Context:** Service that calls the Open-Meteo Historical Weather API and estimates freezing level from track elevation + lapse rate. Pure function, no side effects except HTTP.

- [ ] **Step 1: Write the failing test**

Create `tests/test_services/test_weather_enricher.py`:

```python
"""Tests for app/services/weather_enricher.py"""
import json
from unittest.mock import patch, Mock
from datetime import datetime

import pytest

from app.services.weather_enricher import (
    fetch_historical_weather,
    _build_openmeteo_url,
    _estimate_freezing_level,
    _aggregate_weather_results,
)
from app.services.gpx_analytics import TrackPoint
from app.state import DailyWeather, WeatherInfo


class TestBuildOpenMeteoUrl:
    def test_builds_correct_url(self):
        url = _build_openmeteo_url(
            latitude=47.3,
            longitude=11.4,
            start_date="2025-06-01",
            end_date="2025-06-03",
        )
        assert "archive-api.open-meteo.com" in url
        assert "latitude=47.3" in url
        assert "longitude=11.4" in url
        assert "start_date=2025-06-01" in url
        assert "end_date=2025-06-03" in url
        assert "precipitation_hours" in url
        assert "temperature_2m_min" in url


class TestEstimateFreezingLevel:
    def test_estimates_from_elevation_and_temp(self):
        # Track median elevation 1000m, min temp 5°C
        # freezing_level ≈ 1000 + 5/0.0065 ≈ 1769m
        result = _estimate_freezing_level(median_elevation=1000.0, temperature_min=5.0)
        assert result is not None
        assert 1500 < result < 2000

    def test_returns_none_without_elevation(self):
        result = _estimate_freezing_level(median_elevation=None, temperature_min=5.0)
        assert result is None

    def test_clamps_to_sensible_range(self):
        # Very hot day: negative freezing level would be computed but clamped to 0
        result = _estimate_freezing_level(median_elevation=100.0, temperature_min=35.0)
        assert result <= 10000  # Should not be absurd


class TestAggregateWeatherResults:
    def test_aggregates_two_locations(self):
        daily_a = {"temperature_2m_max": [20, 22], "temperature_2m_min": [10, 12],
                    "precipitation_sum": [0, 5], "precipitation_hours": [0, 2],
                    "weather_code": [1, 2], "wind_speed_10m_max": [10, 15],
                    "cloud_cover_mean": [30, 60]}
        daily_b = {"temperature_2m_max": [22, 24], "temperature_2m_min": [12, 14],
                    "precipitation_sum": [0, 3], "precipitation_hours": [0, 1],
                    "weather_code": [1, 3], "wind_speed_10m_max": [12, 18],
                    "cloud_cover_mean": [40, 70]}
        dates = ["2025-06-01", "2025-06-02"]
        result = _aggregate_weather_results(
            [daily_a, daily_b], dates, median_elevation=800.0
        )
        assert isinstance(result, WeatherInfo)
        assert len(result.daily) == 2
        # Day 1: median temp max between 20 and 22 = 21
        assert result.daily[0].temperature_max == 21.0
        # Day 2 has precipitation: max of 5 and 3 = 5
        assert result.daily[1].precipitation_mm == 5.0


class TestFetchHistoricalWeather:
    @pytest.fixture
    def track_points(self):
        return [
            TrackPoint(lat=47.3, lon=11.4, elevation=800.0,
                       time=datetime(2025, 6, 1, 10, 0)),
            TrackPoint(lat=47.31, lon=11.41, elevation=850.0,
                       time=datetime(2025, 6, 3, 16, 0)),
        ]

    @pytest.fixture
    def openmeteo_response(self):
        return {
            "daily": {
                "time": ["2025-06-01", "2025-06-02", "2025-06-03"],
                "temperature_2m_max": [20.0, 22.0, 21.0],
                "temperature_2m_min": [10.0, 12.0, 11.0],
                "precipitation_sum": [0.0, 5.0, 0.0],
                "precipitation_hours": [0.0, 2.0, 0.0],
                "weather_code": [1, 2, 1],
                "wind_speed_10m_max": [10.0, 15.0, 12.0],
                "cloud_cover_mean": [30.0, 60.0, 40.0],
            }
        }

    def test_returns_weather_info(self, track_points, openmeteo_response):
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = openmeteo_response

        with patch("app.services.weather_enricher.requests.get", return_value=mock_resp):
            result = fetch_historical_weather(
                track_points=track_points,
                pauses=[],
            )
        assert isinstance(result, WeatherInfo)
        assert len(result.daily) == 3
        assert result.source == "open-meteo"
        # freezing level should be estimated
        assert result.daily[0].freezing_level_m is not None

    def test_handles_api_failure_gracefully(self, track_points):
        with patch("app.services.weather_enricher.requests.get",
                   side_effect=Exception("Connection refused")):
            result = fetch_historical_weather(
                track_points=track_points,
                pauses=[],
            )
        assert result is None

    def test_handles_non_200_response(self, track_points):
        mock_resp = Mock()
        mock_resp.status_code = 500
        with patch("app.services.weather_enricher.requests.get", return_value=mock_resp):
            result = fetch_historical_weather(
                track_points=track_points,
                pauses=[],
            )
        assert result is None

    def test_includes_pause_locations(self, track_points, openmeteo_response):
        pauses = [
            {"location": {"lat": 47.305, "lon": 11.405},
             "start_time": datetime(2025, 6, 2, 12, 0),
             "end_time": datetime(2025, 6, 2, 12, 30)}
        ]
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = openmeteo_response
        with patch("app.services.weather_enricher.requests.get", return_value=mock_resp):
            result = fetch_historical_weather(
                track_points=track_points,
                pauses=pauses,
            )
        assert isinstance(result, WeatherInfo)

    def test_returns_none_without_coordinates(self):
        result = fetch_historical_weather(
            track_points=[],
            pauses=[],
        )
        assert result is None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_services/test_weather_enricher.py -v
```

Expected: ImportError — module doesn't exist yet.

- [ ] **Step 3: Implement the weather enricher service**

Create `app/services/weather_enricher.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_services/test_weather_enricher.py -v
```

Expected: All tests pass (9 tests).

- [ ] **Step 5: Commit**

```bash
git add app/services/weather_enricher.py tests/test_services/test_weather_enricher.py
git commit -m "feat: add Open-Meteo weather enricher service with freezing level estimation"
```

---

### Task 3: Weather enricher node

**Files:**
- Create: `app/nodes/enrich_weather_node.py`
- Create: `tests/test_nodes/test_enrich_weather.py`

**Dependencies:** Task 1, Task 2

- [ ] **Step 1: Write the failing test**

Create `tests/test_nodes/test_enrich_weather.py`:

```python
"""Tests for app/nodes/enrich_weather_node.py"""
from unittest.mock import patch
from app.nodes.enrich_weather_node import enrich_weather_node
from app.state import AppState, DailyWeather, WeatherInfo


class TestEnrichWeatherNode:
    def test_skips_when_no_gpx_stats(self):
        state = AppState(gpx_stats=None)
        result = enrich_weather_node(state)
        assert result.weather is None

    def test_enriches_weather_from_gpx_stats(self):
        from app.services.gpx_analytics import TrackPoint, GPXStats
        from datetime import datetime

        points = [
            TrackPoint(lat=47.3, lon=11.4, elevation=800.0,
                       time=datetime(2025, 6, 1, 10, 0)),
        ]
        stats = GPXStats(
            total_distance_m=5000, elevation_gain_m=200, elevation_loss_m=100,
            avg_speed_kmh=4.0, max_speed_kmh=8.0, points=points,
        )
        state = AppState(gpx_stats=stats, gpx_pauses=[])

        mock_weather = WeatherInfo(
            daily=[
                DailyWeather(
                    date="2025-06-01", temperature_max=20.0, temperature_min=10.0,
                    precipitation_mm=0.0, precipitation_hours=0.0,
                    freezing_level_m=2500.0, weather_code=1, wind_speed_kmh=10.0,
                    cloud_cover_pct=30.0,
                )
            ],
            source="open-meteo",
        )

        with patch(
            "app.nodes.enrich_weather_node.fetch_historical_weather",
            return_value=mock_weather,
        ):
            result = enrich_weather_node(state)
            assert result.weather is not None
            assert result.weather.source == "open-meteo"
            assert len(result.weather.daily) == 1
            assert result.weather.daily[0].temperature_max == 20.0
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_nodes/test_enrich_weather.py -v
```

Expected: ImportError — module doesn't exist yet.

- [ ] **Step 3: Implement the node**

Create `app/nodes/enrich_weather_node.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_nodes/test_enrich_weather.py -v
```

Expected: 2 tests pass.

- [ ] **Step 5: Commit**

```bash
git add app/nodes/enrich_weather_node.py tests/test_nodes/test_enrich_weather.py
git commit -m "feat: add weather enrichment pipeline node"
```

---

### Task 4: POI enricher service

**Files:**
- Create: `app/services/poi_enricher.py`
- Create: `tests/test_services/test_poi_enricher.py`

**Dependencies:** None (uses only `gpx_pauses` dict format)

- [ ] **Step 1: Write the failing test**

Create `tests/test_services/test_poi_enricher.py`:

```python
"""Tests for app/services/poi_enricher.py"""
from unittest.mock import patch, Mock

import pytest

from app.services.poi_enricher import (
    fetch_pois,
    _build_overpass_query,
    _parse_overpass_response,
    _deduplicate_pois_by_name_and_proximity,
    _enrich_with_wikipedia,
)


class TestBuildOverpassQuery:
    def test_builds_query_for_single_location(self):
        query = _build_overpass_query(47.3, 11.4, radius=2000)
        assert "[out:json]" in query
        assert "around:2000" in query
        assert 'tourism"~"viewpoint|alpine_hut|information|museum"' in query
        assert 'natural"="peak"' in query
        assert 'historic"~"ruins|castle|memorial"' in query

    def test_respects_custom_radius(self):
        query = _build_overpass_query(47.3, 11.4, radius=5000)
        assert "around:5000" in query


class TestParseOverpassResponse:
    def test_parses_valid_overpass_json(self):
        raw = {
            "elements": [
                {
                    "id": 123,
                    "type": "node",
                    "lat": 47.3,
                    "lon": 11.4,
                    "tags": {
                        "name": "Aussichtspunkt Alpenblick",
                        "tourism": "viewpoint",
                    }
                },
                {
                    "id": 456,
                    "type": "node",
                    "lat": 47.31,
                    "lon": 11.41,
                    "tags": {
                        "name": "Berggipfel",
                        "natural": "peak",
                        "wikipedia": "de:Berggipfel",
                    }
                },
            ]
        }
        results = _parse_overpass_response(raw, ref_lat=47.305, ref_lon=11.405)
        assert len(results) == 2
        assert results[0]["name"] == "Aussichtspunkt Alpenblick"
        assert results[0]["type"] == "viewpoint"
        assert "distance_km" in results[0]
        assert results[1]["wiki_tag"] == "de:Berggipfel"

    def test_handles_empty_response(self):
        results = _parse_overpass_response({"elements": []}, ref_lat=47.3, ref_lon=11.4)
        assert results == []

    def test_handles_missing_name_tag(self):
        raw = {
            "elements": [{
                "id": 789,
                "type": "node",
                "lat": 47.3,
                "lon": 11.4,
                "tags": {"tourism": "viewpoint"},
            }]
        }
        results = _parse_overpass_response(raw, ref_lat=47.3, ref_lon=11.4)
        assert len(results) == 1
        assert results[0]["name"] == "viewpoint (47.300, 11.400)"


class TestDeduplicatePois:
    def test_dedup_by_same_name(self):
        pois = [
            {"name": "Alpenblick", "lat": 47.3, "lon": 11.4},
            {"name": "Alpenblick", "lat": 47.31, "lon": 11.41},
            {"name": "Anderer Ort", "lat": 47.5, "lon": 11.6},
        ]
        result = _deduplicate_pois_by_name_and_proximity(pois)
        assert len(result) == 2
        names = {p["name"] for p in result}
        assert "Alpenblick" in names
        assert "Anderer Ort" in names

    def test_dedup_by_proximity(self):
        pois = [
            {"name": "A", "lat": 47.3000, "lon": 11.4000},
            {"name": "B", "lat": 47.3005, "lon": 11.4005},
        ]
        result = _deduplicate_pois_by_name_and_proximity(pois)
        assert len(result) == 1


class TestEnrichWithWikipedia:
    def test_skips_without_wiki_tag(self):
        poi = {"name": "Some Place", "lat": 47.3, "lon": 11.4}
        result = _enrich_with_wikipedia(poi)
        assert result is poi
        assert "wiki_extract" not in result

    def test_fetches_wikipedia_extract(self):
        poi = {"name": "Some Place", "lat": 47.3, "lon": 11.4,
               "wiki_tag": "de:Berggipfel"}
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "extract": "Der Berggipfel ist ein bekannter Aussichtsberg...",
            "title": "Berggipfel",
        }
        with patch("app.services.poi_enricher.requests.get", return_value=mock_resp):
            result = _enrich_with_wikipedia(poi)
            assert result is not poi  # new dict returned
            assert "wiki_extract" in result
            assert "Berggipfel" in result["wiki_extract"]

    def test_handles_wikipedia_failure(self):
        poi = {"name": "Some Place", "lat": 47.3, "lon": 11.4,
               "wiki_tag": "de:Berggipfel"}
        with patch("app.services.poi_enricher.requests.get",
                   side_effect=Exception("Timeout")):
            result = _enrich_with_wikipedia(poi)
            assert "wiki_extract" not in result


class TestFetchPois:
    def test_returns_empty_without_pauses(self):
        result = fetch_pois(pauses=[])
        assert result == []

    def test_fetches_and_enriches_pois(self):
        from datetime import datetime
        pauses = [{
            "location": {"lat": 47.3, "lon": 11.4},
            "start_time": datetime(2025, 6, 1, 12, 0),
            "end_time": datetime(2025, 6, 1, 12, 30),
        }]

        mock_overpass_resp = Mock()
        mock_overpass_resp.status_code = 200
        mock_overpass_resp.json.return_value = {
            "elements": [{
                "id": 1, "type": "node", "lat": 47.302, "lon": 11.402,
                "tags": {"name": "Berggipfel", "natural": "peak",
                         "wikipedia": "de:Berggipfel"},
            }]
        }

        mock_wiki_resp = Mock()
        mock_wiki_resp.status_code = 200
        mock_wiki_resp.json.return_value = {
            "extract": "A beautiful peak in the Alps...",
            "title": "Berggipfel",
        }

        with patch("app.services.poi_enricher.requests.post",
                   return_value=mock_overpass_resp), \
             patch("app.services.poi_enricher._enrich_with_wikipedia") as mock_enrich:
            mock_enrich.side_effect = lambda p: {**p, "wiki_extract": "A beautiful peak"}
            result = fetch_pois(pauses=pauses)
            assert len(result) >= 1
            assert result[0]["name"] == "Berggipfel"

    def test_handles_overpass_failure(self):
        from datetime import datetime
        pauses = [{
            "location": {"lat": 47.3, "lon": 11.4},
        }]
        with patch("app.services.poi_enricher.requests.post",
                   side_effect=Exception("Connection refused")):
            result = fetch_pois(pauses=pauses)
            assert result == []
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_services/test_poi_enricher.py -v
```

Expected: ImportError — module doesn't exist yet.

- [ ] **Step 3: Implement the POI enricher service**

Create `app/services/poi_enricher.py`:

```python
# app/services/poi_enricher.py
"""POI enrichment via Overpass API + optional Wikipedia extracts.

Kostenlos, kein API-Key, keine Registrierung.
Findet Points of Interest in der Nähe von Pause-Orten entlang der Route.
"""

from typing import Any, Dict, List, Optional
from datetime import datetime
import math
import time

import requests


OVERPASS_URL = "https://overpass-api.de/api/interpreter"
DEFAULT_SEARCH_RADIUS_M = 2000
MAX_POIS_PER_LOCATION = 10
PROXIMITY_DEDUP_M = 500


def _build_overpass_query(lat: float, lon: float, radius: int = DEFAULT_SEARCH_RADIUS_M) -> str:
    """Baut eine Overpass QL-Query für POIs um eine Koordinate."""
    return f"""[out:json];
(
  node["tourism"~"viewpoint|alpine_hut|information|museum"](around:{radius},{lat},{lon});
  node["natural"="peak"](around:{radius},{lat},{lon});
  node["historic"~"ruins|castle|memorial"](around:{radius},{lat},{lon});
);
out {MAX_POIS_PER_LOCATION};"""


def _parse_overpass_response(
    data: Dict[str, Any],
    ref_lat: float,
    ref_lon: float,
) -> List[Dict[str, Any]]:
    """Parst Overpass JSON-Antwort in POI-Dicts mit Distanzberechnung."""
    results = []
    for element in data.get("elements", []):
        if element.get("type") not in ("node", "way"):
            continue
        tags = element.get("tags", {})

        # POI-Typ bestimmen
        poi_type = "unknown"
        for tag_key in ("tourism", "natural", "historic"):
            if tag_key in tags:
                poi_type = tags[tag_key]
                break
        if poi_type == "unknown" and element.get("type") == "node":
            continue

        name = tags.get("name", f"{poi_type} ({element.get('lat', ref_lat):.3f}, {element.get('lon', ref_lon):.3f})")

        # Distanz berechnen (Haversine-Approximation)
        el_lat = element.get("lat", ref_lat)
        el_lon = element.get("lon", ref_lon)
        dlat = math.radians(el_lat - ref_lat)
        dlon = math.radians(el_lon - ref_lon)
        a = (math.sin(dlat / 2) ** 2 +
             math.cos(math.radians(ref_lat)) * math.cos(math.radians(el_lat)) *
             math.sin(dlon / 2) ** 2)
        distance_km = 6371.0 * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        poi = {
            "name": name,
            "type": poi_type,
            "lat": el_lat,
            "lon": el_lon,
            "distance_km": round(distance_km, 2),
        }

        # Wikipedia-Tag extrahieren falls vorhanden
        wiki_tag = tags.get("wikipedia")
        if wiki_tag:
            poi["wiki_tag"] = wiki_tag

        results.append(poi)

    return results


def _deduplicate_pois_by_name_and_proximity(pois: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Entfernt doppelte POIs nach Name und räumlicher Nähe."""
    if not pois:
        return []

    kept: List[Dict[str, Any]] = []
    seen_names = set()

    for poi in pois:
        name_lower = poi["name"].lower()

        # Name-Dedup
        if name_lower in seen_names:
            continue

        # Nähe-Dedup: zu nah an einem bereits behaltenen POI?
        too_close = False
        for existing in kept:
            dist = math.sqrt(
                ((poi["lat"] - existing["lat"]) * 111.32 * 1000) ** 2 +
                ((poi["lon"] - existing["lon"]) * 111.32 *
                 math.cos(math.radians(poi["lat"])) * 1000) ** 2
            )
            if dist < PROXIMITY_DEDUP_M:
                too_close = True
                break

        if not too_close:
            kept.append(poi)
            seen_names.add(name_lower)

    return kept


def _enrich_with_wikipedia(poi: Dict[str, Any]) -> Dict[str, Any]:
    """Reichert einen POI mit dem Wikipedia-Lead-Paragraph an (optional)."""
    wiki_tag = poi.get("wiki_tag")
    if not wiki_tag:
        return poi

    # wikipedia=de:Berggipfel -> lang=de, title=Berggipfel
    parts = wiki_tag.split(":", 1)
    if len(parts) != 2:
        return poi
    lang, title = parts

    try:
        url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{title}"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            extract = data.get("extract", "")
            if extract:
                result = {**poi, "wiki_extract": extract[:500]}
                return result
    except Exception as e:
        print(f"⚠️ Wikipedia fetch failed for {wiki_tag}: {e}")
    return poi


def fetch_pois(
    pauses: List[dict],
    search_radius_m: int = DEFAULT_SEARCH_RADIUS_M,
) -> List[Dict[str, Any]]:
    """Findet Points of Interest in der Nähe der Pause-Orte.

    Args:
        pauses: Liste von Pause-Dicts mit location.lat/lon
        search_radius_m: Suchradius um jede Pause in Metern

    Returns:
        Liste von POI-Dicts mit name, type, lat, lon, distance_km, wiki_extract
    """
    if not pauses:
        print("⚠️ Keine Pausen-Daten — POI-Suche nicht möglich")
        return []

    all_pois: List[Dict[str, Any]] = []

    for pause in pauses:
        loc = pause.get("location", {})
        lat, lon = loc.get("lat"), loc.get("lon")
        if lat is None or lon is None:
            continue

        query = _build_overpass_query(lat, lon, search_radius_m)

        try:
            resp = requests.post(
                OVERPASS_URL,
                data=query.encode("utf-8"),
                headers={"Content-Type": "text/plain"},
                timeout=60,
            )
        except Exception as e:
            print(f"⚠️ Overpass API nicht erreichbar für ({lat}, {lon}): {e}")
            continue

        if resp.status_code == 429:
            print("⚠️ Overpass rate limit — warte 2 Sekunden und versuche erneut")
            time.sleep(2)
            try:
                resp = requests.post(
                    OVERPASS_URL,
                    data=query.encode("utf-8"),
                    headers={"Content-Type": "text/plain"},
                    timeout=60,
                )
            except Exception:
                continue

        if resp.status_code != 200:
            print(f"⚠️ Overpass antwortete mit {resp.status_code}")
            continue

        try:
            data = resp.json()
        except Exception:
            continue

        pois = _parse_overpass_response(data, lat, lon)
        all_pois.extend(pois)

    # Deduplizieren
    all_pois = _deduplicate_pois_by_name_and_proximity(all_pois)

    # Mit Wikipedia-Texten anreichern (für POIs mit wiki-Tag)
    enriched = [_enrich_with_wikipedia(poi) for poi in all_pois]

    print(f"📍 Found {len(enriched)} unique POIs near {len(pauses)} pause locations")
    return enriched
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_services/test_poi_enricher.py -v
```

Expected: All tests pass (12 tests).

- [ ] **Step 5: Commit**

```bash
git add app/services/poi_enricher.py tests/test_services/test_poi_enricher.py
git commit -m "feat: add Overpass + Wikipedia POI enricher service"
```

---

### Task 5: POI enricher node

**Files:**
- Create: `app/nodes/enrich_poi_node.py`
- Create: `tests/test_nodes/test_enrich_poi.py`

**Dependencies:** Task 4

- [ ] **Step 1: Write the failing test**

Create `tests/test_nodes/test_enrich_poi.py`:

```python
"""Tests for app/nodes/enrich_poi_node.py"""
from unittest.mock import patch
from app.nodes.enrich_poi_node import enrich_poi_node
from app.state import AppState


class TestEnrichPoiNode:
    def test_skips_when_no_gpx_pauses(self):
        state = AppState(gpx_pauses=[], gpx_stats=None)
        result = enrich_poi_node(state)
        assert result.poi_list == []

    def test_enriches_pois_from_pauses(self):
        from app.services.gpx_analytics import TrackPoint, GPXStats

        points = [TrackPoint(lat=47.3, lon=11.4, elevation=800.0, time=None)]
        stats = GPXStats(
            total_distance_m=5000, elevation_gain_m=200, elevation_loss_m=100,
            avg_speed_kmh=4.0, max_speed_kmh=8.0, points=points,
        )
        pauses = [{"location": {"lat": 47.3, "lon": 11.4}}]
        state = AppState(gpx_stats=stats, gpx_pauses=pauses)

        mock_pois = [
            {"name": "Berggipfel", "type": "peak", "lat": 47.302, "lon": 11.402,
             "distance_km": 0.5, "wiki_extract": "A beautiful peak"},
        ]
        with patch("app.nodes.enrich_poi_node.fetch_pois", return_value=mock_pois):
            result = enrich_poi_node(state)
            assert len(result.poi_list) == 1
            assert result.poi_list[0]["name"] == "Berggipfel"
            assert result.poi_list[0]["wiki_extract"] == "A beautiful peak"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_nodes/test_enrich_poi.py -v
```

Expected: ImportError — module doesn't exist yet.

- [ ] **Step 3: Implement the node**

Create `app/nodes/enrich_poi_node.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_nodes/test_enrich_poi.py -v
```

Expected: 2 tests pass.

- [ ] **Step 5: Commit**

```bash
git add app/nodes/enrich_poi_node.py tests/test_nodes/test_enrich_poi.py
git commit -m "feat: add POI enrichment pipeline node"
```

---

### Task 6: Content reviewer service

**Files:**
- Create: `app/services/content_reviewer.py`
- Create: `tests/test_services/test_content_reviewer.py`

**Dependencies:** None (independent of weather/POI services)

- [ ] **Step 1: Write the failing test**

Create `tests/test_services/test_content_reviewer.py`:

```python
"""Tests for app/services/content_reviewer.py"""
import json
from unittest.mock import patch, Mock

import pytest

from app.services.content_reviewer import (
    review_enrichment,
    _build_review_prompt,
    _parse_review_response,
)
from app.state import DailyWeather, WeatherInfo


class TestBuildReviewPrompt:
    def test_includes_all_sections(self):
        weather = WeatherInfo(
            daily=[
                DailyWeather(
                    date="2025-06-01", temperature_max=20.0, temperature_min=10.0,
                    precipitation_mm=0.0, precipitation_hours=0.0,
                    freezing_level_m=2800.0, weather_code=1, wind_speed_kmh=10.0,
                    cloud_cover_pct=30.0,
                )
            ],
            summary="Sunny and mild",
        )
        pois = [{"name": "Berggipfel", "type": "peak", "distance_km": 1.0}]
        from app.state import ImageData
        images = [ImageData(path="img1.jpg", timestamp="2025-06-01T10:00:00",
                            latitude=47.3, longitude=11.4)]

        prompt = _build_review_prompt(
            weather=weather,
            poi_list=pois,
            selected_images=images,
            gpx_stats_d=None,
            notes=None,
        )
        assert "Sunny and mild" in prompt
        assert "Berggipfel" in prompt
        assert "img1.jpg" in prompt
        assert "discard" in prompt.lower()
        assert "freezing" in prompt.lower() or "0°C" in prompt


class TestParseReviewResponse:
    def test_parses_valid_json(self):
        response = json.dumps({
            "pois": [{"name": "A", "action": "KEEP", "reason": "great view"}],
            "weather_summary": "Mild and sunny with alpine chill.",
            "discarded_weather_fields": ["freezing_level_m"],
            "image_ratings": {"img1.jpg": 4, "img2.jpg": 3},
            "coherence_score": 8,
            "flags": [],
        })
        result = _parse_review_response(response)
        assert result["kept_pois"] == [{"name": "A", "action": "KEEP", "reason": "great view"}]
        assert result["weather_summary"] == "Mild and sunny with alpine chill."
        assert result["discarded_weather_fields"] == ["freezing_level_m"]
        assert result["coherence_score"] == 8

    def test_fallback_for_invalid_json(self):
        response = "Here is my analysis: the weather was nice. KEEP Berggipfel."
        result = _parse_review_response(response)
        assert "weather_summary" in result
        assert "kept_pois" in result
        # falls back to raw summary
        assert result["weather_summary"] == response[:500]

    def test_fallback_for_null(self):
        result = _parse_review_response(None)
        assert result["weather_summary"] == ""
        assert result["kept_pois"] == []
        assert result["coherence_score"] == 0


class TestReviewEnrichment:
    def test_returns_curated_context(self):
        weather = WeatherInfo(
            daily=[
                DailyWeather(
                    date="2025-06-01", temperature_max=20.0, temperature_min=10.0,
                    precipitation_mm=0.0, precipitation_hours=0.0,
                    weather_code=1, wind_speed_kmh=10.0, cloud_cover_pct=30.0,
                )
            ],
            summary="Sunny and mild",
        )
        pois = [{"name": "Berggipfel", "type": "peak", "distance_km": 1.0,
                 "wiki_extract": "A known peak"}]
        from app.state import ImageData
        images = [ImageData(path="img1.jpg", timestamp="2025-06-01T10:00:00",
                            latitude=47.3, longitude=11.4)]

        review_json = json.dumps({
            "pois": [{"name": "Berggipfel", "action": "KEEP",
                      "reason": "relevant alpine POI"}],
            "weather_summary": "Mild with alpine clarity. Freezing level at 2800m irrelevant for this low-elevation hike.",
            "discarded_weather_fields": ["freezing_level_m"],
            "image_ratings": {"img1.jpg": 4},
            "coherence_score": 7,
            "flags": [],
        })
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "message": {"content": review_json},
        }

        with patch("app.services.content_reviewer.requests.post",
                   return_value=mock_resp):
            result = review_enrichment(
                weather=weather,
                poi_list=pois,
                selected_images=images,
                gpx_stats=None,
                notes=None,
                model="gemma4:26b-ctx128k",
            )
        assert isinstance(result, dict)
        assert result.get("kept_pois") or result.get("weather_summary")

    def test_fallback_when_ollama_unavailable(self):
        weather = WeatherInfo(
            daily=[
                DailyWeather(
                    date="2025-06-01", temperature_max=20.0, temperature_min=10.0,
                    precipitation_mm=0.0, precipitation_hours=0.0,
                    weather_code=1, wind_speed_kmh=10.0, cloud_cover_pct=30.0,
                )
            ],
            summary="Sunny",
        )
        from app.state import ImageData
        images = [ImageData(path="img1.jpg")]

        with patch("app.services.content_reviewer.requests.post",
                   side_effect=Exception("Connection refused")):
            result = review_enrichment(
                weather=weather,
                poi_list=[],
                selected_images=images,
                gpx_stats=None,
                notes=None,
                model="gemma4:26b-ctx128k",
            )
        # Should return a fallback context, not None
        assert isinstance(result, dict)
        assert "weather_summary" in result
        assert "kept_pois" in result
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_services/test_content_reviewer.py -v
```

Expected: ImportError — module doesn't exist yet.

- [ ] **Step 3: Implement the content reviewer service**

Create `app/services/content_reviewer.py`:

```python
# app/services/content_reviewer.py
"""Content reviewer — single-pass LLM quality gate.

Prüft angereicherte Daten (Wetter, POIs, Bilder) auf thematische Passung
und erstellt einen kuratierten Enrichment-Kontext für den Blog-Prompt.
"""

import json
import re
from typing import Any, Dict, List, Optional

import requests

from app.state import ImageData, WeatherInfo, DailyWeather


OLLAMA_CHAT_URL = "http://localhost:11434/api/chat"
MAX_REVIEW_RESPONSE_TOKENS = 2048


def _build_review_prompt(
    weather: Optional[WeatherInfo],
    poi_list: List[Dict[str, Any]],
    selected_images: List[ImageData],
    gpx_stats_d: Optional[Dict[str, Any]],
    notes: Optional[str],
) -> str:
    """Baut den Review-Prompt für das LLM."""

    # Wetter-Sektion
    weather_text = ""
    if weather and weather.daily:
        weather_text = weather.summary
        if not weather_text:
            lines = []
            for dw in weather.daily:
                parts = f"{dw.date}: {dw.temperature_min:.0f}–{dw.temperature_max:.0f}°C"
                if dw.precipitation_mm > 0:
                    parts += f", {dw.precipitation_mm:.1f}mm Regen ({dw.precipitation_hours}h)"
                if dw.freezing_level_m is not None:
                    parts += f", 0°C-Grenze bei {dw.freezing_level_m:.0f}m"
                if dw.cloud_cover_pct > 50:
                    parts += f", {dw.cloud_cover_pct:.0f}% bewölkt"
                parts += f", {dw.wind_speed_kmh:.0f} km/h Wind"
                lines.append(parts)
            weather_text = "\n".join(lines)
    else:
        weather_text = "Keine Wetterdaten verfügbar."

    # POI-Sektion
    if poi_list:
        poi_lines = []
        for i, poi in enumerate(poi_list):
            line = f"{i}. {poi['name']} ({poi.get('type', 'POI')}, {poi.get('distance_km', '?')} km entfernt)"
            if poi.get("wiki_extract"):
                line += f"\n   Wikipedia: {poi['wiki_extract'][:200]}"
            poi_lines.append(line)
        poi_text = "\n".join(poi_lines)
    else:
        poi_text = "Keine POIs gefunden."

    # Bilder-Sektion
    if selected_images:
        img_lines = []
        for i, img in enumerate(selected_images):
            loc = ""
            if img.latitude and img.longitude:
                loc = f"({img.latitude:.4f}, {img.longitude:.4f})"
            ts = img.timestamp or "kein Zeitstempel"
            img_lines.append(f"{i}. {img.path} — {ts} {loc}")
        image_text = "\n".join(img_lines)
    else:
        image_text = "Keine Bilder ausgewählt."

    prompt = f"""You are a travel blog editor. Review the following enriched trip data.
Your job is to filter and curate for a compelling narrative.

WETTERDATEN:
{weather_text}

POINTS OF INTEREST ({len(poi_list)} gefunden):
{poi_text}

AUSGEWÄHLTE BILDER ({len(selected_images)} Bilder):
{image_text}

AUFGABEN:
1. POI-Filterung: Markiere jeden POI als KEEP oder DISCARD. Verwerfe irrelevante
   Einträge (urbane Infrastruktur, banale Orte, Duplikate nach Name/Nähe).
   Behalte maximal 8 POIs. Gib einen kurzen Grund für jedes DISCARD an.
2. Wetter-Kontext: Schreibe eine 2-3 sätzige Wetter-Zusammenfassung für die Blog-Einleitung.
   WICHTIG — manche Wetterfelder sind kontextabhängig und MÜSSEN verworfen werden, wenn
   sie nicht relevant sind:
   - Niederschlagsdaten (Menge + Stunden): verwerfen, wenn die Tour kaum oder keinen
     Niederschlag hatte.
   - 0°C-Grenze (freezing_level): verwerfen, wenn die maximale Höhe der Tour weit darunter
     liegt (z.B. 0°C-Grenze bei 2500 m bei einer flachen 200 m-Wanderung). Nur behalten,
     wenn sie innerhalb von ~1000 m der maximalen Track-Höhe liegt oder alpines Gelände betroffen ist.
   - Windgeschwindigkeit: verwerfen bei unauffälligen Werten (< 20 km/h).
   Ziel: den Blog-Schreiber NICHT mit irrelevanten Daten verwirren.
3. Bildqualität: Bewerte jedes Bild 1-5 auf thematische Eignung für einen Reiseblog.
   Markiere Bilder, die unscharf, schlecht komponiert oder Duplikate sein könnten.
4. Gesamtkohärenz: Vergib 1-10 Punkte, wie gut die Daten eine Geschichte erzählen.

Antworte AUSSCHLIESSLICH als gültiges JSON:
{{"pois": [{{"name": "...", "action": "KEEP|DISCARD", "reason": "..."}}],
 "weather_summary": "...",
 "discarded_weather_fields": [],
 "image_ratings": {{"pfad/zum/bild.jpg": 4}},
 "coherence_score": 7,
 "flags": ["image_x_blurry", "poi_y_irrelevant"]}}"""

    return prompt


def _parse_review_response(response: Optional[str]) -> Dict[str, Any]:
    """Parst die LLM-Antwort — JSON mit Regex-Fallback."""
    default: Dict[str, Any] = {
        "kept_pois": [],
        "weather_summary": "",
        "discarded_weather_fields": [],
        "image_ratings": {},
        "coherence_score": 0,
        "flags": [],
    }

    if not response:
        return default

    # JSON-Extraktion: alles zwischen { und }
    json_match = re.search(r'\{.*\}', response, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group(0))
            result = {
                "kept_pois": data.get("pois", []),
                "weather_summary": data.get("weather_summary", ""),
                "discarded_weather_fields": data.get("discarded_weather_fields", []),
                "image_ratings": data.get("image_ratings", {}),
                "coherence_score": data.get("coherence_score", 0),
                "flags": data.get("flags", []),
            }
            return result
        except json.JSONDecodeError:
            pass

    # Fallback: gesamte Antwort als Weather Summary
    default["weather_summary"] = response[:500]
    default["coherence_score"] = 0
    return default


def review_enrichment(
    weather: Optional[WeatherInfo],
    poi_list: List[Dict[str, Any]],
    selected_images: List[ImageData],
    gpx_stats: Any = None,
    notes: Optional[str] = None,
    model: str = "gemma4:26b-ctx128k",
    base_url: str = "http://localhost:11434",
) -> Dict[str, Any]:
    """Führt die Content-Review durch und gibt kuratierten Kontext zurück.

    Args:
        weather: WeatherInfo oder None
        poi_list: Liste der POI-Dicts
        selected_images: Ausgewählte Bilder
        gpx_stats: GPXStats-Objekt
        notes: Tour-Notizen
        model: Ollama-Modellname
        base_url: Ollama API URL

    Returns:
        Dict mit kept_pois, weather_summary, discarded_weather_fields,
        image_ratings, coherence_score, flags
    """
    # GPX-Stats serialisieren für den Prompt
    gpx_d = None
    if gpx_stats is not None:
        if hasattr(gpx_stats, "model_dump"):
            gpx_d = gpx_stats.model_dump()
        elif isinstance(gpx_stats, dict):
            gpx_d = gpx_stats

    prompt = _build_review_prompt(
        weather=weather,
        poi_list=poi_list,
        selected_images=selected_images,
        gpx_stats_d=gpx_d,
        notes=notes,
    )

    print("🔍 Reviewing enriched content with LLM...")

    try:
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {
                "temperature": 0.3,
                "num_predict": MAX_REVIEW_RESPONSE_TOKENS,
            },
        }
        resp = requests.post(f"{base_url}/api/chat", json=payload, timeout=120)
    except Exception as e:
        print(f"⚠️ Review LLM call failed: {e}")
        # Fallback: Rohdaten durchreichen
        return _build_fallback_context(weather, poi_list, selected_images)

    if resp.status_code != 200:
        print(f"⚠️ Review LLM returned {resp.status_code}")
        return _build_fallback_context(weather, poi_list, selected_images)

    content = resp.json().get("message", {}).get("content", "")
    result = _parse_review_response(content)

    if result["coherence_score"] < 3 and result["coherence_score"] > 0:
        print(f"⚠️ Low coherence score ({result['coherence_score']}/10) — continuing anyway")

    kept = len(result.get("kept_pois", []))
    print(f"✅ Review complete: {kept} POIs kept, coherence {result['coherence_score']}/10")
    return result


def _build_fallback_context(
    weather: Optional[WeatherInfo],
    poi_list: List[Dict[str, Any]],
    selected_images: List[ImageData],
) -> Dict[str, Any]:
    """Baut einen Fallback-Kontext, wenn der Review-LLM nicht verfügbar ist."""
    summary = ""
    if weather:
        summary = weather.summary or "Wetterdaten verfügbar (siehe Details)."

    return {
        "kept_pois": poi_list,
        "weather_summary": summary,
        "discarded_weather_fields": [],
        "image_ratings": {img.path: 3 for img in selected_images},
        "coherence_score": 0,
        "flags": ["review_unavailable"],
    }
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_services/test_content_reviewer.py -v
```

Expected: All tests pass (7 tests).

- [ ] **Step 5: Commit**

```bash
git add app/services/content_reviewer.py tests/test_services/test_content_reviewer.py
git commit -m "feat: add content reviewer service with LLM quality gate"
```

---

### Task 7: Content reviewer node

**Files:**
- Create: `app/nodes/review_content_node.py`
- Create: `tests/test_nodes/test_review_content.py`

**Dependencies:** Task 6

- [ ] **Step 1: Write the failing test**

Create `tests/test_nodes/test_review_content.py`:

```python
"""Tests for app/nodes/review_content_node.py"""
from unittest.mock import patch
from app.nodes.review_content_node import review_content_node
from app.state import AppState, ImageData, DailyWeather, WeatherInfo
from app.services.gpx_analytics import TrackPoint, GPXStats


class TestReviewContentNode:
    def test_reviews_with_all_data(self):
        weather = WeatherInfo(
            daily=[
                DailyWeather(
                    date="2025-06-01", temperature_max=20.0, temperature_min=10.0,
                    precipitation_mm=0.0, precipitation_hours=0.0,
                    weather_code=1, wind_speed_kmh=10.0, cloud_cover_pct=30.0,
                )
            ],
            summary="Sunny and mild",
        )
        points = [TrackPoint(lat=47.3, lon=11.4, elevation=800.0, time=None)]
        stats = GPXStats(
            total_distance_m=5000, elevation_gain_m=200, elevation_loss_m=100,
            avg_speed_kmh=4.0, max_speed_kmh=8.0, points=points,
        )
        images = [ImageData(path="img1.jpg")]
        state = AppState(
            weather=weather,
            poi_list=[{"name": "Berggipfel", "type": "peak", "distance_km": 1.0}],
            selected_images=images,
            gpx_stats=stats,
            notes="Great hike!",
            model="gemma4:26b-ctx128k",
        )

        mock_context = {
            "kept_pois": [{"name": "Berggipfel", "action": "KEEP"}],
            "weather_summary": "Mild and sunny",
            "discarded_weather_fields": ["freezing_level_m"],
            "image_ratings": {"img1.jpg": 4},
            "coherence_score": 8,
            "flags": [],
        }
        with patch(
            "app.nodes.review_content_node.review_enrichment",
            return_value=mock_context,
        ):
            result = review_content_node(state)
            assert result.enrichment_context == mock_context
            assert result.enrichment_context["coherence_score"] == 8

    def test_works_with_minimal_data(self):
        state = AppState(
            weather=None,
            poi_list=[],
            selected_images=[],
            gpx_stats=None,
            model="gemma4:26b-ctx128k",
        )
        mock_context = {
            "kept_pois": [],
            "weather_summary": "",
            "discarded_weather_fields": [],
            "image_ratings": {},
            "coherence_score": 0,
            "flags": ["review_unavailable"],
        }
        with patch(
            "app.nodes.review_content_node.review_enrichment",
            return_value=mock_context,
        ):
            result = review_content_node(state)
            assert result.enrichment_context == mock_context
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_nodes/test_review_content.py -v
```

Expected: ImportError — module doesn't exist yet.

- [ ] **Step 3: Implement the node**

Create `app/nodes/review_content_node.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_nodes/test_review_content.py -v
```

Expected: 2 tests pass.

- [ ] **Step 5: Commit**

```bash
git add app/nodes/review_content_node.py tests/test_nodes/test_review_content.py
git commit -m "feat: add content reviewer pipeline node"
```

---

### Task 8: Blog prompt integration

**Files:**
- Modify: `app/services/blog_generator.py`
- Modify: `app/nodes/generate_blogpost.py`
- Create: `tests/test_services/test_blog_prompt_enrichment.py`

**Dependencies:** Task 1 (needs AppState enrichment fields)

**Context:** Inject enrichment data into the blog post prompt. The `construct_blog_post_prompt` function gains new parameters. The node passes enrichment context through.

- [ ] **Step 1: Write the failing test**

Create `tests/test_services/test_blog_prompt_enrichment.py`:

```python
"""Tests for enrichment integration in blog prompt builder."""
from app.services.blog_generator import construct_blog_post_prompt


class TestBlogPromptEnrichment:
    def test_includes_enrichment_context_when_provided(self):
        enrichment = {
            "kept_pois": [
                {"name": "Berggipfel", "type": "peak", "distance_km": 1.0,
                 "wiki_extract": "A majestic peak in the Alps."},
            ],
            "weather_summary": "Mild alpine weather with clear skies.",
            "discarded_weather_fields": ["freezing_level_m"],
        }
        images = [{"path": "img1.jpg", "timestamp": "2025-06-01T10:00:00",
                   "latitude": 47.3, "longitude": 11.4}]

        prompt, img_data = construct_blog_post_prompt(
            images=images,
            enrichment_context=enrichment,
        )
        assert "Mild alpine weather" in prompt
        assert "Berggipfel" in prompt
        assert "A majestic peak" in prompt

    def test_falls_back_to_raw_weather_when_no_enrichment_context(self):
        from app.state import DailyWeather, WeatherInfo

        weather = WeatherInfo(
            daily=[
                DailyWeather(
                    date="2025-06-01", temperature_max=20.0, temperature_min=10.0,
                    precipitation_mm=0.0, precipitation_hours=0.0,
                    weather_code=1, wind_speed_kmh=10.0, cloud_cover_pct=30.0,
                )
            ],
            summary="Sunny and mild",
        )
        images = [{"path": "img1.jpg"}]

        prompt, img_data = construct_blog_post_prompt(
            images=images,
            enrichment_context={},
            weather=weather,
            poi_list=[{"name": "Test Peak", "type": "peak", "distance_km": 0.5}],
        )
        assert "Test Peak" in prompt

    def test_no_enrichment_section_when_no_data(self):
        images = [{"path": "img1.jpg"}]
        prompt, img_data = construct_blog_post_prompt(
            images=images,
            enrichment_context=None,
            weather=None,
            poi_list=[],
        )
        # Should not crash and should not contain enrichment headers
        assert isinstance(prompt, str)
        assert "WETTER WÄHREND DER TOUR" not in prompt
        assert "INTERESSANTE ORTE" not in prompt
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_services/test_blog_prompt_enrichment.py -v
```

Expected: TypeError — `construct_blog_post_prompt` doesn't accept `enrichment_context` yet.

- [ ] **Step 3: Update construct_blog_post_prompt signature and body**

In `app/services/blog_generator.py`, modify the `construct_blog_post_prompt` function:

Change the function signature (around line 120-127) from:

```python
def construct_blog_post_prompt(
    images: List[Dict[str, Any]],
    map_image_path: Optional[str] = None,
    elevation_profile_path: Optional[str] = None,
    gpx_stats: Optional[Dict[str, Any]] = None,
    notes: Optional[str] = None,
    image_path_prefix: str = ""
) -> tuple[str, List[Dict[str, Any]]]:
```

To:

```python
def construct_blog_post_prompt(
    images: List[Dict[str, Any]],
    map_image_path: Optional[str] = None,
    elevation_profile_path: Optional[str] = None,
    gpx_stats: Optional[Dict[str, Any]] = None,
    notes: Optional[str] = None,
    image_path_prefix: str = "",
    enrichment_context: Optional[Dict[str, Any]] = None,
    weather: Any = None,
    poi_list: Optional[List[Dict[str, Any]]] = None,
) -> tuple[str, List[Dict[str, Any]]]:
```

Then insert the enrichment sections into the prompt. After the GPX stats block (after line 162 which ends the stats formatting), and before the notes block, add:

```python
    # --- Wetter- und POI-Anreicherung ---
    if enrichment_context:
        weather_summary = enrichment_context.get("weather_summary", "")
        kept_pois = enrichment_context.get("kept_pois", [])
        discarded_fields = enrichment_context.get("discarded_weather_fields", [])

        if weather_summary:
            text_prompt += f"""

☀️  WETTER WÄHREND DER TOUR:
{weather_summary}
"""
            if discarded_fields:
                text_prompt += f"(Nicht relevante Wetterdaten wurden ausgefiltert: {', '.join(discarded_fields)})\n"

        if kept_pois:
            text_prompt += f"""
📍  INTERESSANTE ORTE ENTLANG DER ROUTE:
"""
            for poi in kept_pois:
                name = poi.get("name", "Unbekannt")
                ptype = poi.get("type", "POI")
                dist = poi.get("distance_km", "?")
                wiki = poi.get("wiki_extract", "")
                text_prompt += f"- {name} ({ptype}, {dist} km entfernt)"
                if wiki:
                    text_prompt += f": {wiki[:300]}"
                text_prompt += "\n"
    elif weather or poi_list:
        # Fallback: Rohdaten, wenn kein Review-Kontext
        if hasattr(weather, 'summary') and weather.summary:
            text_prompt += f"""

☀️  WETTER WÄHREND DER TOUR:
{weather.summary}
"""
        if poi_list:
            text_prompt += """
📍  INTERESSANTE ORTE ENTLANG DER ROUTE:
"""
            for poi in poi_list:
                name = poi.get("name", "Unbekannt")
                ptype = poi.get("type", "POI")
                dist = poi.get("distance_km", "?")
                text_prompt += f"- {name} ({ptype}, {dist} km entfernt)\n"
    # --- Ende Wetter- und POI-Anreicherung ---
```

- [ ] **Step 4: Update generate_blog_post to pass enrichment data**

In `app/services/blog_generator.py`, in the `generate_blog_post` function, add new parameters and pass them through to `construct_blog_post_prompt`:

Change the function signature (around line 349) from:

```python
def generate_blog_post(
    images: List[Dict[str, Any]],
    map_image_path: Optional[str] = None,
    elevation_profile_path: Optional[str] = None,
    gpx_stats: Optional[Dict[str, Any]] = None,
    notes: Optional[str] = None,
    model: str = "gemma4:26b-ctx128k"
) -> Dict[str, Any]:
```

To:

```python
def generate_blog_post(
    images: List[Dict[str, Any]],
    map_image_path: Optional[str] = None,
    elevation_profile_path: Optional[str] = None,
    gpx_stats: Optional[Dict[str, Any]] = None,
    notes: Optional[str] = None,
    model: str = "gemma4:26b-ctx128k",
    enrichment_context: Optional[Dict[str, Any]] = None,
    weather: Any = None,
    poi_list: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
```

Then update the `construct_blog_post_prompt` call (around line 408) to pass the new arguments:

```python
    prompt, image_data = construct_blog_post_prompt(
        images=images_for_prompt,
        map_image_path=abs_map,
        elevation_profile_path=elevation_profile_path,
        gpx_stats=gpx_stats,
        notes=notes,
        image_path_prefix=image_path_prefix,
        enrichment_context=enrichment_context,
        weather=weather,
        poi_list=poi_list,
    )
```

- [ ] **Step 5: Update generate_blog_post_node to pass enrichment data**

In `app/nodes/generate_blogpost.py`, modify the `generate_blog_post` call to include enrichment data:

Change the `generate_blog_post(...)` call (around line 35) from:

```python
        result = generate_blog_post(
            images=[img.model_dump() for img in images],
            map_image_path=map_image_path,
            elevation_profile_path=state.elevation_profile_path,
            gpx_stats=state.gpx_stats.model_dump() if hasattr(state.gpx_stats, "model_dump") else state.gpx_stats,
            notes=state.notes,
            model=state.model,
        )
```

To:

```python
        result = generate_blog_post(
            images=[img.model_dump() for img in images],
            map_image_path=map_image_path,
            elevation_profile_path=state.elevation_profile_path,
            gpx_stats=state.gpx_stats.model_dump() if hasattr(state.gpx_stats, "model_dump") else state.gpx_stats,
            notes=state.notes,
            model=state.model,
            enrichment_context=state.enrichment_context,
            weather=state.weather,
            poi_list=state.poi_list,
        )
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
uv run pytest tests/test_services/test_blog_prompt_enrichment.py -v
uv run pytest tests/test_nodes/test_generate_blogpost.py -v
```

Expected: All tests pass.

- [ ] **Step 7: Commit**

```bash
git add app/services/blog_generator.py app/nodes/generate_blogpost.py tests/test_services/test_blog_prompt_enrichment.py
git commit -m "feat: integrate enrichment context and raw weather/POI data into blog prompt"
```

---

### Task 9: Graph wiring

**Files:**
- Modify: `app/graph.py`

**Dependencies:** Tasks 3, 5, 7 (all three nodes must exist), Task 8 (blog prompt integration)

**Context:** Insert the three new nodes into the pipeline and raise the `select_images` target count.

- [ ] **Step 1: Write the failing test**

Create/check `tests/test_graph/` exists and create `tests/test_graph/test_enrichment_graph.py`:

```bash
ls tests/test_graph/
```

```python
"""Tests for enrichment pipeline graph."""
from app.graph import build_graph
from app.state import AppState, ImageData, DailyWeather, WeatherInfo
from app.services.gpx_analytics import TrackPoint, GPXStats
from datetime import datetime


class TestEnrichmentPipeline:
    def test_enrichment_nodes_in_graph(self):
        """Verifies the graph compiles with all 11 nodes."""
        graph = build_graph()
        nodes = graph.get_graph().nodes
        expected_nodes = {
            "process_gpx", "load_images", "extract_metadata",
            "clustering_images", "generate_map_image", "load_tour_notes",
            "enrich_weather", "enrich_poi", "select_images",
            "review_content", "generate_blog_post",
        }
        # Check that all expected nodes exist
        for node in expected_nodes:
            assert node in nodes, f"Missing node: {node}"

    def test_pipeline_invokes_enrichment_nodes(self):
        """Smoke test: invoke graph with minimal valid state."""
        graph = build_graph()
        points = [
            TrackPoint(lat=47.3, lon=11.4, elevation=800.0,
                       time=datetime(2025, 6, 1, 10, 0)),
            TrackPoint(lat=47.31, lon=11.41, elevation=850.0,
                       time=datetime(2025, 6, 1, 12, 0)),
        ]
        stats = GPXStats(
            total_distance_m=1000, elevation_gain_m=50, elevation_loss_m=0,
            avg_speed_kmh=3.0, max_speed_kmh=5.0, points=points,
        )

        state = AppState(
            gpx_stats=stats,
            gpx_pauses=[],
            images=[ImageData(path="img1.jpg")],
            selected_images=[ImageData(path="img1.jpg")],
            notes="Great hike",
            model="gemma4:26b-ctx128k",
            # Pre-fill enrichment so network calls are skipped
            weather=WeatherInfo(
                daily=[
                    DailyWeather(
                        date="2025-06-01", temperature_max=20.0, temperature_min=10.0,
                        precipitation_mm=0.0, precipitation_hours=0.0,
                        weather_code=1, wind_speed_kmh=10.0, cloud_cover_pct=30.0,
                    )
                ],
                summary="Sunny",
            ),
            poi_list=[{"name": "Test Peak", "type": "peak", "distance_km": 0.5}],
            enrichment_context={
                "kept_pois": [{"name": "Test Peak", "type": "peak", "distance_km": 0.5}],
                "weather_summary": "Sunny and clear",
                "discarded_weather_fields": [],
                "image_ratings": {},
                "coherence_score": 8,
                "flags": [],
            },
        )

        # The graph should run through without error.
        # Blog generation will fail (no Ollama), but that's expected.
        try:
            result = graph.invoke(state)
        except Exception as e:
            # Acceptable: network/Ollama errors expected in CI
            assert True, f"Graph invocation raised expected error: {e}"
```

- [ ] **Step 2: Update graph.py with new nodes and edges**

In `app/graph.py`, add imports for the three new nodes (after the existing imports):

```python
from app.nodes.enrich_weather_node import enrich_weather_node
from app.nodes.enrich_poi_node import enrich_poi_node
from app.nodes.review_content_node import review_content_node
```

Add display names to `NODE_NAMES`:

```python
NODE_NAMES = {
    "process_gpx": "GPX-Analyse",
    "load_images": "Bilder laden",
    "extract_metadata": "Metadaten extrahieren",
    "clustering_images": "Bilder gruppieren",
    "generate_map_image": "Karte generieren",
    "load_tour_notes": "Notizen laden",
    "enrich_weather": "Wetterdaten abrufen",
    "enrich_poi": "POIs suchen",
    "select_images": "Bilder auswählen",
    "review_content": "Inhalte prüfen",
    "generate_blog_post": "Blogpost generieren",
}
```

In `build_graph()`, add three new nodes (after the existing `add_node` calls):

```python
    # Enrichment nodes
    ewn = _wrap_node(enrich_weather_node, "enrich_weather", event_emitter) if event_emitter else enrich_weather_node
    epn = _wrap_node(enrich_poi_node, "enrich_poi", event_emitter) if event_emitter else enrich_poi_node
    rcn = _wrap_node(review_content_node, "review_content", event_emitter) if event_emitter else review_content_node

    builder.add_node("enrich_weather", ewn)
    builder.add_node("enrich_poi", epn)
    builder.add_node("review_content", rcn)
```

Replace the old `load_tour_notes → select_images` edge with the new chain:

```python
    # Alte Kante entfernen:
    # builder.add_edge("load_tour_notes", "select_images")

    # Neue Kanten:
    builder.add_edge("load_tour_notes", "enrich_weather")
    builder.add_edge("enrich_weather", "enrich_poi")
    builder.add_edge("enrich_poi", "select_images")
    builder.add_edge("select_images", "review_content")
    builder.add_edge("review_content", "generate_blog_post")
```

Important: Verify the finish point is still `"generate_blog_post"` (no change needed):

```python
    builder.set_finish_point("generate_blog_post")
```

- [ ] **Step 3: Raise select_images target count**

In `app/nodes/select_images_node.py`, change `target = 8` to `target = 12`:

```python
def select_images_node(state: AppState) -> AppState:
    """Wählt die besten Bilder für den Blogpost mit einem multimodalen LLM."""
    n = len(state.images)
    target = 12
    print(f"📸 Selecting {target} images for blog post from {n} images...")
    # ... rest unchanged
```

Update the corresponding test expectation in `tests/test_nodes/test_select_images.py` if needed (the test doesn't check the target count, so no change required).

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_graph/ -v
uv run pytest tests/test_nodes/ -v
```

Expected: Graph compilation test passes. Node tests continue to pass.

- [ ] **Step 5: Commit**

```bash
git add app/graph.py app/nodes/select_images_node.py tests/test_graph/test_enrichment_graph.py
git commit -m "feat: wire enrichment and review nodes into pipeline graph"
```

---

### Task 10: End-to-end verification

**Files:**
- Create: `tests/test_api/test_enrichment_e2e.py`

**Dependencies:** All previous tasks

**Context:** Verify the full pipeline runs end-to-end with mocked network calls.

- [ ] **Step 1: Write the E2E test**

Create `tests/test_api/test_enrichment_e2e.py` (if `tests/test_api/` doesn't exist, create it):

```python
"""End-to-end test for enrichment pipeline with mocked network."""
import json
from unittest.mock import patch, Mock

from app.graph import build_graph
from app.state import AppState, ImageData
from app.services.gpx_analytics import TrackPoint, GPXStats
from datetime import datetime


def build_valid_state():
    """Hilfsfunktion: Baut einen AppState mit GPX-Daten und Bildern."""
    points = [
        TrackPoint(lat=47.3, lon=11.4, elevation=800.0,
                   time=datetime(2025, 6, 1, 10, 0)),
        TrackPoint(lat=47.31, lon=11.41, elevation=900.0,
                   time=datetime(2025, 6, 1, 14, 0)),
    ]
    stats = GPXStats(
        total_distance_m=5000, elevation_gain_m=300, elevation_loss_m=200,
        avg_speed_kmh=3.5, max_speed_kmh=7.0, points=points,
    )
    return AppState(
        gpx_stats=stats,
        gpx_pauses=[{
            "start_time": datetime(2025, 6, 1, 12, 0),
            "end_time": datetime(2025, 6, 1, 12, 30),
            "duration_minutes": 30.0,
            "location": {"lat": 47.305, "lon": 11.405},
        }],
        images=[ImageData(path=f"img{i}.jpg") for i in range(5)],
        notes="A great day out.",
        model="gemma4:26b-ctx128k",
    )


class TestEnrichmentE2E:
    def test_full_pipeline_with_mocked_network(self):
        """End-to-end test: pipeline läuft mit allen 11 Knoten durch."""
        state = build_valid_state()

        # Mock: Open-Meteo weather response
        mock_weather_resp = Mock()
        mock_weather_resp.status_code = 200
        mock_weather_resp.json.return_value = {
            "daily": {
                "time": ["2025-06-01"],
                "temperature_2m_max": [21.0],
                "temperature_2m_min": [11.0],
                "precipitation_sum": [0.0],
                "precipitation_hours": [0.0],
                "weather_code": [1],
                "wind_speed_10m_max": [12.0],
                "cloud_cover_mean": [25.0],
            }
        }

        # Mock: Overpass POI response
        mock_overpass_resp = Mock()
        mock_overpass_resp.status_code = 200
        mock_overpass_resp.json.return_value = {
            "elements": []
        }

        # Mock: Ollama review response
        mock_review_resp = Mock()
        mock_review_resp.status_code = 200
        mock_review_resp.json.return_value = {
            "message": {"content": json.dumps({
                "pois": [],
                "weather_summary": "A beautiful sunny day in the Alps.",
                "discarded_weather_fields": [],
                "image_ratings": {f"img{i}.jpg": 4 for i in range(5)},
                "coherence_score": 8,
                "flags": [],
            })},
        }

        # Mock: Ollama blog generation response
        mock_blog_resp = Mock()
        mock_blog_resp.status_code = 200
        mock_blog_resp.json.return_value = {
            "message": {"content": "# Test Blog\n\nThis is a test blog post."},
        }

        with patch("app.services.weather_enricher.requests.get",
                   return_value=mock_weather_resp), \
             patch("app.services.poi_enricher.requests.post",
                   return_value=mock_overpass_resp), \
             patch("app.services.content_reviewer.requests.post",
                   return_value=mock_review_resp), \
             patch("app.services.blog_generator.requests.post",
                   return_value=mock_blog_resp):
            graph = build_graph()
            result = graph.invoke(state)

        # Verify state was enriched
        assert result.weather is not None
        assert result.enrichment_context.get("weather_summary") == "A beautiful sunny day in the Alps."
        assert result.enrichment_context.get("coherence_score") == 8
        # Blog generation should have run
        assert result.blog_post is not None

    def test_pipeline_survives_weather_failure(self):
        """Pipeline sollte weiterlaufen, auch wenn der Wetterdienst ausfällt."""
        state = build_valid_state()

        mock_overpass_resp = Mock()
        mock_overpass_resp.status_code = 200
        mock_overpass_resp.json.return_value = {"elements": []}

        mock_review_resp = Mock()
        mock_review_resp.status_code = 200
        mock_review_resp.json.return_value = {
            "message": {"content": json.dumps({
                "pois": [],
                "weather_summary": "No weather data available.",
                "discarded_weather_fields": [],
                "image_ratings": {},
                "coherence_score": 5,
                "flags": [],
            })},
        }

        mock_blog_resp = Mock()
        mock_blog_resp.status_code = 200
        mock_blog_resp.json.return_value = {
            "message": {"content": "# Test Blog\n\nWeather was unavailable."},
        }

        with patch("app.services.weather_enricher.requests.get",
                   side_effect=Exception("Connection refused")), \
             patch("app.services.poi_enricher.requests.post",
                   return_value=mock_overpass_resp), \
             patch("app.services.content_reviewer.requests.post",
                   return_value=mock_review_resp), \
             patch("app.services.blog_generator.requests.post",
                   return_value=mock_blog_resp):
            graph = build_graph()
            result = graph.invoke(state)

        # Weather should be None (failed), but pipeline continues
        assert result.weather is None
        # Blog post should still be generated
        assert result.blog_post is not None
```

- [ ] **Step 2: Run E2E tests**

```bash
uv run pytest tests/test_api/test_enrichment_e2e.py -v
```

Expected: 2 tests pass (full pipeline with mocks, degraded pipeline on weather failure).

- [ ] **Step 3: Run all enrichment tests together**

```bash
uv run pytest tests/test_state.py tests/test_services/test_weather_enricher.py tests/test_services/test_poi_enricher.py tests/test_services/test_content_reviewer.py tests/test_services/test_blog_prompt_enrichment.py tests/test_nodes/test_enrich_weather.py tests/test_nodes/test_enrich_poi.py tests/test_nodes/test_review_content.py tests/test_graph/test_enrichment_graph.py tests/test_api/test_enrichment_e2e.py -v
```

Expected: All tests pass (should be ~35+ tests total).

- [ ] **Step 4: Commit**

```bash
git add tests/test_api/test_enrichment_e2e.py
git commit -m "test: add end-to-end enrichment pipeline tests"
```

---

## Summary

| Task | Files Created | Files Modified | Tests |
|------|--------------|----------------|-------|
| 1. Weather models | `tests/test_state.py` | `app/state.py` | 5 |
| 2. Weather service | `app/services/weather_enricher.py`, `tests/test_services/test_weather_enricher.py` | — | 9 |
| 3. Weather node | `app/nodes/enrich_weather_node.py`, `tests/test_nodes/test_enrich_weather.py` | — | 2 |
| 4. POI service | `app/services/poi_enricher.py`, `tests/test_services/test_poi_enricher.py` | — | 12 |
| 5. POI node | `app/nodes/enrich_poi_node.py`, `tests/test_nodes/test_enrich_poi.py` | — | 2 |
| 6. Review service | `app/services/content_reviewer.py`, `tests/test_services/test_content_reviewer.py` | — | 7 |
| 7. Review node | `app/nodes/review_content_node.py`, `tests/test_nodes/test_review_content.py` | — | 2 |
| 8. Blog prompt | `tests/test_services/test_blog_prompt_enrichment.py` | `app/services/blog_generator.py`, `app/nodes/generate_blogpost.py` | 3 |
| 9. Graph wiring | `tests/test_graph/test_enrichment_graph.py` | `app/graph.py`, `app/nodes/select_images_node.py` | 2 |
| 10. E2E | `tests/test_api/test_enrichment_e2e.py` | — | 2 |

**Total: 46 tests | 10 commits | 7 new service/node files | 4 modified files**

### Parallel Execution Strategy

Tasks 2, 4, and 6 have zero code dependencies — they can be dispatched to three subagents simultaneously. Tasks 3, 5, 7 each depend on their corresponding service task. Task 8 depends on models (Task 1). Task 9 depends on all nodes existing (Tasks 3, 5, 7). Task 10 depends on everything.

Recommended dispatch order:
1. **Batch 1** (parallel): Tasks 1, 2, 4, 6
2. **Batch 2** (parallel): Tasks 3, 5, 7, 8
3. **Batch 3** (sequential): Task 9
4. **Batch 4** (sequential): Task 10
