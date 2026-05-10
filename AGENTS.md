# AGENTS.md

This file provides guidance to OpenCode when working with code in this repository.

## Worktree convention

**When a git worktree exists (e.g., `.worktrees/blog-draft-review/`), ALL edits must be made in the WORKTREE, never in the main tree.** The worktree contains an in-progress feature branch. Changes to the main tree will be lost when the worktree branch is merged.

Note: `.worktrees/` is gitignored — `git status` won't show worktrees as untracked, but they exist on disk and may contain active branches.

## Quick start

```bash
uv sync                          # install deps
uv run python main.py            # run pipeline (reference only — has hardcoded GPX path)
```

Or import and run interactively:

```python
from app.graph import run_pipeline
result = run_pipeline()          # prompts for model selection
```

## Key conventions

- **`uv` is the only package manager** — `requirements.txt` is empty, dependencies live in `pyproject.toml`. Always prefix commands with `uv run`.
- **Tests use `pytest`** — run with `uv run pytest tests/ -v`. Write tests for new features alongside implementation code.
- **Test markers** in `pyproject.toml`: `unit` (fast, no deps), `integration` (real filesystem, mocked network), `e2e` (needs Ollama + Chrome), `asyncio`. Run subset: `uv run pytest tests/ -v -m unit`.
- **Data files are gitignored.** `data/`, `output/`, and `travel_agent.db` are runtime artifacts. Do not commit them.
- **Code comments are in German.** Follow the existing convention when adding comments.
- **Make minimal surgical changes** — target the smallest possible diff. Don't refactor adjacent code unless necessary.

## Architecture

The pipeline uses a single LangGraph `StateGraph` with two mode-dependent execution paths sharing the first 6 nodes:

```
process_gpx → load_images → extract_metadata → clustering_images → generate_map_image → load_tour_notes
                                                                                │
                                                             ┌──────────────────┘
                                                             ↓
                                              mode=photobook │ mode=blog
                                                             ↓
                                    select_photobook_images  enrich_weather
                                              │              ↓
                                       plan_photobook        enrich_poi
                                              │              ↓
                                     generate_photobook    select_images
                                              │              ↓
                                      render_photobook    review_content
                                              │              ↓
                                   generate_photobook_pdf generate_enriched_map
                                              │              ↓
                                     persist_photobook    generate_blog_post
                                              │              ↓
                                            END        design_blogpost
                                                         │        │
                                            review=true  │        │ review=false
                                                         ↓        ↓
                                                   save_draft   persist_article
                                                         │        │
                                                       END  pdf=true│pdf=false
                                                                  ↓        ↓
                                                          generate_pdf    END
                                                                  ↓
                                                                END
```

- **Nodes** (`app/nodes/`) are thin wrappers: `AppState → AppState`
- **Services** (`app/services/`) contain business logic, no side effects except file I/O
- **Photobook** (`app/photobook/`) — layout planning, rendering, validation, 18 preset layouts
- **State** (`app/state.py`) — the shared `AppState` Pydantic model, plus `PhotobookConfig` and `OutputConfig`
- **Config** (`app/config.py`) — `OLLAMA_BASE_URL`, `OUTPUT_DIR`, length presets, personas
- **DB** (`app/db/`) — SQLAlchemy ORM with SQLite (PostgreSQL-ready), Alembic migrations auto-run on first connect

## Prerequisites

- **Ollama must be running locally** (`ollama serve`) — all LLM calls go through Ollama's `/api/chat`
- **Headless Chrome/Chromium** must be installed for Selenium-based map screenshot and CDP-based PDF generation
- **Python ≥3.12** (see `.python-version`)

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama API endpoint (note: non-standard port 11434) |
| `OUTPUT_DIR` | `output` | Runtime output directory for generated articles and photobooks |
| `DATABASE_URL` | `sqlite:///travel_agent.db` | SQLAlchemy connection string. Set to `postgresql://...` for PostgreSQL. |
| `API_KEY` | *(empty)* | Optional API key for production deployments (checked by middleware) |

The DB auto-creates tables and indexes on first use. Alembic migrations in `migrations/` run automatically via `app/db/connection.py`'s `_run_migrations()`. Manual run: `uv run alembic upgrade head`.

## Gotchas

- `main.py` contains a hardcoded GPX path (`/home/stephan-zeibig/Coding/travel_agent_langgraph/data/gpx/Tour.gpx`) — treat it as a reference, not a runnable script on other machines. Use `run_pipeline()` for interactive model selection or `build_graph()` + `graph.invoke(state)` with your own `AppState`.
- `alembic.ini` hardcodes `sqlite:///data/travel_agent.db` but this URL is overridden at runtime by `connection.py` using the `DATABASE_URL` env var. Do not rely on the .ini URL.

## Frontend development

```bash
# Terminal 1: Start FastAPI backend
uv run uvicorn app.api.server:app --reload --host 0.0.0.0 --port 8000

# Terminal 2: Start Svelte dev server (proxies /api to :8000 via vite.config.ts)
cd frontend && npm install && npm run dev

# Terminal 3: Run backend tests
uv run pytest tests/test_api.py -v
```

The frontend is a Svelte 5 + Vite 6 + TypeScript SPA in `frontend/`. Node.js ≥18 required.

**Production:** Build with `cd frontend && npm install && npm run build`, then serve with `uv run uvicorn app.api.server:app --port 8000`. FastAPI serves both API routes and the built Svelte static files from `frontend/dist/`.
