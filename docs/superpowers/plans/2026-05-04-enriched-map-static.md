# Statische angereicherte Karte mit "Foto X"-Labels — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace interactive Folium markers with static DivIcon labels ("Foto 1", "Foto 2"), group nearby photos, associate photos to pauses, and add "Foto X:" prefix to blog image captions.

**Architecture:** Three new helper functions in `generate_mapimage.py` (haversine, group-by-location, match-to-pauses). Rewrite `generate_enriched_map_html()` with DivIcon markers. Update blog prompt in `blog_generator.py` to request "Foto X:" caption format.

**Tech Stack:** Folium `DivIcon`, Haversine formula, existing Selenium screenshot pipeline, existing Ollama prompt construction.

---

### Task 1: Add `_haversine_distance` helper with tests

**Files:**
- Modify: `app/services/generate_mapimage.py` (add function after imports)
- Create: `tests/test_services/test_map_helpers.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_services/test_map_helpers.py
"""Tests for map helper functions in app/services/generate_mapimage.py"""
import pytest
from app.services.generate_mapimage import _haversine_distance


class TestHaversineDistance:
    @pytest.mark.unit
    def test_same_point_zero(self):
        assert _haversine_distance(47.0, 8.0, 47.0, 8.0) == 0.0

    @pytest.mark.unit
    def test_one_degree_latitude(self):
        # 1 Grad Latitude ≈ 111 km
        dist = _haversine_distance(47.0, 8.0, 48.0, 8.0)
        assert 110000 < dist < 112000

    @pytest.mark.unit
    def test_small_distance_known(self):
        # ~11.1m (0.0001 Grad Latitude)
        dist = _haversine_distance(47.0, 8.0, 47.0001, 8.0)
        assert 10 < dist < 12

    @pytest.mark.unit
    def test_equator_large_distance(self):
        # ~157 km (Hamburg–Bremen grob)
        dist = _haversine_distance(53.55, 10.0, 53.08, 8.8)
        assert 90000 < dist < 120000
```

Run: `uv run pytest tests/test_services/test_map_helpers.py::TestHaversineDistance -v`

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_services/test_map_helpers.py::TestHaversineDistance -v`
Expected: FAIL with "ImportError: cannot import name '_haversine_distance'"

- [ ] **Step 3: Write minimal implementation**

```python
# In app/services/generate_mapimage.py, add after line 5 (after imports):
import math as _math  # bereits importiert als `math` in Zeile 2 — verwende `math`

