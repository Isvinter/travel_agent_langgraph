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
- **AI content review** — LLM quality gate validates enrichment data (POI relevance, weather, image quality, narrative coherence) and discards low-quality content
- **AI image selection** — multimodal LLM selects best photos for the blog (batched, iterative)
- **AI blog generation** — multimodal LLM writes narrative travel blog enriched with weather, POIs, images, map
- **AI blog design** — styled HTML with two writer personas (Mountain Veteran / Field Reporter) and three length presets (short / normal / detailed)
- **PDF export** — downloadable PDFs via headless Chrome CDP (optional, user-togglable)
- **Database persistence** — SQLAlchemy with filterable article queries, PostgreSQL-ready
- **Article browser** — filterable table, batch delete, inline HTML rendering with images
- **Web UI** — Svelte 5 frontend with drag-and-drop, live SSE progress streaming

### Photobook Pipeline (NEW)
- **Dedicated image selection** — multimodal LLM selects best photos for print layout (batched, tolerate parsing)
- **AI layout planning** — LLM chooses from 18 A4 presets (1–5 images/page) with variety rules
- **Three size presets** — short (12 photos, 8–12 pages), normal (16, 14–18), detailed (20, 20–24)
- **18 CSS Grid layouts** — cover_hero, single_full, single_text_below, single_text_left, double_stacked, double_stacked_text, double_text_right, triple_big_top, triple_big_text_below, triple_stacked, triple_stacked_text, quad_grid, quad_grid_text, quad_large_plus_3, image_text_split, panorama, map_focus, collage_5
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
                                                    select_photobook_images  enrich_weather
                                                              │              ↓
                                                       plan_photobook       enrich_poi
                                                              │              ↓
                                                     generate_photobook   select_images
                                                              │              ↓
                                                      render_photobook   review_content
                                                              │              ↓
                                                   generate_photobook_pdf generate_enriched_map
                                                              │              ↓
                                                            END     generate_blog_post
                                                                             ↓
                                                                     design_blogpost
                                                                             ↓
                                                                     persist_article
                                                                        │        │
                                                                pdf=true│        │pdf=false
                                                                        ↓        ↓
                                                                generate_pdf    END
                                                                        ↓
                                                                      END
