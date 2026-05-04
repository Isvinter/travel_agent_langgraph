# Enriched Map Generation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an enriched map (route + pause markers + selected image markers) generated after the content review step, while keeping the basic map for progress display.

**Architecture:** Additive — new node `generate_enriched_map_node` and new service function `generate_enriched_map_html()`. Existing code unchanged except graph wiring (1 edge removed, 2 added) and blog node (1 metadata key changed).

**Tech Stack:** Python, folium, Selenium (headless Chrome), LangGraph, pytest

---

### File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `app/services/generate_mapimage.py` | Modify | Add `generate_enriched_map_html()` |
| `app/nodes/generate_enriched_map.py` | **Create** | Node: AppState → AppState, calls service + html_to_png |
| `app/graph.py` | Modify | Import, NODE_NAMES, wire new node into pipeline |
| `app/nodes/generate_blogpost.py` | Modify | Change metadata key to `enriched_map_image_path` |
| `tests/test_services/test_generate_enriched_mapimage.py` | **Create** | Service-level unit tests |
| `tests/test_nodes/test_generate_enriched_map.py` | **Create** | Node-level unit tests |
| `tests/test_graph/test_pipeline_e2e.py` | Modify | Assert enriched map path in metadata |

---

### Task 1: Write service-level tests for `generate_enriched_map_html`

**Files:**
- Create: `tests/test_services/test_generate_enriched_mapimage.py`

- [ ] **Step 1: Create test file with all test cases**

```python
"""Tests for generate_enriched_map_html in app/services/generate_mapimage.py"""
import os
import pytest
from app.services.generate_mapimage import generate_enriched_map_html
from app.services.gpx_analytics import TrackPoint
from app.state import ImageData


@pytest.fixture
def sample_points():
    return [
        TrackPoint(lat=47.3, lon=8.5, elevation=500.0, time=None),
        TrackPoint(lat=47.301, lon=8.501, elevation=510.0, time=None),
        TrackPoint(lat=47.302, lon=8.502, elevation=520.0, time=None),
    ]


@pytest.fixture
def sample_pauses():
    from datetime import datetime
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
    def test_contains_pause_markers(self, tmp_path, sample_points, sample_pauses, sample_images):
        html_path = str(tmp_path / "enriched_map.html")
        generate_enriched_map_html(sample_points, sample_pauses, sample_images, html_path)

        content = open(html_path).read()
        assert "Pause: 15.0 min" in content
        assert "Pause: 25.0 min" in content

    @pytest.mark.unit
    def test_contains_image_markers(self, tmp_path, sample_points, sample_pauses, sample_images):
        html_path = str(tmp_path / "enriched_map.html")
        generate_enriched_map_html(sample_points, sample_pauses, sample_images, html_path)

        content = open(html_path).read()
        assert "Bild 1:" in content
        assert "Bild 2:" in content

    @pytest.mark.unit
    def test_handles_empty_pauses(self, tmp_path, sample_points, sample_images):
        html_path = str(tmp_path / "enriched_map.html")
        generate_enriched_map_html(sample_points, [], sample_images, html_path)

        assert os.path.exists(html_path)
        content = open(html_path).read()
        assert "Pause:" not in content  # keine Pausen-Marker

    @pytest.mark.unit
    def test_handles_empty_images(self, tmp_path, sample_points, sample_pauses):
        html_path = str(tmp_path / "enriched_map.html")
        generate_enriched_map_html(sample_points, sample_pauses, [], html_path)

        assert os.path.exists(html_path)
        content = open(html_path).read()
        assert "Bild" not in content  # keine Bild-Marker

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
```

- [ ] **Step 2: Run tests (will fail — function not yet defined)**

```bash
uv run pytest tests/test_services/test_generate_enriched_mapimage.py -v
```

Expected: All 7 tests FAIL with `ImportError` or `AttributeError: module 'app.services.generate_mapimage' has no attribute 'generate_enriched_map_html'`

- [ ] **Step 3: Commit**

```bash
git add tests/test_services/test_generate_enriched_mapimage.py
git commit -m "test: add failing tests for generate_enriched_map_html"
```

---

### Task 2: Implement `generate_enriched_map_html` service function

**Files:**
- Modify: `app/services/generate_mapimage.py`

- [ ] **Step 1: Add the function to `app/services/generate_mapimage.py`**

Append after line 69 (after `html_to_png`):