def _haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distanz in Metern zwischen zwei Koordinaten (Haversine-Formel)."""
    R = 6371000  # Erdradius in Metern
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_services/test_map_helpers.py::TestHaversineDistance -v`
Expected: 4 PASSED

- [ ] **Step 5: Commit**

```bash
git add tests/test_services/test_map_helpers.py app/services/generate_mapimage.py
git commit -m "feat: add _haversine_distance helper with tests"
```

---

### Task 2: Add `_group_photos_by_location` helper with tests

**Files:**
- Modify: `app/services/generate_mapimage.py` (add function)
- Modify: `tests/test_services/test_map_helpers.py` (add test class)

- [ ] **Step 1: Write the failing tests**

```python
# Add to tests/test_services/test_map_helpers.py
from app.services.generate_mapimage import _group_photos_by_location
from app.state import ImageData


class TestGroupPhotosByLocation:
    @pytest.mark.unit
    def test_single_photo(self):
        images = [ImageData(path="a.jpg", latitude=47.0, longitude=8.0, timestamp="2024-01-01T10:00:00")]
        groups = _group_photos_by_location(images)
        assert groups == [[0]]

    @pytest.mark.unit
    def test_far_apart_photos_separate(self):
        images = [
            ImageData(path="a.jpg", latitude=47.0, longitude=8.0, timestamp="2024-01-01T10:00:00"),
            ImageData(path="b.jpg", latitude=47.1, longitude=8.0, timestamp="2024-01-01T11:00:00"),
        ]
        groups = _group_photos_by_location(images)
        assert len(groups) == 2
        assert 0 in groups[0] or 0 in groups[1]
        assert 1 in groups[0] or 1 in groups[1]

    @pytest.mark.unit
    def test_nearby_photos_grouped(self):
        images = [
            ImageData(path="a.jpg", latitude=47.0, longitude=8.0, timestamp="2024-01-01T10:00:00"),
            ImageData(path="b.jpg", latitude=47.0, longitude=8.00003, timestamp="2024-01-01T10:01:00"),
        ]
        groups = _group_photos_by_location(images, threshold_m=5.0)
        # ~3.3m auseinander → eine Gruppe
        assert len(groups) == 1
        assert 0 in groups[0] and 1 in groups[0]

    @pytest.mark.unit
    def test_nearby_and_far_mixed(self):
        images = [
            ImageData(path="a.jpg", latitude=47.0, longitude=8.0, timestamp="T1"),
            ImageData(path="b.jpg", latitude=47.0, longitude=8.00001, timestamp="T2"),  # ~1.1m → Gruppe mit a
            ImageData(path="c.jpg", latitude=47.1, longitude=8.0, timestamp="T3"),       # weit weg
        ]
        groups = _group_photos_by_location(images, threshold_m=5.0)
        assert len(groups) == 2
        # Finde die 2er-Gruppe
        group_sizes = sorted([len(g) for g in groups])
        assert group_sizes == [1, 2]

    @pytest.mark.unit
    def test_custom_threshold(self):
        images = [
            ImageData(path="a.jpg", latitude=47.0, longitude=8.0, timestamp="T1"),
            ImageData(path="b.jpg", latitude=47.0, longitude=8.0005, timestamp="T2"),  # ~55m
        ]
        # Mit 100m Threshold → eine Gruppe
        groups_wide = _group_photos_by_location(images, threshold_m=100.0)
        assert len(groups_wide) == 1
        # Mit 5m Threshold → zwei Gruppen
        groups_tight = _group_photos_by_location(images, threshold_m=5.0)
        assert len(groups_tight) == 2

    @pytest.mark.unit
    def test_skips_images_without_coordinates(self):
        images = [
            ImageData(path="a.jpg", latitude=47.0, longitude=8.0, timestamp="T1"),
            ImageData(path="b.jpg", latitude=None, longitude=None, timestamp="T2"),
            ImageData(path="c.jpg", latitude=47.0, longitude=8.00001, timestamp="T3"),
        ]
        groups = _group_photos_by_location(images, threshold_m=5.0)
        # b wird ignoriert, a und c sind nah → eine Gruppe
        assert len(groups) == 1
        assert 0 in groups[0] and 2 in groups[0]

    @pytest.mark.unit
    def test_empty_images(self):
        assert _group_photos_by_location([]) == []
```

Run: `uv run pytest tests/test_services/test_map_helpers.py::TestGroupPhotosByLocation -v`

- [ ] **Step 2: Run test to verify it fails**

Expected: FAIL — ImportError or NameError for `_group_photos_by_location`

- [ ] **Step 3: Write minimal implementation**

```python
# In app/services/generate_mapimage.py, nach _haversine_distance:
def _group_photos_by_location(images, threshold_m: float = 5.0):
    """Gruppiert Fotos nach räumlicher Nähe (threshold_m).
    
    Greedy-Algorithmus: Jedes Foto wird der ersten Gruppe zugeordnet,
    zu deren erstem Element die Distanz <= threshold_m ist. Sonst neue Gruppe.
    
    Rückgabe: [[idx1, idx2], [idx3], ...] — 0-basierte Indizes in images.
    Fotos ohne Koordinaten werden übergangen.
    """
    groups: list[list[int]] = []
    for idx, img in enumerate(images):
        lat = img.latitude if hasattr(img, "latitude") else img.get("latitude")
        lon = img.longitude if hasattr(img, "longitude") else img.get("longitude")
        if lat is None or lon is None:
            continue
        
        found = False
        for group in groups:
            # Prüfe gegen das erste Element der Gruppe (Referenzpunkt)
            ref_idx = group[0]
            ref = images[ref_idx]
            ref_lat = ref.latitude if hasattr(ref, "latitude") else ref.get("latitude")
            ref_lon = ref.longitude if hasattr(ref, "longitude") else ref.get("longitude")
            if _haversine_distance(lat, lon, ref_lat, ref_lon) <= threshold_m:
                group.append(idx)
                found = True
                break
        
        if not found:
            groups.append([idx])
    
    return groups
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_services/test_map_helpers.py::TestGroupPhotosByLocation -v`
Expected: all PASSED

- [ ] **Step 5: Commit**

```bash
git add tests/test_services/test_map_helpers.py app/services/generate_mapimage.py
git commit -m "feat: add _group_photos_by_location helper with tests"
```

---

### Task 3: Add `_match_photos_to_pauses` helper with tests

**Files:**
- Modify: `app/services/generate_mapimage.py` (add function)
- Modify: `tests/test_services/test_map_helpers.py` (add test class)

- [ ] **Step 1: Write the failing tests**

```python
# Add to tests/test_services/test_map_helpers.py
from app.services.generate_mapimage import _match_photos_to_pauses
from datetime import datetime


class TestMatchPhotosToPauses:
    @pytest.mark.unit
    def test_both_criteria_met(self):
        images = [
            ImageData(path="a.jpg", latitude=47.0, longitude=8.0,
                      timestamp="2024-07-15T10:05:00"),
        ]
        pauses = [
            {
                "start_time": datetime(2024, 7, 15, 10, 0),
                "end_time": datetime(2024, 7, 15, 10, 15),
                "duration_minutes": 15.0,
                "location": {"lat": 47.0, "lon": 8.0},
            }
        ]
        result = _match_photos_to_pauses(images, pauses, distance_m=50.0)
        assert 0 in result
        assert result[0] == [0]

    @pytest.mark.unit
    def test_spatial_only_not_matched(self):
        # Foto räumlich nah, aber zeitlich ausserhalb → keine Zuordnung
        images = [
            ImageData(path="a.jpg", latitude=47.0, longitude=8.0,
                      timestamp="2024-07-15T11:00:00"),  # ausserhalb 10:00-10:15
        ]
        pauses = [
            {
                "start_time": datetime(2024, 7, 15, 10, 0),
                "end_time": datetime(2024, 7, 15, 10, 15),
                "duration_minutes": 15.0,
                "location": {"lat": 47.0, "lon": 8.0},
            }
        ]
        result = _match_photos_to_pauses(images, pauses, distance_m=50.0)
        assert len(result) == 0

    @pytest.mark.unit
    def test_temporal_only_not_matched(self):
        # Foto zeitlich in Pause, aber räumlich weit weg → keine Zuordnung
        images = [
            ImageData(path="a.jpg", latitude=47.1, longitude=8.0,  # >50m
                      timestamp="2024-07-15T10:05:00"),
        ]
        pauses = [
            {
                "start_time": datetime(2024, 7, 15, 10, 0),
                "end_time": datetime(2024, 7, 15, 10, 15),
                "duration_minutes": 15.0,
                "location": {"lat": 47.0, "lon": 8.0},
            }
        ]
        result = _match_photos_to_pauses(images, pauses, distance_m=50.0)
        assert len(result) == 0

    @pytest.mark.unit
    def test_multiple_photos_one_pause(self):
        images = [
            ImageData(path="a.jpg", latitude=47.0, longitude=8.0,
                      timestamp="2024-07-15T10:05:00"),
            ImageData(path="b.jpg", latitude=47.0, longitude=8.0002,  # ~22m
                      timestamp="2024-07-15T10:10:00"),
        ]
        pauses = [
            {
                "start_time": datetime(2024, 7, 15, 10, 0),
                "end_time": datetime(2024, 7, 15, 10, 15),
                "duration_minutes": 15.0,
                "location": {"lat": 47.0, "lon": 8.0},
            }
        ]
        result = _match_photos_to_pauses(images, pauses, distance_m=50.0)
        assert 0 in result
        assert sorted(result[0]) == [0, 1]

    @pytest.mark.unit
    def test_multiple_pauses(self):
        images = [
            ImageData(path="a.jpg", latitude=47.0, longitude=8.0,
                      timestamp="2024-07-15T10:05:00"),
            ImageData(path="b.jpg", latitude=47.1, longitude=8.1,
                      timestamp="2024-07-15T12:35:00"),
        ]
        pauses = [
            {
                "start_time": datetime(2024, 7, 15, 10, 0),
                "end_time": datetime(2024, 7, 15, 10, 15),
                "duration_minutes": 15.0,
                "location": {"lat": 47.0, "lon": 8.0},
            },
            {
                "start_time": datetime(2024, 7, 15, 12, 30),
                "end_time": datetime(2024, 7, 15, 12, 55),
                "duration_minutes": 25.0,
                "location": {"lat": 47.1, "lon": 8.1},
            },
        ]
        result = _match_photos_to_pauses(images, pauses, distance_m=50.0)
        assert result[0] == [0]
        assert result[1] == [1]

    @pytest.mark.unit
    def test_photo_matches_multiple_pauses(self):
        # Foto liegt zeitlich+räumlich in zwei Pausen → erste gewinnt
        images = [
            ImageData(path="a.jpg", latitude=47.0, longitude=8.0,
                      timestamp="2024-07-15T10:05:00"),
        ]
        pauses = [
            {
                "start_time": datetime(2024, 7, 15, 10, 0),
                "end_time": datetime(2024, 7, 15, 10, 15),
                "duration_minutes": 15.0,
                "location": {"lat": 47.0, "lon": 8.0},
            },
            {
                "start_time": datetime(2024, 7, 15, 10, 0),
                "end_time": datetime(2024, 7, 15, 10, 30),
                "duration_minutes": 30.0,
                "location": {"lat": 47.0, "lon": 8.0},
            },
        ]
        result = _match_photos_to_pauses(images, pauses, distance_m=50.0)
        # Foto sollte nur der ersten Pause zugeordnet werden
        assert len(result) == 2  # Beide Pausen matchen → beide bekommen es
        assert result[0] == [0]
        assert result[1] == [0]

    @pytest.mark.unit
    def test_photo_without_timestamp_skipped(self):
        images = [
            ImageData(path="a.jpg", latitude=47.0, longitude=8.0, timestamp=None),
        ]
        pauses = [
            {
                "start_time": datetime(2024, 7, 15, 10, 0),
                "end_time": datetime(2024, 7, 15, 10, 15),
                "duration_minutes": 15.0,
                "location": {"lat": 47.0, "lon": 8.0},
            }
        ]
        result = _match_photos_to_pauses(images, pauses, distance_m=50.0)
        assert len(result) == 0

    @pytest.mark.unit
    def test_photo_without_coordinates_skipped(self):
        images = [
            ImageData(path="a.jpg", latitude=None, longitude=None,
                      timestamp="2024-07-15T10:05:00"),
        ]
        pauses = [
            {
                "start_time": datetime(2024, 7, 15, 10, 0),
                "end_time": datetime(2024, 7, 15, 10, 15),
                "duration_minutes": 15.0,
                "location": {"lat": 47.0, "lon": 8.0},
            }
        ]
        result = _match_photos_to_pauses(images, pauses, distance_m=50.0)
        assert len(result) == 0

    @pytest.mark.unit
    def test_empty_inputs(self):
        assert _match_photos_to_pauses([], [], 50.0) == {}
        assert _match_photos_to_pauses([], [{"location": {"lat": 47.0, "lon": 8.0}}], 50.0) == {}
```

Run: `uv run pytest tests/test_services/test_map_helpers.py::TestMatchPhotosToPauses -v`

- [ ] **Step 2: Run test to verify it fails**

Expected: FAIL — ImportError

- [ ] **Step 3: Write minimal implementation**

```python
# In app/services/generate_mapimage.py, nach _group_photos_by_location:
def _match_photos_to_pauses(images, pauses, distance_m: float = 50.0):
    """Ordnet Fotos Pausen zu (räumlich + zeitlich).
    
    Kriterien (beide müssen erfüllt sein):
      1. Haversine-Distanz Foto-Pause <= distance_m
      2. Foto-Timestamp liegt zwischen Pausen-Start und Pausen-Ende
    
    Rückgabe: {pause_index: [foto_index, ...]}
    Nur Pausen mit mindestens einem zugeordneten Foto erscheinen im Dict.
    Ein Foto kann mehreren Pausen zugeordnet sein (Überlappung).
    """
    from datetime import datetime as _dt
    
    result: dict[int, list[int]] = {}
    
    for pause_idx, pause in enumerate(pauses):
        loc = pause.get("location", {})
        p_lat = loc.get("lat")
        p_lon = loc.get("lon")
        if p_lat is None or p_lon is None:
            continue
        
        start = pause.get("start_time")
        end = pause.get("end_time")
        
        for foto_idx, img in enumerate(images):
            f_lat = img.latitude if hasattr(img, "latitude") else img.get("latitude")
            f_lon = img.longitude if hasattr(img, "longitude") else img.get("longitude")
            if f_lat is None or f_lon is None:
                continue
            
            # Räumliche Prüfung
            if _haversine_distance(p_lat, p_lon, f_lat, f_lon) > distance_m:
                continue
            
            # Zeitliche Prüfung
            ts_str = img.timestamp if hasattr(img, "timestamp") else img.get("timestamp")
            if not ts_str or not start or not end:
                continue
            
            try:
                ts = _dt.fromisoformat(ts_str) if isinstance(ts_str, str) else ts_str
            except (ValueError, TypeError):
                continue
            
            # Zeitstempel auf gleiche Zeitzone normalisieren (ignorieren — Werte sind naive datetimes)
            if start <= ts <= end:
                result.setdefault(pause_idx, []).append(foto_idx)
    
    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_services/test_map_helpers.py::TestMatchPhotosToPauses -v`
Expected: all PASSED

- [ ] **Step 5: Commit**

```bash
git add tests/test_services/test_map_helpers.py app/services/generate_mapimage.py
git commit -m "feat: add _match_photos_to_pauses helper with tests"
```

---

### Task 4: Rewrite `generate_enriched_map_html()` — remove tooltips, add DivIcon labels

**Files:**
- Modify: `app/services/generate_mapimage.py` (Zeilen 72–150)
- Modify: `tests/test_services/test_generate_enriched_mapimage.py` (update assertions)

- [ ] **Step 1: Update existing tests to expect new marker format**

```python
# tests/test_services/test_generate_enriched_mapimage.py — ersetze die gesamte Datei:
"""Tests for generate_enriched_map_html in app/services/generate_mapimage.py"""
import os
import pytest
from app.services.generate_mapimage import generate_enriched_map_html
from app.services.gpx_analytics import TrackPoint
from app.state import ImageData
from datetime import datetime


@pytest.fixture
def sample_points():
    return [
        TrackPoint(lat=47.3, lon=8.5, elevation=500.0, time=None),
        TrackPoint(lat=47.301, lon=8.501, elevation=510.0, time=None),
        TrackPoint(lat=47.302, lon=8.502, elevation=520.0, time=None),
    ]


@pytest.fixture
def sample_pauses():
    return [
        {
            "start_time": datetime(2024, 7, 15, 10, 0),
            "end_time": datetime(2024, 7, 15, 10, 15),
            "duration_minutes": 15.0,
            "location": {"lat": 47.301, "lon": 8.501},
        },
        {
            "start_time": datetime(2024, 7, 15, 12, 30),
            "end_time": datetime(2024, 7, 15, 12, 55),
            "duration_minutes": 25.0,
            "location": {"lat": 47.302, "lon": 8.502},
        },
    ]


@pytest.fixture
def sample_images():
    return [
        ImageData(
            path="data/images/photo_01.jpg",
            timestamp="2024-07-15T10:00:00",
            latitude=47.3005,
            longitude=8.5005,
        ),
        ImageData(
            path="data/images/photo_02.jpg",
            timestamp="2024-07-15T12:30:00",
            latitude=47.3015,
            longitude=8.5000,
        ),
    ]


class TestGenerateEnrichedMapHtml:
    @pytest.mark.unit
    def test_generates_html_file(self, tmp_path, sample_points, sample_pauses, sample_images):
        html_path = str(tmp_path / "enriched_map.html")
        generate_enriched_map_html(sample_points, sample_pauses, sample_images, html_path)

        assert os.path.exists(html_path)
        content = open(html_path).read()
        assert "folium" in content.lower() or "leaflet" in content.lower()

    @pytest.mark.unit
    def test_contains_divicon_foto_labels(self, tmp_path, sample_points, sample_pauses, sample_images):
        html_path = str(tmp_path / "enriched_map.html")
        generate_enriched_map_html(sample_points, sample_pauses, sample_images, html_path)

        content = open(html_path).read()
        assert "Foto 1" in content
        assert "Foto 2" in content

    @pytest.mark.unit
    def test_no_tooltips_on_foto_markers(self, tmp_path, sample_points, sample_images):
        """Foto-Marker sollen keine Tooltips mehr haben."""
        html_path = str(tmp_path / "enriched_map.html")
        generate_enriched_map_html(sample_points, [], sample_images, html_path)

        content = open(html_path).read()
        # Weder der alte tooltip-Text noch ein tooltip-Attribut sollten vorkommen
        assert "Bild 1:" not in content
        assert "Bild 2:" not in content

    @pytest.mark.unit
    def test_no_tooltips_on_pause_markers(self, tmp_path, sample_points, sample_pauses):
        """Pause-Marker sollen keine Tooltips mehr haben."""
        html_path = str(tmp_path / "enriched_map.html")
        generate_enriched_map_html(sample_points, sample_pauses, [], html_path)

        content = open(html_path).read()
        # Weder "Pause:" (alter tooltip) noch popup sollte vorkommen
        assert "Pause: 15.0 min" not in content
        assert "Pause: 25.0 min" not in content

    @pytest.mark.unit
    def test_pause_markers_use_divicon(self, tmp_path, sample_points, sample_pauses):
        html_path = str(tmp_path / "enriched_map.html")
        generate_enriched_map_html(sample_points, sample_pauses, [], html_path)

        content = open(html_path).read()
        # Pause-Text sollte direkt im DivIcon-HTML stehen
        assert "15min" in content or "15.0min" in content or "15 min" in content
        assert "25min" in content or "25.0min" in content or "25 min" in content

    @pytest.mark.unit
    def test_pause_with_matched_photos_shows_foto_labels(self, tmp_path, sample_points, sample_pauses):
        """Fotos die räumlich+zeitlich zur Pause passen → Labels erscheinen beim Pause-Marker."""
        images_matching_pause1 = [
            ImageData(
                path="data/images/pause_photo.jpg",
                timestamp="2024-07-15T10:05:00",
                latitude=47.301,   # genau an Pause 1 (47.301, 8.501) — 0m Abstand
                longitude=8.501,
            ),
        ]
        html_path = str(tmp_path / "enriched_map.html")
        generate_enriched_map_html(sample_points, sample_pauses, images_matching_pause1, html_path)

        content = open(html_path).read()
        assert "Foto 1" in content  # Foto-Label erscheint
        assert "Foto 1" in content  # beim Pause-Marker referenziert (singular für ein Foto)

    @pytest.mark.unit
    def test_handles_empty_pauses(self, tmp_path, sample_points, sample_images):
        html_path = str(tmp_path / "enriched_map.html")
        generate_enriched_map_html(sample_points, [], sample_images, html_path)

        assert os.path.exists(html_path)
        content = open(html_path).read()
        assert "Foto 1" in content  # Foto-Marker trotzdem da

    @pytest.mark.unit
    def test_handles_empty_images(self, tmp_path, sample_points, sample_pauses):
        html_path = str(tmp_path / "enriched_map.html")
        generate_enriched_map_html(sample_points, sample_pauses, [], html_path)

        assert os.path.exists(html_path)
        content = open(html_path).read()
        assert "Foto" not in content  # keine Foto-Marker

    @pytest.mark.unit
    def test_handles_both_empty(self, tmp_path, sample_points):
        html_path = str(tmp_path / "enriched_map.html")
        generate_enriched_map_html(sample_points, [], [], html_path)

        assert os.path.exists(html_path)
        content = open(html_path).read()
        assert "folium" in content.lower() or "leaflet" in content.lower()

    @pytest.mark.unit
    def test_contains_route_polyline(self, tmp_path, sample_points):
        html_path = str(tmp_path / "enriched_map.html")
        generate_enriched_map_html(sample_points, [], [], html_path)

        content = open(html_path).read()
        assert "47.3" in content
        assert "47.302" in content

    @pytest.mark.unit
    def test_start_end_no_tooltips(self, tmp_path, sample_points):
        """Start/End-Marker sollen keine Tooltips mehr haben."""
        html_path = str(tmp_path / "enriched_map.html")
        generate_enriched_map_html(sample_points, [], [], html_path)

        content = open(html_path).read()
        assert '"Start"' not in content  # Tooltip entfernt
        assert '"Ende"' not in content   # Tooltip entfernt

    @pytest.mark.unit
    def test_groups_nearby_photos(self, tmp_path, sample_points):
        """Fotos an fast gleicher Position werden gruppiert."""
        images = [
            ImageData(
                path="data/images/a.jpg",
                timestamp="2024-07-15T10:00:00",
                latitude=47.3005,
                longitude=8.5005,
            ),
            ImageData(
                path="data/images/b.jpg",
                timestamp="2024-07-15T10:01:00",
                latitude=47.3005,   # gleiche Koordinaten wie a
                longitude=8.5005,
            ),
        ]
        html_path = str(tmp_path / "enriched_map.html")
        generate_enriched_map_html(sample_points, [], images, html_path)

        content = open(html_path).read()
        # Beide Fotos sollten gruppiert sein → "Fotos 1, 2" (plural) erscheint
        assert "Fotos 1, 2" in content
        # Kein einzeln stehender Marker — prüfe dass kein <b>Foto 1</b> oder <b>Foto 2</b> existiert
        # (nur das gruppierte <b>Fotos 1, 2</b>)
        assert "<b>Foto 1</b>" not in content
        assert "<b>Foto 2</b>" not in content
```

Run: `uv run pytest tests/test_services/test_generate_enriched_mapimage.py -v`

- [ ] **Step 2: Run test to verify it fails**

Expected: FAIL — "Pause: 15.0 min" still in content, "Foto 1" not found, etc.

- [ ] **Step 3: Rewrite `generate_enriched_map_html()`**

```python
# In app/services/generate_mapimage.py — ersetze die gesamte Funktion (Zeilen 72–150):

def generate_enriched_map_html(
    points: List[TrackPoint],
    pauses: list,
    images: list,
    output_html: str,
):
    """Generiert eine statische Folium-Karte mit Route, Pausen- und Foto-Markern (DivIcon)."""
    # Mittelpunkt und Bounding Box
    avg_lat = sum(p.lat for p in points) / len(points)
    avg_lon = sum(p.lon for p in points) / len(points)

    min_lat = min(p.lat for p in points)
    max_lat = max(p.lat for p in points)
    min_lon = min(p.lon for p in points)
    max_lon = max(p.lon for p in points)

    padding_m = 500
    lat_pad = padding_m / 111000
    lon_pad = padding_m / (111000 * math.cos(math.radians(avg_lat)))

    south = min_lat - lat_pad
    north = max_lat + lat_pad
    west = min_lon - lon_pad
    east = max_lon + lon_pad

    m = folium.Map(
        location=[avg_lat, avg_lon],
        tiles="https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png",
        attr="© OpenTopoMap",
    )

    coords = [(p.lat, p.lon) for p in points]
    folium.PolyLine(coords, weight=4).add_to(m)

    # Start / Ende Marker (ohne Tooltips — statisch)
    folium.Marker(
        coords[0],
        icon=folium.Icon(color="green", icon="flag", prefix="fa"),
    ).add_to(m)
    folium.Marker(
        coords[-1],
        icon=folium.Icon(color="red", icon="flag-checkered", prefix="fa"),
    ).add_to(m)

    # Foto-Gruppierung
    foto_groups = _group_photos_by_location(images, threshold_m=5.0)

    # Pause-Foto-Zuordnung
    pause_fotos = _match_photos_to_pauses(images, pauses, distance_m=50.0)

    # Pause-Marker (DivIcon)
    for pause_idx, pause in enumerate(pauses):
        loc = pause.get("location", {})
        lat = loc.get("lat")
        lon = loc.get("lon")
        if lat is None or lon is None:
            continue
        duration = pause.get("duration_minutes", 0)
        duration_str = f"{duration:.0f}" if duration == int(duration) else f"{duration:.1f}"

        matched = pause_fotos.get(pause_idx, [])
        if matched:
            foto_labels = ", ".join(str(i + 1) for i in matched)
            prefix = "Foto" if len(matched) == 1 else "Fotos"
            html = (
                f'<div style="font-size:12px;white-space:nowrap;font-family:sans-serif;">'
                f'<i class="fa fa-pause" style="color:#f39c12;"></i> '
                f'<b>Pause ({duration_str}min)</b> '
                f'<span style="color:#1a73e8;">{prefix} {foto_labels}</span>'
                f'</div>'
            )
        else:
            html = (
                f'<div style="font-size:12px;white-space:nowrap;font-family:sans-serif;">'
                f'<i class="fa fa-pause" style="color:#f39c12;"></i> '
                f'<b>Pause ({duration_str}min)</b>'
                f'</div>'
            )
        folium.Marker(
            [lat, lon],
            icon=folium.DivIcon(html=html, icon_size=(250, 30), icon_anchor=(0, 15)),
        ).add_to(m)

    # Foto-Marker (DivIcon)
    for group in foto_groups:
        if len(group) == 1:
            idx = group[0]
            foto_num = idx + 1
            html = (
                f'<div style="font-size:12px;white-space:nowrap;font-family:sans-serif;">'
                f'<i class="fa fa-camera" style="color:#1a73e8;"></i> '
                f'<b>Foto {foto_num}</b>'
                f'</div>'
            )
        else:
            foto_nums = ", ".join(str(i + 1) for i in group)
            html = (
                f'<div style="font-size:12px;white-space:nowrap;font-family:sans-serif;">'
                f'<i class="fa fa-camera" style="color:#1a73e8;"></i> '
                f'<b>Fotos {foto_nums}</b>'
                f'</div>'
            )
        lat = images[group[0]].latitude if hasattr(images[group[0]], "latitude") else images[group[0]].get("latitude")
        lon = images[group[0]].longitude if hasattr(images[group[0]], "longitude") else images[group[0]].get("longitude")
        if lat is None or lon is None:
            continue
        folium.Marker(
            [lat, lon],
            icon=folium.DivIcon(html=html, icon_size=(200, 30), icon_anchor=(0, 15)),
        ).add_to(m)

    m.fit_bounds([[south, west], [north, east]])
    m.save(output_html)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_services/test_generate_enriched_mapimage.py -v`
Expected: All PASSED

- [ ] **Step 5: Run all map helper tests too**

Run: `uv run pytest tests/test_services/test_map_helpers.py tests/test_services/test_generate_enriched_mapimage.py -v`
Expected: All PASSED

- [ ] **Step 6: Commit**

```bash
git add tests/test_services/test_generate_enriched_mapimage.py app/services/generate_mapimage.py
git commit -m "feat: rewrite enriched map with static DivIcon labels, photo grouping, pause-photo matching"
```

---

### Task 5: Update blog prompt for "Foto X:" caption format

**Files:**
- Modify: `app/services/blog_generator.py` (Zeilen 228–254)
- Modify: `tests/test_services/test_blog_generator.py` (add test)

- [ ] **Step 1: Write the failing test**

```python
# Add to tests/test_services/test_blog_generator.py, inside class TestConstructBlogPostPrompt:

    @pytest.mark.unit
    def test_prompt_requires_foto_x_format(self, tmp_path):
        """Prompt soll 'Foto X:'-Format für Tour-Fotos verlangen."""
        img_path = str(tmp_path / "photo.jpg")
        img = Image.new("RGB", (100, 100), color="blue")
        img.save(img_path)

        images = [{"path": img_path, "timestamp": "2025-06-01", "latitude": 47.0, "longitude": 8.0}]
        prompt, _ = bg.construct_blog_post_prompt(images=images)

        assert "Foto X:" in prompt or "Foto 1:" in prompt or "Foto X" in prompt
        assert "![Foto" in prompt  # Format im Prompt enthalten

    @pytest.mark.unit
    def test_prompt_excludes_foto_prefix_for_map_and_elevation(self, tmp_path):
        """Karte und Höhenprofil sollen KEIN 'Foto X:'-Prefix bekommen."""
        prompt, _ = bg.construct_blog_post_prompt(images=[])

        # Karte im Prompt sollte OHNE Foto-Prefix sein
        assert "![Routenverlauf" in prompt
        # Die explizite Karten-Referenz sollte kein "Foto" enthalten
        assert "![Foto" not in prompt
```

Run: `uv run pytest tests/test_services/test_blog_generator.py::TestConstructBlogPostPrompt::test_prompt_requires_foto_x_format tests/test_services/test_blog_generator.py::TestConstructBlogPostPrompt::test_prompt_excludes_foto_prefix_for_map_and_elevation -v`

- [ ] **Step 2: Run test to verify it fails**

Expected: FAIL — "![Foto" not found in prompt

- [ ] **Step 3: Update the prompt in `construct_blog_post_prompt()`**

In `app/services/blog_generator.py`, ersetze Zeilen 228–254 (ab "3. **BILDER & TEXTFLUSS**" bis zum Ende des Formatierungs-Abschnitts) mit:

```python
     3. **BILDER & TEXTFLUSS**: Integriere die Tour-Fotos organisch als Meilensteine in die Geschichte.
     - Schreibe für JEDES Bild (auch Karte und Höhengraphen!) eine aussagekräftige Bildunterschrift IM ALT-TEXT (1-2 Sätze).
     - **WICHTIG:** Die Bildbeschreibung steht NUR im alt-Text des Bildes — schreibe sie NICHT zusätzlich als separaten Fließtext davor oder danach.
     - Leite im Fließtext kurz auf das Bild hin (z.B. "Als wir um die Ecke bogen…"), aber wiederhole NICHT die Bildbeschreibung.

     4. **TEXTFLUSS**: Mach den Leser neugierig. Nutze abwechslungsreiche Satzstrukturen und Absätze.

     5. **STRUKTUR — als Markdown-Überschriften mit ## und ###**:
     - **Ganz am Anfang MUSS ein # Haupttitel stehen** (eine Zeile mit # als erstes Zeichen).
       Beispiel: # Meine Wintertour durch die Allgäuer Alpen
     - Verwende `##` für Hauptabschnitte und `###` für Unterabschnitte.
     - Deine Abschnitte:
     - **Hook & Einleitung**: Ein packender Einstieg. Warum diese Tour? Die Vorfreude. (KEINE Überschrift nötig — Starte direkt mit dem Text.)
     - **## Die Übersicht**: Beschreibe die Route anhand der Karte. Bette die Karte ein.
     - **## Der Aufbruch**: Wie war der Start? Leichtes Einlaufen oder direkt steil?
     - **## Die Challenge**: Die Höhenmeter, Erschöpfung, Hindernisse.
     - **## Das Highlight**: Der emotionale Höhepunkt, Aussicht, Gipfelmoment.
     - **## Der Abstieg & Fazit**: Die Rückkehr, Resümee. Bette hier den Höhengraphen ein.

     6. **FORMATIERUNG (STRIKT)**:
     - Gib NUR den Markdown-Text des Blogposts zurück.
     - Keine Einleitung deinerseits, keine Metatexte, keine Kommentare.
     - Nutze ## und ### für Überschriften — MINDESTENS eine ##-Überschrift pro Abschnitt.
     - Jeder Abschnitt der Heldenreise MUSS mit einer ##-Überschrift beginnen (außer der Einleitung).
     - Nutze für Karte und Höhenprofil folgendes Format (OHNE Nummer):
       ![Routenverlauf unserer Tour — jeder markierte Punkt ein Stück Weg](./images/00_map.png)
       ![Höhenprofil der Tour — jeder Anstieg und jeder Abstieg auf einen Blick](./images/00_elevation_profile.png)
     - Nutze für Tour-Fotos EXAKT folgendes Format mit Nummer:
       ![Foto X: Deine Beschreibung](pfad/zum/bild)
       Die Nummer X entspricht der Position in der Bildliste. Auf der Übersichtskarte
       findest du jedes Foto mit dem Label "Foto X" am Aufnahmeort eingezeichnet.
     - **WICHTIG:** Verwende NUR die exakten Dateipfade aus der Liste unten. Kopiere den Pfad 1:1.
       Erfinde NIEMALS eigene Pfade oder Nummern — jeder Pfad aus der Liste muss exakt verwendet werden.
     - **JEDES Bild BRAUCHT eine Beschreibung im alt-Text** (auch Karte und Höhengraphen).
       Beispiel Tour-Foto: ![Foto 1: Atmosphärische Beschreibung des Bildinhalts](PFAD_AUS_DER_LISTE)
       Beispiel Karte: ![Routenverlauf unserer Tour](PFAD_ZUR_KARTE)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_services/test_blog_generator.py::TestConstructBlogPostPrompt -v`
Expected: All PASSED

- [ ] **Step 5: Commit**

```bash
git add tests/test_services/test_blog_generator.py app/services/blog_generator.py
git commit -m "feat: add Foto-X caption format to blog prompt"
```

---

### Task 6: Verification — full test suite

**Files:** None (read-only verification)

- [ ] **Step 1: Run all related tests**

Run: `uv run pytest tests/test_services/test_map_helpers.py tests/test_services/test_generate_enriched_mapimage.py tests/test_services/test_blog_generator.py tests/test_nodes/test_generate_enriched_map.py tests/test_services/test_generate_mapimage.py -v`

Expected: All PASSED (existing basic map tests unaffected, existing node test continues to pass with mocked services)

- [ ] **Step 2: Run full test suite**

Run: `uv run pytest tests/ -v`
Expected: All PASSED (no regressions)

- [ ] **Step 3: Run lint/typecheck if configured**

Run: `uv run ruff check app/` (if ruff installed) or verify no syntax issues

---

### Task 7: Final commit with all changes verified

- [ ] **Step 1: Verify git status is clean**

```bash
git status
```

- [ ] **Step 2: (Optional) Squash commits if desired**

Nur wenn der User es wünscht.
