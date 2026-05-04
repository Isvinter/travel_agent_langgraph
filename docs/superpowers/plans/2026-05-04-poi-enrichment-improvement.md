# POI Enrichment Improvement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Robuste, fehlertolerante POI-Abfrage mit ~60 outdoor-relevanten OSM-Kategorien und Datei-Cache, ohne neue Abhängigkeiten.

**Architecture:** Einzelne Datei `app/services/poi_enricher.py` wird komplett überarbeitet. Interface (`fetch_pois(pauses, search_radius_m) -> List[Dict]`) bleibt unverändert. Intern: dynamische Query aus Kategorie-Dict, 3 Overpass-Instanzen mit Fallback, generischer Retry bei allen Fehlern, Datei-Cache unter `output/poi_cache.json`.

**Tech Stack:** `requests`, `json`, `math`, `time` — alle bereits im Projekt.

---

### Task 1: Define expanded POI categories dict

**Files:**
- Modify: `app/services/poi_enricher.py` (top section, after imports)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_services/test_poi_enricher.py — neue Test-Klasse

class TestCategories:
    def test_categories_dict_is_well_formed(self):
        from app.services.poi_enricher import OVERPASS_POI_CATEGORIES
        assert isinstance(OVERPASS_POI_CATEGORIES, dict)
        assert len(OVERPASS_POI_CATEGORIES) >= 5
        for key, values in OVERPASS_POI_CATEGORIES.items():
            assert isinstance(values, list)
            assert len(values) > 0
            for v in values:
                assert isinstance(v, str)
                assert " " not in v  # OSM-Tags haben keine Leerzeichen
```

- [ ] **Step 2: Run test to verify it fails**

```
uv run pytest tests/test_services/test_poi_enricher.py::TestCategories::test_categories_dict_is_well_formed -v
```
Expected: FAIL (ImportError — `OVERPASS_POI_CATEGORIES` not defined)

- [ ] **Step 3: Write minimal implementation**

Replace the existing top-level constants in `app/services/poi_enricher.py` (lines 16-19):

```python
OVERPASS_INSTANCES = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]

OVERPASS_POI_CATEGORIES = {
    "natural": [
        "peak", "volcano", "cliff", "cave_entrance", "rock",
        "spring", "waterfall", "glacier", "ridge", "valley",
        "saddle", "hill", "geyser", "crater",
    ],
    "tourism": [
        "alpine_hut", "wilderness_hut", "viewpoint", "picnic_site",
        "camp_site", "artwork", "attraction", "guest_house",
    ],
    "historic": [
        "castle", "ruins", "memorial", "wayside_cross",
        "archaeological_site", "boundary_stone", "battlefield",
        "mine", "monument", "city_gate", "fort", "tower",
    ],
    "amenity": [
        "shelter", "drinking_water", "fountain", "bench",
        "hunting_stand", "biergarten",
    ],
    "leisure": [
        "picnic_table", "firepit",
    ],
    "man_made": [
        "cross", "tower", "observatory", "cairn",
    ],
    "waterway": ["waterfall", "dam"],
    "water": ["lake", "reservoir"],
}

DEFAULT_SEARCH_RADIUS_M = 2000
MAX_POIS_PER_LOCATION = 15
PROXIMITY_DEDUP_M = 500
```

Remove the old `OVERPASS_URL = "https://overpass-api.de/api/interpreter"` line. Keep `DEFAULT_SEARCH_RADIUS_M` and `PROXIMITY_DEDUP_M`. Change `MAX_POIS_PER_LOCATION` from 10 to 15.

- [ ] **Step 4: Run test to verify it passes**

```
uv run pytest tests/test_services/test_poi_enricher.py::TestCategories::test_categories_dict_is_well_formed -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_services/test_poi_enricher.py app/services/poi_enricher.py
git commit -m "feat: define expanded POI categories dict and multi-instance config"
```

---

### Task 2: Dynamic Overpass query builder

**Files:**
- Modify: `app/services/poi_enricher.py` (replace `_build_overpass_query`)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_services/test_poi_enricher.py — zur TestBuildOverpassQuery-Klasse hinzufügen

def test_builds_query_from_all_categories(self):
    from app.services.poi_enricher import _build_overpass_query
    query = _build_overpass_query(47.3, 11.4, radius=3000)
    assert "[out:json]" in query
    assert "around:3000" in query
    # Alle Kategorien prüfen
    assert 'natural"~"peak|volcano' in query
    assert 'tourism"~"alpine_hut|wilderness_hut' in query
    assert 'historic"~"castle|ruins' in query
    assert 'amenity"~"shelter|drinking_water' in query
    assert "out 15;" in query  # MAX_POIS_PER_LOCATION

def test_way_elements_queried(self):
    from app.services.poi_enricher import _build_overpass_query
    query = _build_overpass_query(47.3, 11.4)
    assert "way[" in query

def test_empty_categories_handled(self):
    from app.services.poi_enricher import _build_overpass_query
    # Sollte funktionieren, auch wenn Kategorien initialisiert sind
    query = _build_overpass_query(47.3, 11.4)
    assert ";" in query
    assert "(" in query
```