```python
def generate_enriched_map_html(
    points: List[TrackPoint],
    pauses: list,
    images: list,
    output_html: str,
):
    """Generiert eine Folium-Karte mit Route, Pausen-Markern und Bild-Markern."""
    import math

    # Mittelpunkt und Bounding Box (wie generate_map_html)
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

    # Start / Ende Marker
    folium.Marker(
        coords[0],
        tooltip="Start",
        icon=folium.Icon(color="green", icon="flag", prefix="fa"),
    ).add_to(m)
    folium.Marker(
        coords[-1],
        tooltip="Ende",
        icon=folium.Icon(color="red", icon="flag-checkered", prefix="fa"),
    ).add_to(m)

    # Pausen-Marker
    for pause in pauses:
        loc = pause.get("location", {})
        lat = loc.get("lat")
        lon = loc.get("lon")
        if lat is None or lon is None:
            continue
        duration = pause.get("duration_minutes", 0)
        start = pause.get("start_time", "")
        end = pause.get("end_time", "")
        popup_text = f"{start} – {end}" if start and end else ""
        folium.Marker(
            [lat, lon],
            tooltip=f"Pause: {duration} min",
            popup=folium.Popup(popup_text, max_width=200) if popup_text else None,
            icon=folium.Icon(color="orange", icon="pause", prefix="fa"),
        ).add_to(m)

    # Bild-Marker
    for idx, img in enumerate(images, 1):
        lat = img.latitude if hasattr(img, "latitude") else img.get("latitude")
        lon = img.longitude if hasattr(img, "longitude") else img.get("longitude")
        if lat is None or lon is None:
            continue
        timestamp = img.timestamp if hasattr(img, "timestamp") else img.get("timestamp", "")
        folium.Marker(
            [lat, lon],
            tooltip=f"Bild {idx}: {timestamp}",
            icon=folium.Icon(color="blue", icon="camera", prefix="fa"),
        ).add_to(m)

    m.fit_bounds([[south, west], [north, east]])
    m.save(output_html)
```

- [ ] **Step 2: Run tests**

```bash
uv run pytest tests/test_services/test_generate_enriched_mapimage.py -v
```

Expected: All 7 tests PASS

- [ ] **Step 3: Commit**

```bash
git add app/services/generate_mapimage.py
git commit -m "feat: add generate_enriched_map_html with pause and image markers"
```

---

### Task 3: Write node-level tests for `generate_enriched_map_node`

**Files:**
- Create: `tests/test_nodes/test_generate_enriched_map.py`

- [ ] **Step 1: Create test file**

```python
"""Tests for app/nodes/generate_enriched_map.py"""
from unittest.mock import patch
from app.nodes.generate_enriched_map import generate_enriched_map_node
from app.state import AppState, ImageData
from app.services.gpx_analytics import TrackPoint, GPXStats
from datetime import datetime


class TestGenerateEnrichedMapNode:
    def test_skips_when_no_gpx_stats(self):
        state = AppState(gpx_stats=None)
        result = generate_enriched_map_node(state)
        assert "enriched_map_image_path" not in result.metadata

    def test_generates_enriched_map_with_mocked_services(self):
        points = [TrackPoint(lat=47.0, lon=8.0, elevation=500.0, time=None)]
        stats = GPXStats(
            total_distance_m=1000,
            elevation_gain_m=100,
            elevation_loss_m=50,
            avg_speed_kmh=5.0,
            max_speed_kmh=10.0,
            points=points,
        )
        pauses = [
            {
                "start_time": datetime(2024, 7, 15, 10, 0),
                "end_time": datetime(2024, 7, 15, 10, 15),
                "duration_minutes": 15.0,
                "location": {"lat": 47.001, "lon": 8.001},
            }
        ]
        images = [
            ImageData(
                path="data/images/photo.jpg",
                timestamp="2024-07-15T10:00:00",
                latitude=47.0005,
                longitude=8.0005,
            )
        ]

        state = AppState(
            gpx_stats=stats,
            gpx_pauses=pauses,
            selected_images=images,
        )

        with patch(
            "app.nodes.generate_enriched_map.generate_enriched_map_html"
        ) as mock_html, patch(
            "app.nodes.generate_enriched_map.html_to_png"
        ) as mock_png, patch(
            "os.makedirs"
        ):
            result = generate_enriched_map_node(state)

            mock_html.assert_called_once()
            mock_png.assert_called_once()
            assert "enriched_map_image_path" in result.metadata
            assert result.metadata["enriched_map_image_path"] == "output/enriched_map.png"
```

- [ ] **Step 2: Run tests (will fail — node not yet defined)**

```bash
uv run pytest tests/test_nodes/test_generate_enriched_map.py -v
```

Expected: FAIL with `ModuleNotFoundError` or `ImportError`

- [ ] **Step 3: Commit**

```bash
git add tests/test_nodes/test_generate_enriched_map.py
git commit -m "test: add failing tests for generate_enriched_map_node"
```

---

### Task 4: Implement `generate_enriched_map_node`

