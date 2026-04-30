# Travel Agent LangGraph

Automatically turn GPX hiking tracks and tour photos into richly illustrated, long-form blog posts — powered by a [LangGraph](https://langchain-oss.github.io/langgraph/) pipeline and local multimodal LLMs via [Ollama](https://ollama.com).

## Features

- **GPX Analytics** — parses track files, computes distance, elevation, speed stats, and detects rest pauses
- **Image ingestion** — loads photos from a directory, extracts EXIF GPS coordinates and timestamps
- **Location clustering** — groups geotagged photos taken at the same spot (density-based, 20 m radius)
- **Map generation** — renders an interactive Folium map and captures it as a PNG via headless Chrome
- **Elevation profile** — Matplotlib chart of elevation vs. distance
- **AI image selection** — multimodal LLM selects the best photos for the blog (batched, iterative)
- **AI blog generation** — multimodal LLM writes a narrative travel blog post with embedded images, map, and elevation profile
- **Outputs** — Markdown + HTML files with compressed JPEG images in a timestamped `output/` directory
- **Web UI** — Svelte 5 frontend with drag-and-drop file uploads and live SSE progress streaming
- **REST API** — FastAPI backend with `/api/pipeline/run`, `/api/pipeline/stream/{id}`, file upload endpoints

## Architecture

```
process_gpx → load_images → extract_metadata → clustering_images → generate_map_image → load_tour_notes → select_images → generate_blog_post
```

All steps are LangGraph nodes that read and write a shared `AppState` (Pydantic model). Nodes are thin wrappers in `app/nodes/` that delegate to pure functions in `app/services/`.

| Layer | Module | Purpose |
|-------|--------|---------|
| State | `app/state.py` | `AppState` (images, clusters, GPX stats, notes, blog_post) + `ImageData` |
| Graph | `app/graph.py` | LangGraph `StateGraph` definition — nodes, edges, entry/finish points |
| Nodes | `app/nodes/*.py` | Pipeline step wrappers (`AppState → AppState`) |
| Services | `app/services/*.py` | Business logic: GPX parsing, image loading, EXIF extraction, clustering, map generation, blog generation, image selection |
| API | `app/api/` | FastAPI server, routes, SSE event manager |
| Utils | `app/utils/` | Low-level EXIF helpers |
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
| Image processing | [Pillow](https://python-pillow.org/) |
| GPX parsing | [gpxpy](https://pypi.org/project/gpxpy/) |
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
uv run uvicorn app.api.server:app --host 0.0.0.0 --port 8000
```

FastAPI serves both the API and the built Svelte static files from `frontend/dist/`.

## Project Structure

```
.
├── app/
│   ├── api/            # FastAPI server, routes, SSE events
│   ├── nodes/          # LangGraph pipeline nodes (thin wrappers)
│   ├── services/       # Business logic (no side effects except file I/O)
│   ├── utils/          # EXIF helpers
│   ├── graph.py        # StateGraph builder + run_pipeline()
│   └── state.py        # AppState Pydantic model
├── frontend/           # Svelte 5 + Vite + TypeScript SPA
├── tests/              # pytest suite (unit, integration, e2e)
├── data/               # Runtime input data (gitignored)
│   ├── gpx/
│   ├── images/
│   ├── notes/
│   └── uploads/
├── output/             # Generated blog posts (gitignored)
├── main.py             # CLI entry point (reference only — hardcoded GPX path)
├── pyproject.toml      # Dependencies and project config
└── uv.lock             # Lock file
```

## Running Tests

```bash
uv run pytest tests/ -v
```

Test markers: `unit` (fast, no external deps), `integration` (real filesystem), `e2e` (requires Ollama + Chrome).

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/models` | List available Ollama models |
| `POST` | `/api/files/upload` | Upload a file (multipart, session cookie) |
| `DELETE` | `/api/files/{filename}` | Delete an uploaded file |
| `POST` | `/api/pipeline/run` | Start a pipeline run → returns `run_id` |
| `GET` | `/api/pipeline/stream/{run_id}` | SSE stream of pipeline progress events |
| `GET` | `/api/pipeline/result/{run_id}` | Retrieve completed pipeline result |

## Available Models

Configured in `app/state.py`:

- `gemma4:26b-ctx128k` (default)
- `gemma4:31b-ctx128k`
- `qwen3.6:35b-ctx128k`

Custom models can be entered interactively in the CLI pipeline.

## License

This project is for personal/educational use.