- [ ] **Step 2: Run tests to verify they fail**

```
uv run pytest tests/test_services/test_poi_enricher.py::TestBuildOverpassQuery -v
```
Expected: Two of three new tests FAIL (still old `_build_overpass_query`)

- [ ] **Step 3: Write minimal implementation**

Replace the `_build_overpass_query` function (lines 22-30):

```python
def _build_overpass_query(lat: float, lon: float, radius: int = DEFAULT_SEARCH_RADIUS_M) -> str:
    """Baut eine Overpass QL-Query aus den Kategorien in OVERPASS_POI_CATEGORIES."""
    lines = ["[out:json];", "("]

    for category, values in OVERPASS_POI_CATEGORIES.items():
        value_str = "|".join(values)
        # Nodes
        lines.append(
            f'  node["{category}"~"{value_str}"](around:{radius},{lat},{lon});'
        )
        # Ways (für Flächen-POIs wie Seen, Burganlagen, etc.)
        lines.append(
            f'  way["{category}"~"{value_str}"](around:{radius},{lat},{lon});'
        )

    lines.append(");")
    lines.append(f"out {MAX_POIS_PER_LOCATION};")
    return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

```
uv run pytest tests/test_services/test_poi_enricher.py::TestBuildOverpassQuery -v
```
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_services/test_poi_enricher.py app/services/poi_enricher.py
git commit -m "feat: dynamic Overpass query builder from category dict"
```

---

### Task 3: Parse way elements and new category keys

**Files:**
- Modify: `app/services/poi_enricher.py` (replace `_parse_overpass_response`)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_services/test_poi_enricher.py — zur TestParseOverpassResponse-Klasse hinzufügen

def test_parses_way_element_with_center(self):
    raw = {
        "elements": [{
            "id": 999,
            "type": "way",
            "center": {"lat": 47.3, "lon": 11.4},
            "tags": {"name": "Bergsee", "natural": "water"},
        }]
    }
    results = _parse_overpass_response(raw, ref_lat=47.305, ref_lon=11.405)
    assert len(results) == 1
    assert results[0]["name"] == "Bergsee"
    assert results[0]["type"] == "water"

def test_parses_new_category_keys(self):
    raw = {
        "elements": [{
            "id": 123, "type": "node", "lat": 47.3, "lon": 11.4,
            "tags": {"name": "Schutzhütte", "amenity": "shelter"},
        }]
    }
    results = _parse_overpass_response(raw, ref_lat=47.3, ref_lon=11.4)
    assert len(results) == 1
    assert results[0]["type"] == "shelter"
```

- [ ] **Step 2: Run tests to verify they fail**

```
uv run pytest tests/test_services/test_poi_enricher.py::TestParseOverpassResponse -v
```
Expected: Two new tests FAIL

- [ ] **Step 3: Write minimal implementation**

Replace the `_parse_overpass_response` function (lines 33-81):

```python
def _parse_overpass_response(
    data: Dict[str, Any],
    ref_lat: float,
    ref_lon: float,
) -> List[Dict[str, Any]]:
    """Parst Overpass JSON-Antwort in POI-Dicts mit Distanzberechnung."""
    results = []
    for element in data.get("elements", []):
        tags = element.get("tags", {})

        # POI-Typ bestimmen — alle Kategorien aus OVERPASS_POI_CATEGORIES prüfen
        poi_type = "unknown"
        for tag_key in OVERPASS_POI_CATEGORIES:
            if tag_key in tags:
                poi_type = tags[tag_key]
                break

        if poi_type == "unknown":
            continue

        # Koordinaten: nodes direkt, ways über center
        if element.get("type") == "node":
            el_lat = element.get("lat", ref_lat)
            el_lon = element.get("lon", ref_lon)
        elif element.get("type") == "way":
            center = element.get("center", {})
            el_lat = center.get("lat", ref_lat)
            el_lon = center.get("lon", ref_lon)
        else:
            continue

        name = tags.get("name", f"{poi_type} ({el_lat:.3f}, {el_lon:.3f})")

        # Distanz berechnen (Haversine-Approximation)
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

        wiki_tag = tags.get("wikipedia")
        if wiki_tag:
            poi["wiki_tag"] = wiki_tag

        results.append(poi)

    return results
