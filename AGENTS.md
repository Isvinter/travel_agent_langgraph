# AGENTS.md

This file provides guidance to OpenCode when working with code in this repository.

## Quick start

```bash
uv sync                          # install deps
uv run python main.py            # run pipeline
```

Or import and run interactively:

```python
from app.graph import run_pipeline
result = run_pipeline()          # prompts for model selection
```

## Key conventions

- **`uv` is the only package manager** — `requirements.txt` is empty, dependencies live in `pyproject.toml`. Always prefix commands with `uv run`.
- **Tests use `pytest`** — run with `uv run pytest tests/ -v`. Write tests for new features alongside implementation code.
- **Data files are gitignored.** `data/` and `output/` are runtime artifacts. Do not commit them.
- **Code comments are in German.** Follow the existing convention when adding comments.
- **Make minimal surgical changes** — see `CLAUDE.md` for the full editing philosophy.

## Architecture (see CLAUDE.md for full details)

```
process_gpx → load_images → extract_metadata → clustering_images → generate_map_image → load_tour_notes → select_images → generate_blog_post
```

- **Nodes** (`app/nodes/`) are thin wrappers: `AppState → AppState`
- **Services** (`app/services/`) contain business logic, no side effects except file I/O
- **State** (`app/state.py`) — the shared `AppState` Pydantic model

## Prerequisites

- **Ollama must be running locally** (`ollama serve`) — the blog generator calls Ollama's `/api/chat`
- **Headless Chrome/Chromium** must be installed for Selenium-based map screenshot generation (`app/services/generate_mapimage.py`)
- **Python ≥3.12** (see `.python-version`)

## Gotchas

- `main.py` contains a hardcoded GPX path — agents should treat it as a reference, not a runnable script on other machines. Use `run_pipeline()` for interactive model selection or `build_graph()` + `graph.invoke(state)` with your own `AppState`.
- `app/models.py` is empty and unused — do not add code there.

## Frontend development

```bash
# Terminal 1: Start FastAPI backend
uv run uvicorn app.api.server:app --reload --host 0.0.0.0 --port 8000

# Terminal 2: Start Svelte dev server (proxies /api to :8000)
cd frontend && npm run dev

# Terminal 3: Run backend tests
uv run pytest tests/test_api.py -v
```

The frontend is a Svelte 5 + Vite + TypeScript SPA in `frontend/`. Node.js ≥18 required.

**Production:** Build with `cd frontend && npm run build`, then serve with `uv run uvicorn app.api.server:app --port 8000`. FastAPI serves both API routes and the built Svelte static files.
