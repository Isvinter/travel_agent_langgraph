# Enrichment & Review Pipeline

**Date:** 2026-04-30
**Status:** approved

## Overview

Extend the travel blog generator pipeline with three new capabilities:

1. **Historical weather enrichment** via Open-Meteo (free, no account, no API key)
2. **POI enrichment** via Overpass API + optional Wikipedia extracts (free, no account)
3. **Content review** — a single-pass LLM quality gate that filters and curates enrichment data before blog generation

The review step prunes irrelevant POIs, generates a weather summary, rates images for thematic fit, and assesses overall coherence — all in one Ollama call. It is designed as a single-pass gate (no iterative loop), but with a clean interface that allows adding a human-in-the-loop mode later by swapping or extending the review node implementation.

All external dependencies are free, require no authentication, and are replaceable without affecting the rest of the pipeline.

## New Pipeline

Three new nodes inserted into the existing linear pipeline. Total grows from 8 to 11 nodes.

```
process_gpx → load_images → extract_metadata → clustering_images
  → generate_map_image → load_tour_notes
  → enrich_weather → enrich_poi → select_images → review_content
  → generate_blog_post
```

| New Node | Insertion Point | Responsibility |
|----------|----------------|----------------|
| `enrich_weather` | after `load_tour_notes` | Fetch historical weather from Open-Meteo for the trip date range and route coordinates |
| `enrich_poi` | after `enrich_weather` | Query Overpass API for POIs near pause locations; optionally enrich with Wikipedia lead paragraphs |
| `review_content` | after `select_images` | LLM-based quality gate: filter POIs, summarize weather, rate images, produce curated context for blog prompt |

`select_images` stays after enrichment so the reviewer sees weather, POIs, and selected images together. `select_images` target count is raised from 8 to 12-15 images; the reviewer may flag weak images, and the blog prompt builder has more material to work with.

## AppState Changes

New fields on `AppState`:

```python
weather: Optional[WeatherInfo] = None
poi_list: List[Dict[str, Any]] = []
enrichment_context: Dict[str, Any] = {}
```

New Pydantic models:

```python
class DailyWeather(BaseModel):
    date: str
    temperature_max: float
    temperature_min: float
    precipitation_mm: float         # Niederschlagsmenge
    precipitation_hours: float      # Stunden mit Niederschlag (Intensitätsindikator)
    freezing_level_m: Optional[float] = None  # 0°C-Grenze (Höhe ü. NN), None wenn nicht ermittelbar
    weather_code: int               # Open-Meteo WMO code
    wind_speed_kmh: float
    cloud_cover_pct: float

class WeatherInfo(BaseModel):
    daily: List[DailyWeather]
    source: str = "open-meteo"
    summary: str = ""
```

Existing fields (`images`, `selected_images`, `gpx_stats`, `gpx_pauses`, `metadata`, `notes`, `blog_post`, `model`) are unchanged.

## Services

### 1. Weather Enricher (`app/services/weather_enricher.py`)

**Input:** `List[TrackPoint]` from `GPXStats` (lat, lon, timestamps), plus pause locations from `gpx_pauses`.

**Process:**
- Extract date range from track points (first and last timestamp)
- Select ~10 representative coordinate points: every 20th track point plus all pause locations, spatially deduplicated
- Call Open-Meteo Historical Weather API: `GET https://archive-api.open-meteo.com/v1/archive`
  - Parameters: `latitude`, `longitude`, `start_date`, `end_date`, `daily=temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_hours,weather_code,wind_speed_10m_max,cloud_cover_mean`
  - One call per unique (lat, lon) — batch if Open-Meteo supports multi-location, otherwise sequentially with 100ms delay between calls (respectful of rate limits)
- Aggregate results across query points: take the median temperature range, max precipitation, predominant weather code
- **Freezing level estimation:** Open-Meteo archive API does not provide `freezing_level_height`. Instead, estimate it from available data:
  - Use the standard atmospheric lapse rate of ~6.5 °C per 1000 m
  - For each day: take the median track elevation + daily min temperature, extrapolate upward to 0°C: `freezing_level_m ≈ median_track_elevation + (temperature_min / 0.0065)`, clamped to 0–6000 m
  - If no elevation data exists, set `freezing_level_m = None`
- Build `WeatherInfo` with `daily` records and a human-readable `summary` string

**Output:** `WeatherInfo` model.

**Error handling:** If Open-Meteo is unreachable or returns non-200, log a warning, set `state.weather = None`, continue pipeline.

### 2. POI Enricher (`app/services/poi_enricher.py`)

**Input:** `List[dict]` from `gpx_pauses`, track bounding box from `gpx_stats`.