```

- [ ] **Step 4: Run tests to verify they pass**

```
uv run pytest tests/test_services/test_poi_enricher.py::TestParseOverpassResponse -v
```
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_services/test_poi_enricher.py app/services/poi_enricher.py
git commit -m "feat: parse way elements and all category keys in POI response"
```

---

### Task 4: Multi-instance retry with exponential backoff

**Files:**
- Modify: `app/services/poi_enricher.py` (add helper function, refactor `fetch_pois` call logic)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_services/test_poi_enricher.py — neue Test-Klasse

class TestOverpassRetry:
    def test_retries_on_406_and_falls_back_to_next_instance(self):
        import requests as real_requests

        fails = Mock()
        fails.status_code = 406
        falls_fails = Mock()
        falls_fails.status_code = 406
        success = Mock()
        success.status_code = 200
        success.json.return_value = {"elements": []}

        responses = [fails, falls_fails, success]

        def mock_post(url, *args, **kwargs):
            return responses.pop(0)

        from datetime import datetime
        pauses = [{"location": {"lat": 47.3, "lon": 11.4}}]
        with patch("app.services.poi_enricher.requests.post", side_effect=mock_post):
            with patch("app.services.poi_enricher.time.sleep", return_value=None):
                result = fetch_pois(pauses=pauses)

        assert result == []

    def test_retries_with_exponential_backoff(self):
        fails = Mock()
        fails.status_code = 503
        success = Mock()
        success.status_code = 200
        success.json.return_value = {"elements": []}

        responses = [fails, success]
        sleep_times = []

        def mock_post(url, *args, **kwargs):
            return responses.pop(0)

        def mock_sleep(seconds):
            sleep_times.append(seconds)

        from datetime import datetime
        pauses = [{"location": {"lat": 47.3, "lon": 11.4}}]
        with patch("app.services.poi_enricher.requests.post", side_effect=mock_post):
            with patch("app.services.poi_enricher.time.sleep", side_effect=mock_sleep):
                fetch_pois(pauses=pauses)

        assert sleep_times[0] == 1  # erster Retry nach 1s
```

- [ ] **Step 2: Run tests to verify they fail**

```
uv run pytest tests/test_services/test_poi_enricher.py::TestOverpassRetry -v
```
Expected: FAIL (current code handles only 429, not 406/503)

- [ ] **Step 3: Write minimal implementation**

Add after the constants section (after `PROXIMITY_DEDUP_M = 500`):

```python
MAX_RETRIES = 3
RETRY_BACKOFF = [1, 2, 4]  # Sekunden


def _try_overpass_query(query: str) -> Optional[List[Dict[str, Any]]]:
    """Sendet eine Overpass-Query mit Retry und Instanz-Fallback.

    Probiert alle Instanzen mit exponentiellem Backoff.
    Gibt None zurück wenn keine Instanz erreichbar ist.
    """
    request_headers = {
        "Content-Type": "text/plain",
        "Accept": "application/json",
        "User-Agent": "TravelBlogBot/1.0",
    }

    for attempt in range(MAX_RETRIES + 1):
        instance_idx = attempt % len(OVERPASS_INSTANCES)
        url = OVERPASS_INSTANCES[instance_idx]

        try:
            resp = requests.post(
                url,
                data=query.encode("utf-8"),
                headers=request_headers,
                timeout=30,
            )
        except Exception as e:
            print(f"⚠️ Overpass {url} nicht erreichbar: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF[min(attempt, len(RETRY_BACKOFF) - 1)])
            continue

        if resp.status_code == 200:
            try:
                return resp.json().get("elements", [])
            except Exception:
                print(f"⚠️ Ungültiges JSON von {url}")
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_BACKOFF[min(attempt, len(RETRY_BACKOFF) - 1)])
                continue

        print(f"⚠️ Overpass {url} antwortete mit {resp.status_code}")
        if attempt < MAX_RETRIES:
            time.sleep(RETRY_BACKOFF[min(attempt, len(RETRY_BACKOFF) - 1)])

    return None
```

Now replace the API-call block in `fetch_pois` (lines 169-203). The old block:

```python
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
```

Becomes:

```python
        query = _build_overpass_query(lat, lon, search_radius_m)
        elements = _try_overpass_query(query)
        if elements:
            pois = _parse_overpass_response({"elements": elements}, lat, lon)
            all_pois.extend(pois)
