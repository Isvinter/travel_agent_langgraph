# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Travel agent that processes hiking tour data (GPX tracks + photos) and auto-generates blog posts. The pipeline loads images, extracts GPS metadata, clusters photos, generates a map image, computes GPX analytics, and feeds everything into a multimodal LLM (Ollama/Gemma4) to produce a markdown + HTML blog post.

## Running the pipeline

No formal test suite or build system. Run the pipeline directly:

```bash
python -c "from app.graph import build_graph; graph = build_graph(); result = graph.invoke({})"
```

Before running, ensure:
- GPX file path is set in `AppState.gpx_file`
- Tour photos are in `data/images/`
- Optional notes are in `data/notes/`
- Ollama is running locally (`ollama serve`)

## Architecture

### Data flow (LangGraph StateGraph)

```
process_gpx -> load_images -> extract_metadata -> clustering_images -> generate_map_image -> load_tour_notes -> generate_blog_post
```

All nodes read/write a shared `AppState` (Pydantic model in `app/state.py`).

### Key modules

| Layer | Module | Purpose |
|-------|--------|---------|
| State | `app/state.py` | `AppState` (images, clusters, GPX stats, notes, blog_post) + `ImageData` |
| Graph | `app/graph.py` | LangGraph `StateGraph` definition — entry/exit points and edges |
| Nodes | `app/nodes/*.py` | Individual pipeline steps (one function each, takes AppState -> AppState) |
| Services | `app/services/*.py` | Business logic: GPX parsing, image loading, metadata extraction, clustering, map generation, elevation profile, blog generation |
| Utils | `app/utils/exif_helper.py` | Low-level EXIF parsing (GPS coordinates, timestamps) |
| Pipeline | `app/pipeline/process_images.py` | Higher-level orchestration helper (`enrich_images_with_metadata`) |

### Services deep dive

- **`gpx_analytics.py`** — Parses GPX via `gpxpy`, computes distance/elevation/speed stats, detects pauses (time gaps > 10 min with < 20m movement). Outputs `GPXStats` + pause list.
- **`generate_elevation_profile.py`** — Matplotlib chart of elevation vs distance.
- **`generate_mapimage.py`** — Folium map from GPX coords saved as HTML, then headless Chrome (Selenium) captures it as PNG.
- **`clustering_images.py`** — Density-based clustering (20m radius) of geotagged images to group photos taken at same location.
- **`blog_generator.py`** — Core AI service: encodes images to base64, builds a multimodal prompt, calls Ollama `/api/chat` with Gemma4:26b-ctx128k, saves markdown + HTML to `output/`.

## Dependencies

Managed via `pyproject.toml`. Use `uv` for environment and dependency management:

```bash
uv sync          # install deps into venv
uv run python ...  # run code in the venv
```

## Code structure notes

- Nodes are thin wrappers that call services and update `AppState`. Each node is a pure function `AppState -> AppState`.
- Services are standalone — no global state, no side effects except file I/O.
- `app/models.py` is empty (currently unused).
- `app/__init__.py`, `app/nodes/__init__.py`, `app/services/__init__.py` are all empty.
- Output files go to `output/` with timestamped filenames (e.g. `2026-04-21_13-53-53_blogpost.md`).

## Editing rules

Make minimal surgical changes. Only touch what is strictly necessary for the current task — do not refactor, reformat, or "clean up" unrelated code.