```

**Photobook mode** branches at `load_tour_notes`, skipping 6 blog-only enrichment nodes.

All steps are LangGraph nodes reading/writing a shared `AppState` (Pydantic model). Nodes are thin wrappers in `app/nodes/` delegating to services.

| Layer | Module | Purpose |
|-------|--------|---------|
| State | `app/state.py` | `AppState`, `ImageData`, `WeatherInfo`, `DailyWeather`, `PageDescription`, `PhotobookConfig`, `OutputConfig` |
| Config | `app/config.py` | `OLLAMA_BASE_URL`, `OUTPUT_DIR`, `LENGTH_PRESETS`, `PERSONAS`, blog styles |
| Graph | `app/graph.py` | LangGraph `StateGraph` — mode-dependent branching, 20 nodes |
| Nodes | `app/nodes/*.py` | Pipeline step wrappers (`AppState → AppState`), 20 nodes |
| Services | `app/services/*.py` | Blog business logic (GPX, images, clustering, maps, weather, POI, review, blog, design, PDF) |
| Pipeline | `app/pipeline/*.py` | Higher-level orchestration helper (`enrich_images_with_metadata`) |
| Photobook | `app/photobook/*.py` | Photobook module: plan, generate, render, validate, PDF, image selection, 18 presets |
| Presets | `app/photobook/preset_data/` | 18 JSON preset definitions with CSS grid areas and text constraints |
| CSS | `app/photobook/styles.css` | A4-optimized print CSS with 18 preset grid layouts |
| Database | `app/db/` | SQLAlchemy ORM models, connection, repository pattern |
| API | `app/api/` | FastAPI server, routes, SSE events |
| Utils | `app/utils/` | EXIF helpers, image compression/base64 encoding |
| Frontend | `frontend/` | Svelte 5 + Vite + TypeScript SPA (13 components, 2 stores) |

## Tech Stack

| Category | Technology |
|----------|-----------|
| Pipeline orchestration | [LangGraph](https://pypi.org/project/langgraph/) |
| LLM runtime | [Ollama](https://ollama.com) (Gemma4, Qwen3.6) |
| Backend | Python 3.12, [FastAPI](https://fastapi.tiangolo.com/), [Uvicorn](https://www.uvicorn.org/) |
| Frontend | [Svelte 5](https://svelte.dev/), [Vite 6](https://vitejs.dev/), TypeScript |
| Map rendering | [Folium](https://python-visualization.github.io/folium/), [Selenium](https://www.selenium.dev/) (headless Chrome) |
| PDF generation | Headless Chrome via [Chrome DevTools Protocol](https://chromedevtools.github.io/devtools-protocol/) (CDP) |
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
│   ├── api/                  # FastAPI server, routes, SSE events
│   │   ├── server.py             # Uvicorn entry point, static file serving
│   │   ├── routes.py             # REST endpoints (models, files, pipeline, articles)
│   │   └── events.py             # SSE event types and emitter
│   ├── db/                   # SQLAlchemy persistence layer
│   │   ├── models.py             # ORM models (Article, Image)
│   │   ├── connection.py         # Engine/session factory
│   │   └── repository.py         # CRUD repository pattern
│   ├── nodes/                # LangGraph pipeline nodes (20 nodes)
│   │   ├── process_gpx.py            # GPX parsing and analytics
│   │   ├── load_images.py            # Load images from directory
│   │   ├── extract_metadata.py        # EXIF GPS + timestamp extraction
│   │   ├── clustering_image_node.py   # Density-based photo clustering
│   │   ├── generate_map.py            # Folium map + headless Chrome screenshot
│   │   ├── load_tour_notes_node.py    # Load optional user notes
│   │   ├── enrich_weather_node.py     # Historical weather via Open-Meteo
│   │   ├── enrich_poi_node.py         # POI discovery via Overpass + Wikipedia
│   │   ├── select_images_node.py      # AI image selection for blog
│   │   ├── review_content_node.py     # LLM quality gate for enrichment data
│   │   ├── generate_enriched_map.py   # Map with POIs + weather overlay
│   │   ├── generate_blogpost.py       # Multimodal LLM blog generation
│   │   ├── design_blogpost.py         # CSS styling + persona + length presets
│   │   ├── persist_article.py         # Database persistence
│   │   ├── generate_pdf.py            # Optional blog PDF export (Chrome CDP)
│   │   ├── select_photobook_images_node.py  # AI image selection for photobook
│   │   ├── plan_photobook_node.py          # LLM layout planning (18 presets)
│   │   ├── generate_photobook_node.py      # LLM slot assignment + text generation
│   │   ├── render_photobook_node.py        # HTML assembler from PageDescription
│   │   └── generate_photobook_pdf_node.py  # Photobook PDF via headless Chrome CDP
│   ├── services/             # Business logic (no side effects except file I/O)
│   │   ├── gpx_analytics.py           # GPX parsing, distance/elevation/speed/pauses
│   │   ├── image_loader.py            # Directory scanning, JPEG loading
│   │   ├── metadata_extractor.py      # EXIF GPS/timestamp extraction
│   │   ├── clustering_images.py       # Density-based clustering (20m radius)
│   │   ├── generate_mapimage.py       # Folium + Selenium headless Chrome
│   │   ├── generate_elevation_profile.py # Matplotlib elevation vs. distance chart
│   │   ├── load_tour_notes.py         # File-based note loading
│   │   ├── weather_enricher.py        # Open-Meteo Archive API
│   │   ├── poi_enricher.py            # Overpass API + Wikipedia REST API
│   │   ├── image_selector.py          # Multimodal LLM batch image selection
│   │   ├── content_reviewer.py        # LLM quality gate for enrichment data
│   │   ├── blog_generator.py          # Multimodal LLM blog post generation
│   │   ├── design_blogpost.py         # Persona-aware CSS design
│   │   ├── persist_article.py         # SQLAlchemy CRUD operations
│   │   └── generate_pdf.py            # Headless Chrome CDP PDF export
│   ├── photobook/            # Photobook module
│   │   ├── preset_data/          # 18 JSON preset definitions
│   │   ├── styles.css            # A4 print CSS with 18 grid layouts
│   │   ├── plan.py               # LLM Pass 1: layout planning with variety rules
│   │   ├── generate.py           # LLM Pass 2: slot assignment + text generation
│   │   ├── renderer.py           # HTML assembler from PageDescription list
│   │   ├── validator.py          # Deterministic variety + text enforcement
│   │   ├── generate_pdf.py       # Headless Chrome PDF via CDP
│   │   ├── image_selector.py     # Multimodal batch image selection (tolerant)
│   │   ├── presets.py            # Preset catalog definitions
│   │   └── preset_loader.py      # JSON preset file loader
│   ├── pipeline/             # Higher-level orchestration
│   │   └── process_images.py     # enrich_images_with_metadata helper
│   ├── utils/                # Utility helpers
│   │   ├── exif_helper.py        # Low-level EXIF parsing (GPS, timestamps)
│   │   └── image_utils.py        # Image compression, base64 encoding
│   ├── graph.py              # StateGraph builder with mode-dependent branching
│   ├── state.py              # AppState, ImageData, WeatherInfo, PhotobookConfig, OutputConfig
│   ├── config.py             # OLLAMA_BASE_URL, OUTPUT_DIR, LENGTH_PRESETS, PERSONAS
│   └── models.py             # Empty (reserved for future use)
├── frontend/                 # Svelte 5 + Vite + TypeScript SPA
│   ├── src/
│   │   ├── lib/
│   │   │   ├── stores/
│   │   │   │   ├── pipeline.ts         # SSE event streaming + pipeline state
│   │   │   │   └── router.ts           # Client-side routing
│   │   │   ├── ArticleDetail.svelte    # Full article view with images
│   │   │   ├── ArticleList.svelte      # Filterable article browser
│   │   │   ├── FileDropZone.svelte     # GPX + image drag-and-drop upload
│   │   │   ├── LengthSelector.svelte   # Blog length preset picker
│   │   │   ├── ModelSelector.svelte    # Ollama model picker
│   │   │   ├── SettingsTabs.svelte      # Blog / Photobook settings tabs
│   │   │   ├── NotesInput.svelte       # Optional tour notes textarea
│   │   │   ├── OutputDirInput.svelte   # Output directory config
│   │   │   ├── OutputWindow.svelte     # Live SSE progress + result display
│   │   │   ├── PdfExportCheckbox.svelte # PDF export toggle
│   │   │   ├── PhotobookSizeSelector.svelte # Photobook size picker
│   │   │   ├── RunButton.svelte        # Pipeline start button (auto-detects mode)
│   │   │   ├── StyleSelector.svelte    # Persona picker
│   │   │   └── WildcardCount.svelte    # Max image config
│   │   ├── App.svelte          # Root component
│   │   ├── main.ts             # Entry point
│   │   └── app.css             # Global styles
│   ├── index.html
│   ├── package.json
│   ├── vite.config.ts
│   └── tsconfig.json
├── tests/                    # pytest suite (335 tests, 73 photobook)
│   ├── fixtures/                 # Test data (GPX, images, notes)
│   ├── conftest.py               # Shared fixtures
│   ├── test_api/                 # API integration + enrichment e2e
│   ├── test_services/            # Per-service unit/integration tests
│   ├── test_nodes/               # Per-node unit/integration tests
│   ├── test_graph/               # Graph integration + pipeline e2e
│   ├── test_photobook/           # Photobook-specific tests (73 tests)
│   ├── test_utils/               # Utility tests
│   ├── test_state.py             # AppState model tests
│   ├── test_repository.py        # DB repository tests
│   ├── test_persist_service.py   # Persist service tests
│   ├── test_api_endpoints.py     # API endpoint tests
│   └── test_conftest_fixtures.py # Fixture verification
├── main.py                   # Reference CLI entry point (hardcoded GPX)
├── pyproject.toml            # Project metadata + dependencies
├── uv.lock                   # Locked dependency versions
├── CLAUDE.md                 # Claude Code instructions
└── AGENTS.md                 # OpenCode agent instructions
```

## Running Tests

```bash
uv run pytest tests/ -v
```

335 tests total, 73 of which are photobook-specific. Test structure: `tests/test_services/` (per-service unit tests), `tests/test_nodes/` (per-node tests), `tests/test_graph/` (graph integration + e2e), `tests/test_api/` (API + enrichment e2e), `tests/test_photobook/` (photobook plan/generate/render/validate/pdf/image-selection). Test markers from `pyproject.toml`: `unit` (fast, no external deps), `integration` (real filesystem/mocked network), `e2e` (requires Ollama + Chrome). Fixtures in `tests/fixtures/`.

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

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama API endpoint |
| `OUTPUT_DIR` | `output` | Directory for generated articles and photobooks |
| `DATABASE_URL` | `sqlite:///travel_agent.db` | SQLAlchemy connection string (set to `postgresql://...` for PostgreSQL) |

Default is SQLite — a single `travel_agent.db` file created in the project root on first use. Tables and indexes are auto-created. Images are referenced by file path (no BLOBs).

### Blog Options

**Length presets** (configured in `app/config.py`):

| Preset | Words | Use case |
|--------|-------|----------|
| `short` | 300–650 | Quick overview, social media |
| `normal` | 650–1300 | Standard blog post (default) |
| `detailed` | 1300–2500 | In-depth narrative |

**Style personas** (configured in `app/config.py`):

| Persona | Perspective | Tone |
|---------|-------------|------|
| `mountain_veteran` | First person (Ich) | Experienced outdoor athlete, direct, competent, no exaggeration |
| `field_reporter` | Third person (man, der Wanderer) | Objective, fact-based, dry humor, professional |

### Photobook Options

**Size presets** (configured in `app/state.py`):

| Size | Photos | Page range |
|------|--------|-------------|
| `short` | 12 | 8–12 |
| `normal` | 16 | 14–18 (default) |
| `detailed` | 20 | 20–24 |

## Available Models

Configured in `app/state.py`:

- `gemma4:26b-ctx128k` (default)
- `gemma4:31b-ctx112k`
- `qwen3.6:27b-ctx128k`
- `qwen3.6:35b-ctx128k`

Custom models can be entered interactively in the CLI pipeline (not in the web UI).

## License

This project is for personal/educational use.
