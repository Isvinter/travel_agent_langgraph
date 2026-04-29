# Test Suite Design

**Date:** 2026-04-29
**Status:** Approved
**Context:** Add comprehensive tests (unit through E2E) to the travel agent LangGraph project before implementing new features.

## Overview

A three-layer pytest test suite using committed synthetic fixtures, pytest markers for layer differentiation, and a directory structure mirroring `app/`.

## Directory Structure

```
tests/
  conftest.py                    # shared fixtures, marker registration
  fixtures/
    gpx/tour.gpx                 # ~15 trackpoints, 2 segments, includes 12-min pause gap
    images/photo_a.jpg           # 200x200 JPEG, EXIF: lat=47.3 lon=8.5 ts=2025-06-01T10:00
    images/photo_b.jpg           # 200x200 JPEG, EXIF: lat=47.3002 lon=8.5002 (~15m from A)
    images/photo_c.jpg           # 200x200 JPEG, EXIF: lat=47.5 lon=9.0 (separate cluster)
    notes/notes.txt              # 3 lines of tour notes
  test_services/
    test_gpx_analytics.py
    test_image_loader.py
    test_metadata_extractor.py
    test_clustering_images.py
    test_generate_elevation_profile.py
    test_generate_mapimage.py
    test_blog_generator.py
    test_image_selector.py
    test_load_tour_notes.py
  test_nodes/
    test_process_gpx.py
    test_load_images.py
    test_extract_metadata.py
    test_clustering_image.py
    test_generate_map.py
    test_load_tour_notes.py
    test_select_images.py
    test_generate_blogpost.py
  test_graph/
    test_pipeline_e2e.py
```

## Test Layers

### Unit tests (`@pytest.mark.unit`)

- Test one function in isolation
- Mock all file I/O and external calls (Ollama HTTP, Selenium, filesystem)
- Target: full suite runs in <1 second

### Integration tests (`@pytest.mark.integration`)

- Test one service with real local dependencies:
  - Real file I/O against committed fixture files
  - Real matplotlib (Agg backend)
  - Real Folium HTML generation (mock Selenium screenshot)
  - Mocked Ollama HTTP (deterministic canned response)
- Default safety-net layer — run before every change

### E2E tests (`@pytest.mark.e2e`)

- Full pipeline via `build_graph()` → `graph.invoke(state)` with fixture GPX + images
- Real Ollama must be running (`ollama serve`)
- Real Chrome headless for map screenshot
- Skippable (`pytest.skip`) if prerequisites missing
- Opt-in only: `pytest -m e2e`

## Fixtures and Mocking Strategy

### Committed synthetic fixtures

All fixtures live in `tests/fixtures/` (not `data/`) so they're always available and version-controlled.

### conftest.py shared fixtures

- `sample_gpx_path` — returns `tests/fixtures/gpx/tour.gpx`
- `sample_images` — returns list of 3 `ImageData` from fixture photos
- `sample_state` — minimal `AppState` with GPX path and images populated
- `sample_gpx_stats` — pre-computed `GPXStats` (avoids re-parsing in every test)

### Mocking rules

| Dependency | Unit test | Integration test | E2E test |
|-----------|-----------|-----------------|----------|
| File I/O | Mocked | Real fixture files | Real fixture files |
| Ollama HTTP | Mocked | Mocked (deterministic) | Real |
| Selenium/Chrome | Mocked | Skip if Chrome missing, else real | Real (required) |
| matplotlib | Mocked (don't render) | Real (Agg backend) | Real |

### Skipping strategy

- Integration tests needing Chrome: `pytest.skip` if `shutil.which("chromium")` returns falsy
- E2E tests: `pytest.skip` if Ollama not reachable or Chrome not installed
- GPX/fixture-dependent tests: fail on missing fixtures (never skip — fixtures are committed)

## Test Coverage Per Service

### test_gpx_analytics.py
- Parse valid GPX → correct distance, elevation, duration
- Parse GPX with 12-min gap → pause detected with correct duration
- Broken XML → handles gracefully (no crash)
- Empty GPX file → handles edge case

### test_image_loader.py
- Load from fixture directory → returns correct ImageData count
- Empty directory → empty list
- Directory with non-image files → only images returned

### test_metadata_extractor.py
- JPEG with EXIF → GPS coordinates and timestamp extracted correctly
- JPEG without EXIF → None fields, no crash
- PNG or unsupported format → handled gracefully

### test_clustering_images.py
- 3 images (2 close, 1 far) → 2 clusters with correct membership
- No geotagged images → 0 clusters
- Single image → 1 cluster
- Verify cluster centroid and member count

### test_generate_elevation_profile.py
- Valid GPXStats input → PNG file written to expected path
- Verify matplotlib uses Agg backend (no display required)
- Output path returned correctly

### test_generate_mapimage.py
- Unit: mock Selenium → HTML file saved, screenshot method called, map center matches GPX coords
- Integration: real Chrome if available → PNG output; skip if Chrome missing

### test_blog_generator.py
- Unit: mock Ollama → markdown + HTML files written to output/
- Verify prompt content includes image count, GPX stats, notes
- Test base64 image encoding produces valid output
- Ollama returns error → handled gracefully, no crash

### test_image_selector.py
- 3 clusters → 3 selected images (one per cluster)
- Empty clusters → empty list
- Single cluster with 5 images → picks exactly 1 representative

### test_load_tour_notes.py
- Fixture notes file exists → returns content string
- Missing file → returns None or empty (no crash)

## Node Tests

Each node test file:
1. Constructs a partial `AppState` with the relevant input fields set
2. Calls the node function
3. Asserts the output state contains the expected fields/values
4. Mocks the underlying service the node delegates to

## E2E Test

Single file `test_pipeline_e2e.py`:
- Builds the full LangGraph graph via `build_graph()`
- Invokes with `AppState` containing fixture GPX path and image paths
- Asserts result contains non-empty `blog_post` dict with `markdown` and `html` keys
- Asserts output files exist in `output/` directory
- Skipped entirely if Ollama not reachable or Chrome not installed

## Dependencies

Add to `pyproject.toml`:

```toml
[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-mock>=3.14",
]

[tool.pytest.ini_options]
markers = [
    "unit: Fast tests with no external dependencies",
    "integration: Tests using real filesystem and fixtures, mocked network/browser",
    "e2e: Full pipeline tests requiring Ollama and Chrome",
]
```

## Commands

```bash
uv sync --group dev                       # install test deps
uv run pytest -m unit                     # fast, no deps
uv run pytest -m "unit or integration"    # default safety net
uv run pytest -m e2e                      # full pipeline (needs Ollama + Chrome)
uv run pytest -m "not e2e"                # CI target
uv run pytest tests/test_services/test_gpx_analytics.py -v  # single file
```
