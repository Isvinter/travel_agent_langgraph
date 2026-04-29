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
- **No tests, linters, or formatters are configured.** There is nothing to run for verification beyond manual execution.
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