```

Remove the `import requests` at module level since `_try_overpass_query` imports it internally. Actually keep it — it's used by `_enrich_with_wikipedia` too.

- [ ] **Step 4: Run tests to verify they pass**

```
uv run pytest tests/test_services/test_poi_enricher.py::TestOverpassRetry -v
```
Expected: PASS

Also run existing Overpass/FetchPois tests:
```
uv run pytest tests/test_services/test_poi_enricher.py::TestFetchPois -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_services/test_poi_enricher.py app/services/poi_enricher.py
git commit -m "feat: multi-instance retry with exponential backoff for Overpass"
```

---

### Task 5: File-based POI cache

**Files:**
- Modify: `app/services/poi_enricher.py` (add cache functions)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_services/test_poi_enricher.py — neue Test-Klasse

class TestPoiCache:
    def test_cache_hit_returns_cached_pois(self, tmp_path):
        from app.services.poi_enricher import _load_cache, _save_to_cache, _get_cache_key

        cache_file = tmp_path / "poi_cache.json"
        key = _get_cache_key(47.3, 11.4, 2000)
        dummy_pois = [{"name": "Test", "type": "peak", "lat": 47.3, "lon": 11.4}]
        _save_to_cache(key, dummy_pois, cache_file)

        cache = _load_cache(cache_file)
        assert cache[key] == dummy_pois

    def test_cache_miss_returns_none(self, tmp_path):
        from app.services.poi_enricher import _load_cache, _get_cache_key

        cache_file = tmp_path / "nonexistent.json"
        key = _get_cache_key(99.0, 99.0, 2000)
        cache = _load_cache(cache_file)
        assert key not in cache
```

- [ ] **Step 2: Run tests to verify they fail**

```
uv run pytest tests/test_services/test_poi_enricher.py::TestPoiCache -v
```
Expected: FAIL (ImportError — functions not defined)

- [ ] **Step 3: Write minimal implementation**

Add these functions in `app/services/poi_enricher.py`, after `PROXIMITY_DEDUP_M`:

```python
import json
from pathlib import Path

POI_CACHE_PATH = Path("output/poi_cache.json")


def _get_cache_key(lat: float, lon: float, radius: int) -> str:
    """Erzeugt einen Cache-Key aus Koordinaten und Radius."""
    return f"{lat:.4f}_{lon:.4f}_{radius}"


def _load_cache(cache_path: Path = POI_CACHE_PATH) -> Dict[str, Any]:
    """Lädt den POI-Cache aus der JSON-Datei."""
    try:
        if cache_path.exists():
            with open(cache_path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        print(f"⚠️ Cache-Datei konnte nicht geladen werden: {e}")
    return {}


def _save_to_cache(key: str, pois: List[Dict[str, Any]], cache_path: Path = POI_CACHE_PATH):
    """Speichert POIs für einen Key im Cache."""
    try:
        cache = _load_cache(cache_path)
        cache[key] = pois
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ Cache konnte nicht gespeichert werden: {e}")
```

Now integrate cache into `fetch_pois`. Replace the loop body (lines 163-205) with:

```python
    cache = _load_cache()

    for pause in pauses:
        loc = pause.get("location", {})
        lat, lon = loc.get("lat"), loc.get("lon")
        if lat is None or lon is None:
            continue

        cache_key = _get_cache_key(lat, lon, search_radius_m)

        # Cache-Check
        if cache_key in cache:
            all_pois.extend(cache[cache_key])
            continue

        query = _build_overpass_query(lat, lon, search_radius_m)
        elements = _try_overpass_query(query)
        if elements:
            pois = _parse_overpass_response({"elements": elements}, lat, lon)
            _save_to_cache(cache_key, pois)
            all_pois.extend(pois)
        else:
            print(f"⚠️ Keine POI-Daten für ({lat}, {lon})")
```

- [ ] **Step 4: Run tests to verify they pass**

```
uv run pytest tests/test_services/test_poi_enricher.py::TestPoiCache -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_services/test_poi_enricher.py app/services/poi_enricher.py
git commit -m "feat: add file-based POI cache with JSON persistence"
```

---

### Task 6: Full test suite verification and cleanup

**Files:**
- Run: full test suite
- Verify: no regression in node-level tests

- [ ] **Step 1: Run all POI service tests**

```
uv run pytest tests/test_services/test_poi_enricher.py -v
```
Expected: ALL PASS

- [ ] **Step 2: Run node-level POI tests**

```
uv run pytest tests/test_nodes/test_enrich_poi.py -v
```
Expected: ALL PASS

- [ ] **Step 3: Run enrichment graph tests**

```
uv run pytest tests/test_graph/test_enrichment_graph.py -v
```
Expected: ALL PASS

- [ ] **Step 4: Run enrichment E2E tests**

```
uv run pytest tests/test_api/test_enrichment_e2e.py -v
```
Expected: ALL PASS (fixtures are mocked, don't call real Overpass)

- [ ] **Step 5: Run full test suite**

```
uv run pytest -v
```
Expected: All tests pass

- [ ] **Step 6: Commit final state (only if changes were needed from test fixes)**

```bash
git add . && git commit -m "test: verify full test suite passes after POI enrichment changes"
```