**Files:**
- Create: `app/nodes/generate_enriched_map.py`

- [ ] **Step 1: Create the node file**

```python
# app/nodes/generate_enriched_map.py

from app.state import AppState
from app.services.generate_mapimage import generate_enriched_map_html, html_to_png
import os


def generate_enriched_map_node(state: AppState) -> AppState:
    if state.gpx_stats is None or not state.gpx_stats.points:
        print("⚠️  No GPX data available for enriched map generation.")
        return state

    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)

    html_path = os.path.join(output_dir, "enriched_map.html")
    png_path = os.path.join(output_dir, "enriched_map.png")

    generate_enriched_map_html(
        points=state.gpx_stats.points,
        pauses=state.gpx_pauses,
        images=state.selected_images,
        output_html=html_path,
    )

    html_to_png(html_path, png_path)

    state.metadata["enriched_map_image_path"] = png_path

    print(f"🗺️  Enriched map generated: {png_path}")
    return state
```

- [ ] **Step 2: Run node tests**

```bash
uv run pytest tests/test_nodes/test_generate_enriched_map.py -v
```

Expected: Both tests PASS

- [ ] **Step 3: Commit**

```bash
git add app/nodes/generate_enriched_map.py
git commit -m "feat: add generate_enriched_map_node with pause and image markers"
```

---

### Task 5: Wire new node into the graph

**Files:**
- Modify: `app/graph.py`

- [ ] **Step 1: Add import, NODE_NAMES entry, wrap, add_node, rewire edges**

**Import** (after line 16, before the `EventEmitter` alias):

```python
from app.nodes.generate_enriched_map import generate_enriched_map_node
```

**NODE_NAMES** dict (after line 35, `"generate_pdf"` entry):

```python
    "generate_enriched_map": "Angereicherte Karte generieren",
```

**Wrap** (after line 104, after `rcn = ...`):

```python
    gem = _wrap_node(generate_enriched_map_node, "generate_enriched_map", event_emitter) if event_emitter else generate_enriched_map_node
```

**add_node** (after line 120, `builder.add_node("generate_pdf", gpn)`):

```python
    builder.add_node("generate_enriched_map", gem)
```

**Edge change** — replace line 133:

```python
# REMOVE this line:
    builder.add_edge("review_content", "generate_blog_post")
# ADD these two lines:
    builder.add_edge("review_content", "generate_enriched_map")
    builder.add_edge("generate_enriched_map", "generate_blog_post")
```

- [ ] **Step 2: Run existing graph tests to verify no regressions**

```bash
uv run pytest tests/test_graph/ -v
```

Expected: All existing graph tests PASS

- [ ] **Step 3: Commit**

```bash
git add app/graph.py
git commit -m "feat: wire generate_enriched_map node into pipeline after review_content"
```

---

### Task 6: Update blog generator to use enriched map

**Files:**
- Modify: `app/nodes/generate_blogpost.py`

- [ ] **Step 1: Change metadata key on line 31**

In `app/nodes/generate_blogpost.py`, replace line:

```python
map_image_path = state.metadata.get("map_image_path")
```

With:

```python
map_image_path = state.metadata.get("enriched_map_image_path")
```

- [ ] **Step 2: Run blog generation tests**

```bash
uv run pytest tests/test_nodes/test_generate_blogpost.py -v
```

Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add app/nodes/generate_blogpost.py
git commit -m "feat: blog generator uses enriched_map_image_path from metadata"
```

---

### Task 7: Update E2E test assertion

**Files:**
- Modify: `tests/test_graph/test_pipeline_e2e.py`

- [ ] **Step 1: Add assertion for enriched map path**

After line 44 (`result = graph.invoke(state)`), add:

```python
            assert "enriched_map_image_path" in result.get("metadata", {})
```

- [ ] **Step 2: Run E2E test (may skip if no Ollama/Chrome)**

```bash
uv run pytest tests/test_graph/test_pipeline_e2e.py -v
```

Expected: SKIP (no Ollama/Chrome) or PASS with assertion

- [ ] **Step 3: Commit**

```bash
git add tests/test_graph/test_pipeline_e2e.py
git commit -m "test: assert enriched_map_image_path in E2E test metadata"
```

---

### Task 8: Final verification — run full test suite

- [ ] **Step 1: Run all tests**

```bash
uv run pytest tests/ -v --ignore=tests/test_api --ignore=tests/test_graph/test_pipeline_e2e.py
```

Expected: All unit tests PASS

- [ ] **Step 2: Run lint**

```bash
uv run ruff check app/ tests/
```

Expected: No new linting errors

- [ ] **Step 3: Commit if anything was fixed**

```bash
git add .
git commit -m "chore: final lint and test fixes for enriched map feature"
```
