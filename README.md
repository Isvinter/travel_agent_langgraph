# Travel Agent LangGraph

Automatically turn GPX hiking tracks and tour photos into richly illustrated, long-form blog posts — powered by a [LangGraph](https://langchain-oss.github.io/langgraph/) pipeline and local multimodal LLMs via [Ollama](https://ollama.com).

## Features

- **GPX Analytics** — parses track files, computes distance, elevation, speed stats, and detects rest pauses
- **Image ingestion** — loads photos from a directory, extracts EXIF GPS coordinates and timestamps
- **Location clustering** — groups geotagged photos taken at the same spot (density-based, 20 m radius)
- **Map generation** — renders an interactive Folium map and captures it as a PNG via headless Chrome
- **Elevation profile** — Matplotlib chart of elevation vs. distance
- **Historical weather** — fetches past weather data via Open-Meteo Archive API (no API key required), estimates 0°C freezing level from elevation data
- **POI discovery** — queries Overpass API for ~60 outdoor-relevant POI categories (peaks, waterfalls, huts, ruins, castles, shelters, etc.) near pause locations, with multi-instance fallback, exponential backoff retry, and file-based JSON cache; enriches with Wikipedia extracts (no API key required)
- **AI content review** — LLM quality gate that curates enrichment data: filters irrelevant POIs, discards non-applicable weather fields, rates image suitability, scores overall coherence
- **AI image selection** — multimodal LLM selects the best photos for the blog (batched, iterative)
- **AI blog generation** — multimodal LLM writes a narrative travel blog post enriched with weather, POIs, images, map, and elevation profile
- **AI blog design** — template-based CSS styling wraps generated HTML into a polished, responsive layout
- **Outputs** — styled HTML + Markdown files with compressed JPEG images, map, and elevation profile in a timestamped `output/` directory
- **PDF export** — generate downloadable PDFs from article HTML via headless Chrome CDP, available as a pipeline checkbox ("Als PDF exportieren") and from the article detail view
- **Database persistence** — SQLAlchemy-powered storage for generated articles with filterable queries (tour date, duration, generation time). Image paths stored, not BLOBs. Defaults to SQLite, PostgreSQL-ready via `DATABASE_URL` env var
- **Article browser** — filterable article table with checkboxes, single/batch delete with confirmation dialog, inline HTML rendering with images served via API
- **Web UI** — Svelte 5 frontend with drag-and-drop file uploads (GPX, images, .txt notes), live SSE progress streaming, model selection, output config (wildcard count, article length, style persona, PDF export toggle)
- **REST API** — FastAPI backend with pipeline run/stream, article CRUD + batch delete, PDF export, image serving, file upload endpoints

## Architecture

```
process_gpx → load_images → extract_metadata → clustering_images → generate_map_image → load_tour_notes → enrich_weather → enrich_poi → select_images → review_content → generate_blog_post → design_blogpost → persist_article → generate_pdf
```

All steps are LangGraph nodes that read and write a shared `AppState` (Pydantic model). Nodes are thin wrappers in `app/nodes/` that delegate to pure functions in `app/services/`.

| Layer | Module | Purpose |
|-------|--------|---------|
| State | `app/state.py` | `AppState` (images, clusters, GPX stats, weather, POIs, enrichment context, notes, blog_post) + `ImageData`, `DailyWeather`, `WeatherInfo`, `OutputConfig` |
| Graph | `app/graph.py` | LangGraph `StateGraph` definition — nodes, edges, entry/finish points |
| Nodes | `app/nodes/*.py` | Pipeline step wrappers (`AppState → AppState`) — 14 nodes total |
| Services | `app/services/*.py` | Business logic: GPX parsing, image loading, EXIF extraction, clustering, map generation, elevation profiles, weather enrichment (Open-Meteo), POI enrichment (Overpass + Wikipedia), content review (LLM quality gate), blog generation, blog design (template-based HTML/CSS), image selection, article persistence, PDF generation (headless Chrome CDP) |
| Database | `app/db/` | SQLAlchemy ORM models (`Article`, `ArticleImage`), repository pattern (CRUD + batch delete), connection management, auto-indexes. Default SQLite, PostgreSQL-ready |
| Pipeline | `app/pipeline/process_images.py` | Higher-level image processing orchestration |
| API | `app/api/` | FastAPI server, routes (CRUD, batch delete, image serving), SSE event manager |
| Utils | `app/utils/` | Low-level EXIF helpers |
| Frontend | `frontend/` | Svelte 5 + Vite + TypeScript SPA (12 components)

## Tech Stack

| Category | Technology |
|----------|-----------|
| Pipeline orchestration | [LangGraph](https://pypi.org/project/langgraph/) |
| LLM runtime | [Ollama](https://ollama.com) (Gemma4, Qwen3.6) |
| Backend | Python 3.12, [FastAPI](https://fastapi.tiangolo.com/), [Uvicorn](https://www.uvicorn.org/) |
| Frontend | [Svelte 5](https://svelte.dev/), [Vite 6](https://vitejs.dev/), TypeScript |
| Map rendering | [Folium](https://python-visualization.github.io/folium/), Selenium (headless Chrome) |
| Charts | [Matplotlib](https://matplotlib.org/) |
| Weather data | [Open-Meteo Archive API](https://open-meteo.com/) (free, no key) |
| POI data | [Overpass API](https://overpass-api.de/) + [Wikipedia REST API](https://www.mediawiki.org/wiki/API) (free, no key) |
| Image processing | [Pillow](https://python-pillow.org/) |
| GPX parsing | [gpxpy](https://pypi.org/project/gpxpy/) |
| Database | [SQLAlchemy 2.0](https://www.sqlalchemy.org/) with [Alembic](https://alembic.sqlalchemy.org/) migrations |
| SSE streaming | [sse-starlette](https://pypi.org/project/sse-starlette/) |
| Markdown → HTML | [Python-Markdown](https://python-markdown.github.io/) |
| Package management | [uv](https://docs.astral.sh/uv/) |

## Prerequisites

- **Python ≥ 3.12**
- **uv** — Python package and project manager
- **Ollama** running locally (`ollama serve`) with a multimodal model pulled (e.g. `gemma4:26b-ctx128k`)
- **Chromium/Chrome** installed (for Selenium-based map screenshot capture)
- **Node.js ≥ 18** (frontend development only)

## Installation

```bash
git clone <repo-url> && cd travel_agent_langgraph
uv sync
```

Pull at least one supported Ollama model:

```bash
ollama pull gemma4:26b-ctx128k
```

## Quick Start

### Command-line pipeline

```bash
uv run python main.py
```

Or interactively with model selection:

```python
from app.graph import run_pipeline
result = run_pipeline()  # prompts for model choice
```

### Web UI (development)

**Terminal 1** — FastAPI backend:

```bash
uv run uvicorn app.api.server:app --reload --host 0.0.0.0 --port 8000
```

**Terminal 2** — Svelte dev server (proxies `/api` to `:8000`):

```bash
cd frontend && npm run dev
```

Open `http://localhost:5173`. Upload a GPX file, photos, optionally add notes, select a model, and run the pipeline. Progress streams live via SSE.

### Web UI (production)

```bash
cd frontend && npm run build
travel-agent-api --host 0.0.0.0 --port 8000
# or: uv run uvicorn app.api.server:app --host 0.0.0.0 --port 8000
```

FastAPI serves both the API and the built Svelte static files from `frontend/dist/`.

## CLI

```bash
travel-agent-api --host 0.0.0.0 --port 8000
```
Defined as console script in `pyproject.toml`. Equivalent to `uv run uvicorn app.api.server:app`. Options: `--host`, `--port`. Omit `--host` for localhost-only binding.

## Project Structure

```
.
├── app/
│   ├── api/            # FastAPI server, routes, SSE events
│   ├── db/             # SQLAlchemy models, connection, repository
│   ├── nodes/          # LangGraph pipeline nodes (thin wrappers, 14 nodes)
│   ├── services/       # Business logic (15 services: GPX, images, clustering, maps, weather, POIs, review, blog, persistence, PDF, etc.)
│   ├── pipeline/       # Higher-level image processing orchestration
│   ├── utils/          # EXIF helpers
│   ├── graph.py        # StateGraph builder + build_graph() + run_pipeline()
│   └── state.py        # AppState, ImageData, DailyWeather, WeatherInfo Pydantic models
├── frontend/           # Svelte 5 + Vite + TypeScript SPA (11 components)
│   ├── src/
│   │   ├── App.svelte
│   │   └── lib/
│   │       ├── stores/          # pipeline.ts, router.ts
│   │       ├── ArticleList.svelte
│   │       ├── ArticleDetail.svelte
│   │       ├── FileDropZone.svelte
│   │       ├── ModelSelector.svelte
│   │       ├── NotesInput.svelte
│   │       ├── OutputDirInput.svelte
│   │       ├── OutputWindow.svelte
│   │       ├── RunButton.svelte
│   │       ├── WildcardCount.svelte
│   │       ├── LengthSelector.svelte
│   │       ├── StyleSelector.svelte
│   │       └── PdfExportCheckbox.svelte
│   └── dist/           # Production build (served by FastAPI)
├── tests/              # pytest suite (unit, integration, e2e)
│   ├── test_api/       # API-specific tests
│   ├── test_graph/     # Graph/integration tests
│   ├── test_nodes/     # Per-node unit tests
│   ├── test_services/  # Per-service unit tests
│   └── fixtures/       # Test data (GPX, images, notes)
├── docs/               # Design specs and implementation plans
├── data/               # Runtime input data (gitignored)
│   ├── gpx/
│   ├── images/
│   ├── notes/
│   └── uploads/
├── output/             # Generated blog posts (gitignored, timestamped subdirs)
├── main.py             # CLI entry point (reference only — hardcoded GPX path)
├── pyproject.toml      # Dependencies and project config
└── uv.lock             # Lock file
```

## Running Tests

```bash
uv run pytest tests/ -v
```

Test structure: `tests/test_services/` (per-service unit tests), `tests/test_nodes/` (per-node tests), `tests/test_graph/` (graph integration + e2e), `tests/test_api/` (API + enrichment e2e). Test markers from `pyproject.toml`: `unit` (fast, no external deps), `integration` (real filesystem/mocked network), `e2e` (requires Ollama + Chrome). Fixtures in `tests/fixtures/`.

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/models` | List available Ollama models |
| `POST` | `/api/files/upload` | Upload a file (multipart, session cookie) |
| `DELETE` | `/api/files/{filename}` | Delete an uploaded file |
| `POST` | `/api/pipeline/run` | Start a pipeline run → returns `run_id` |
| `GET` | `/api/pipeline/stream/{run_id}` | SSE stream of pipeline progress events |
| `GET` | `/api/pipeline/result/{run_id}` | Retrieve completed pipeline result |
| `GET` | `/api/articles` | List persisted articles with filters (tour date, duration, generation time) and pagination |
| `GET` | `/api/articles/{id}` | Get full article detail with markdown, HTML, and image references |
| `DELETE` | `/api/articles/{id}` | Delete an article — removes DB record and output files |
| `POST` | `/api/articles/delete-batch` | Delete multiple articles at once |
| `GET` | `/api/articles/{id}/pdf` | Export an article as a downloadable PDF file |
| `GET` | `/api/articles/{id}/images/{filename}` | Serve an article's image file |

## Database Configuration

The persistence layer uses SQLAlchemy with a swappable backend. Configuration via environment variable:

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:///travel_agent.db` | Connection string (set to `postgresql://...` for PostgreSQL) |

Default is SQLite — a single `travel_agent.db` file created in the project root on first use. Tables and indexes are auto-created. Images are referenced by file path (no BLOBs).

## Available Models

Configured in `app/state.py`:

- `gemma4:26b-ctx128k` (default)
- `gemma4:31b-ctx112k`
- `qwen3.6:27b-ctx128k`
- `qwen3.6:35b-ctx128k`

Custom models can be entered interactively in the CLI pipeline.

## License

This project is for personal/educational use.
