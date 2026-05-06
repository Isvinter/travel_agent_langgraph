# Travel Agent LangGraph

Automatically turn GPX hiking tracks and tour photos into richly illustrated blog posts **and A4 photo books** — powered by a [LangGraph](https://langchain-oss.github.io/langgraph/) pipeline and local multimodal LLMs via [Ollama](https://ollama.com).

## Features

### Blog Pipeline
- **GPX Analytics** — parses track files, computes distance, elevation, speed stats, and detects rest pauses
- **Image ingestion** — loads photos from a directory, extracts EXIF GPS coordinates and timestamps
- **Location clustering** — groups geotagged photos taken at the same spot (density-based, 20 m radius)
- **Map generation** — renders an interactive Folium map and captures it as a PNG via headless Chrome
- **Elevation profile** — Matplotlib chart of elevation vs. distance
- **Historical weather** — fetches past weather data via Open-Meteo Archive API (no API key required)
- **POI discovery** — queries Overpass API for outdoor-relevant POI categories near pause locations
- **AI content review** — LLM quality gate curates enrichment data (POIs, weather, images, coherence)
- **AI image selection** — multimodal LLM selects best photos for the blog (batched, iterative)
- **AI blog generation** — multimodal LLM writes narrative travel blog enriched with weather, POIs, images, map
- **AI blog design** — template-based CSS styling wraps HTML into polished responsive layout
- **PDF export** — downloadable PDFs via headless Chrome CDP
- **Database persistence** — SQLAlchemy with filterable article queries, PostgreSQL-ready
- **Article browser** — filterable table, batch delete, inline HTML rendering with images
- **Web UI** — Svelte 5 frontend with drag-and-drop, live SSE progress streaming

### Photobook Pipeline (NEW)
- **Dedicated image selection** — multimodal LLM selects best photos for print layout (batched, tolerate parsing)
- **AI layout planning** — LLM chooses from 18 A4 presets (1–5 images/page) with variety rules
- **AI text generation** — LLM writes page titles and detailed captions (up to 500 chars) describing what's visible in each image group, with landscape/stimmung/colors/weather awareness
- **Deterministic validation** — enforces variety rules (no duplicate cover, max 3 textless pages, diverse image counts), upgrades textless presets when LLM generates captions, truncates overflow
- **CSS Grid rendering** — each preset renders as a precise 210×297mm page with A4 print CSS
- **PDF export** — headless Chrome CDP with print media emulation
- **HTML debug output** — intermediate HTML saved alongside PDF for inspection
- **Pipeline separation** — photobook mode branches early, skipping expensive blog enrichment nodes

## Architecture

The pipeline uses a single LangGraph `StateGraph` with two mode-dependent execution paths:

```
process_gpx → load_images → extract_metadata → clustering_images → generate_map_image → load_tour_notes
                                                                                                │
                                                                             ┌──────────────────┘
                                                                             ↓
                                                              mode=photobook │ mode=blog
                                                                             ↓
                                                    select_photobook_images   enrich_weather
                                                              │               ↓
                                                       plan_photobook      enrich_poi
                                                              │               ↓
                                                     generate_photobook    select_images
                                                              │               ↓
                                                      render_photobook    review_content
                                                              │               ↓
                                                   generate_photobook_pdf  generate_enriched_map
                                                                             │
                                                                     generate_blog_post
                                                                             │
                                                                     design_blogpost → persist_article → (PDF) → END
```

**Photobook mode** branches at `load_tour_notes`, skipping 6 blog-only enrichment nodes.

All steps are LangGraph nodes reading/writing a shared `AppState` (Pydantic model). Nodes are thin wrappers in `app/nodes/` delegating to services.

| Layer | Module | Purpose |
|-------|--------|---------|
| State | `app/state.py` | `AppState`, `ImageData`, `PageDescription`, `PhotobookConfig`, `OutputConfig` |
| Graph | `app/graph.py` | LangGraph `StateGraph` — mode-dependent branching, 20 nodes |
| Nodes | `app/nodes/*.py` | Pipeline step wrappers (`AppState → AppState`) |
| Services | `app/services/*.py` | Blog business logic (GPX, images, clustering, maps, weather, POIs, review, blog, design, PDF) |
| Photobook | `app/photobook/*.py` | Photobook module: plan, generate, render, validate, PDF, image selection, 18 presets |
| Presets | `app/photobook/preset_data/` | 18 JSON preset definitions with CSS grid areas and text constraints |
| CSS | `app/photobook/styles.css` | A4-optimized print CSS with 18 preset grid layouts |
| Database | `app/db/` | SQLAlchemy ORM models, repository pattern |
| API | `app/api/` | FastAPI server, routes, SSE events |
| Utils | `app/utils/` | EXIF helpers, image compression/base64 encoding |
| Frontend | `frontend/` | Svelte 5 + Vite + TypeScript SPA |

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
│   ├── nodes/          # LangGraph pipeline nodes (20 nodes for blog + photobook)
│   ├── services/       # Blog business logic (GPX, images, clustering, weather, etc.)
│   ├── photobook/      # Photobook module
│   │   ├── preset_data/    # 18 JSON preset definitions
│   │   ├── styles.css      # A4 print CSS with 18 grid layouts
│   │   ├── plan.py         # LLM Pass 1: layout planning
│   │   ├── generate.py     # LLM Pass 2: slot assignment + text
│   │   ├── renderer.py     # HTML assembler from PageDescription
│   │   ├── validator.py    # Deterministic variety + text enforcement
│   │   ├── generate_pdf.py # Headless Chrome PDF via CDP
│   │   ├── image_selector.py  # Multimodal batch image selection
│   │   └── presets.py      # Preset catalog + text constraints
│   ├── utils/          # EXIF helpers, image compression/base64
│   ├── graph.py        # StateGraph builder with mode-dependent branching
│   ├── state.py        # AppState, PageDescription, PhotobookConfig
│   └── config.py       # OLLAMA_BASE_URL, OUTPUT_DIR, PHOTOBOOK_SIZE_MAP
├── frontend/           # Svelte 5 + Vite + TypeScript SPA
├── tests/              # pytest suite
│   └── test_photobook/ # Photobook-specific tests (73 tests)
├── output/             # Generated output (gitignored, timestamped subdirs)
├── pyproject.toml
└── uv.lock
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