**Process (Overpass API):**
- For each pause location, construct an Overpass QL query with radius ~2km:
  ```
  [out:json];
  (
    node["tourism"~"viewpoint|alpine_hut|information|museum"](around:2000,lat,lon);
    node["natural"="peak"](around:2000,lat,lon);
    node["historic"~"ruins|castle|memorial"](around:2000,lat,lon);
  );
  out 10;
  ```
- Call `POST https://overpass-api.de/api/interpreter` with the query string
- Deduplicate results by name (case-insensitive) and proximity (within 500m of another result)
- Compute distance from each POI to its associated pause point
- **Optional Wikipedia enrichment:** For POIs with a `wikipedia=lang:Title` tag, fetch the lead paragraph via `GET https://{lang}.wikipedia.org/api/rest_v1/page/summary/{title}`
  - Store `wiki_extract` (first 500 chars) in the POI dict for narrative context in the blog prompt

**Output:** `List[Dict[str, Any]]` stored as `state.poi_list`. Each entry has: `name`, `type`, `lat`, `lon`, `distance_km`, `wiki_extract` (optional).

**Error handling:**
- Overpass rate-limited (HTTP 429): wait 2 seconds, retry once
- Overpass unreachable: log warning, empty `poi_list`, continue
- Wikipedia fetch failure: leave `wiki_extract` as `None`, continue

### 3. Content Reviewer (`app/services/content_reviewer.py`)

**Input:** `WeatherInfo`, POI list, selected images, `GPXStats`, tour notes.

**Process (single-pass LLM quality gate):**
- Construct a prompt for the same Ollama model (temperature 0.3 for deterministic curation):
  ```
  You are a travel blog editor. Review the following enriched trip data.
  Your job is to filter and curate for a compelling narrative.

  WEATHER DATA:
  {weather summary from WeatherInfo}

  POINTS OF INTEREST ({n} found):
  {POI list with name, type, distance, wiki extract}

  SELECTED IMAGES ({m} images):
  {image list with timestamp, lat/lon description}

  TASKS:
  1. POI filtering: Mark each POI as KEEP or DISCARD. Discard irrelevant items
     (urban infrastructure, mundane objects, duplicates by name/proximity).
     Keep at most 8 POIs. Provide a brief reason for each discard.
  2. Weather context: Write a 2-3 sentence weather summary suitable for a blog intro.
     CRITICAL — some weather fields are context-dependent and MUST be discarded
     when not applicable:
     - Precipitation data (amount + hours): discard if the trip had zero or
       negligible precipitation throughout.
     - Freezing level (0°C altitude): discard if the track's maximum elevation
       is far below it (e.g. freezing level at 2500 m on a flat 200 m hike).
       Only include freezing level when it is within ~1000 m of the track's
       max elevation or the trip involves alpine terrain.
     - Wind speed: discard if values are unremarkable (< 20 km/h).
     The goal is to NOT confuse the blog writer with irrelevant data.
  3. Image quality: Rate each image 1-5 on thematic fit for a travel blog.
     Flag any that appear blurry, poorly composed, or duplicative.
  4. Overall coherence: Score 1-10 how well this data tells a coherent travel story.

  Respond ONLY in valid JSON:
  {"pois": [{"name": "...", "action": "KEEP|DISCARD", "reason": "..."}],
   "weather_summary": "...",
   "discarded_weather_fields": [],
   "image_ratings": {"path/to/image.jpg": 4, ...},
   "coherence_score": 7,
   "flags": ["image_x_blurry", "poi_y_irrelevant"]}
  ```
- Call Ollama with **text only** (no images in review call — image ratings are based on metadata descriptions and the prior selection quality)
- Parse JSON response; fallback to regex extraction if JSON parsing fails

**Output:** `enrichment_context` dict stored on `AppState`:
```json
{
  "kept_pois": [...],
  "weather_summary": "2-3 sentence text",
  "discarded_weather_fields": [],
  "image_ratings": {"relative/path.jpg": 4, ...},
  "coherence_score": 7,
  "flags": ["image_03_blurry", "poi_bus_stop_irrelevant"]
}
```

**Error handling:**
- LLM call fails or JSON unparseable: pass raw data through; `enrichment_context` contains all POIs marked as KEEP, raw weather summary, neutral image ratings
- Coherence score below 3: log a warning but still proceed (degraded enrichment is better than no blog post)

### 4. Blog Prompt Integration (modify `app/services/blog_generator.py`)

`construct_blog_post_prompt()` gains two new optional parameters: `enrichment_context` and `weather`. Two new sections are injected into the prompt text, between the GPX stats and the notes section:

```
☀️  WETTER WÄHREND DER TOUR:
{enrichment_context.weather_summary or weather.summary}

📍  INTERESSANTE ORTE ENTLANG DER ROUTE:
{list of kept_pois with name, type, distance, wiki extract as natural language}
```

If `enrichment_context` is empty (review failed), fall back to raw `weather` and `poi_list` for these sections.

## Node Implementations

Each node follows the existing thin-wrapper pattern: `AppState → AppState`, delegates to a service function.

### `enrich_weather_node` (`app/nodes/enrich_weather_node.py`)

```python
def enrich_weather_node(state: AppState) -> AppState:
    if not state.gpx_stats:
        return state
    state.weather = fetch_historical_weather(
        track_points=state.gpx_stats.points,
        pauses=state.gpx_pauses,
    )
    return state
```

### `enrich_poi_node` (`app/nodes/enrich_poi_node.py`)

```python
def enrich_poi_node(state: AppState) -> AppState:
    if not state.gpx_stats or not state.gpx_pauses:
        return state
    state.poi_list = fetch_pois(
        pauses=state.gpx_pauses,
    )
    return state
```

### `review_content_node` (`app/nodes/review_content_node.py`)

```python
def review_content_node(state: AppState) -> AppState:
    state.enrichment_context = review_enrichment(
        weather=state.weather,
        poi_list=state.poi_list,
        selected_images=state.selected_images,
        gpx_stats=state.gpx_stats,
        notes=state.notes,
        model=state.model,
    )
    return state
```

## Graph Wiring

In `app/graph.py`, `build_graph()`:

1. Add three new edges replacing the old `load_tour_notes → select_images` segment:
   ```
   load_tour_notes → enrich_weather → enrich_poi → select_images → review_content → generate_blog_post
   ```
2. Register new nodes with `builder.add_node(...)` and `builder.add_edge(...)`
3. Add display names to `NODE_NAMES` dict for the event emitter

Existing nodes and edges are unchanged except for the replaced edge.

## Error Resilience

The pipeline never halts on enrichment failure. Every service has a non-fatal error path:

| Failure | Behavior |
|---------|----------|
| Open-Meteo unreachable | `weather = None`, log warning, continue |
| Overpass rate-limited (429) | Retry once with 2s delay, then log warning, empty list |
| Overpass unreachable | Log warning, `poi_list = []`, continue |
| Wikipedia fetch fails | `wiki_extract` stays `None`, POI kept without text |
| Review LLM call fails | Log warning, pass raw enrichment through unfiltered |
| Review JSON unparseable | Regex extraction fallback, then raw pass-through |

All warnings use `print(f"⚠️ ...")` to match the existing logging convention.

## Implementation Decomposition (for subagent-driven development)

The work breaks into 7 independent subtasks, ordered by dependency:

| # | Subtask | Dependencies | Description |
|---|---------|-------------|-------------|
| 1 | Weather model + Open-Meteo service | None | Add `DailyWeather`, `WeatherInfo` to `app/state.py`. Implement `app/services/weather_enricher.py` with `fetch_historical_weather()` function. |
| 2 | POI model + Overpass + Wikipedia service | None | Implement `app/services/poi_enricher.py` with `fetch_pois()` function. Overpass query builder, dedup logic, optional Wikipedia enrichment. |
| 3 | Content reviewer service | None | Implement `app/services/content_reviewer.py` with `review_enrichment()` function. LLM prompt, JSON parse + regex fallback. |
| 4 | Enrichment nodes | 1, 2, 3 | Create `app/nodes/enrich_weather_node.py`, `app/nodes/enrich_poi_node.py`, `app/nodes/review_content_node.py`. |
| 5 | Blog prompt integration | 3 | Modify `construct_blog_post_prompt()` and `generate_blog_post()` in `blog_generator.py` to accept and render enrichment data. |
| 6 | Graph wiring | 4, 5 | Update `build_graph()` in `app/graph.py`: add nodes, edges, NODE_NAMES entries. Raise `select_images` target count from 8 to 12. |
| 7 | End-to-end verification | 1-6 | Run `uv run python main.py` with a real GPX file, verify weather/POI are fetched, review runs, blog prompt contains enriched sections. |

Subtasks 1, 2, and 3 have no code dependencies on each other — they can be implemented in parallel by separate subagents. Subtask 4 depends on 1-3. Subtask 5 depends on 3 (needs the `enrichment_context` shape). Subtask 6 depends on 4 and 5. Subtask 7 is last.

## Open Questions (resolved during implementation)

- Exact coordinate sampling strategy for Open-Meteo calls (every 20th point = default, tune if too many/few calls)
- Overpass query radius (2km default, may need regional adjustment)
- Review prompt temperature (0.3 default, tune for determinism vs. flexibility)
- Image rating scale usage in blog prompt (ratings currently informational; future: could auto-drop images rated 1-2)
