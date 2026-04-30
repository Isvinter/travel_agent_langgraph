# Database Persistence for Generated Articles

**Date:** 2026-04-30
**Status:** Approved

## Summary

Add SQLAlchemy-based database persistence for generated blog posts and their resized images. Default to SQLite (zero-config, single file) with a repository pattern allowing future migration to PostgreSQL via a single config change.

## Approach

SQLAlchemy ORM + repository pattern. DB backend configured via `DATABASE_URL` env var, defaulting to `sqlite:///travel_agent.db`. Alembic for schema migrations. The repository isolates DB code from the rest of the application.

**Rejected alternatives:**
- Raw `sqlite3` — simpler but locks us into SQLite, no migration story, harder to test with mock sessions.
- Postgres-only — overkill for single-user local tool, adds Docker dependency.

## Database Schema

### `articles` — one row per generated blog post

| Column | Type | Source |
|---|---|---|
| `id` | INTEGER PK (auto-increment) | auto |
| `title` | TEXT (nullable) | extracted from markdown H1 |
| `tour_date` | DATE | GPX `points[0].time` (first trackpoint timestamp) |
| `tour_duration_hours` | REAL | `(end_time - start_time).total_seconds() / 3600` |
| `tour_duration_source` | TEXT (nullable) | `'gpx'` or `'photos'` — which timestamps were used |
| `generation_timestamp` | TIMESTAMP | `datetime.now()` at generation time |
| `gpx_file` | TEXT | path to source GPX file |
| `total_distance_km` | REAL | from GPXStats.total_distance_m / 1000 |
| `elevation_gain_m` | REAL | from GPXStats.elevation_gain_m |
| `elevation_loss_m` | REAL | from GPXStats.elevation_loss_m |
| `image_count` | INTEGER | number of resized images used in article |
| `markdown_content` | TEXT | full markdown text |
| `html_content` | TEXT | full HTML |
| `markdown_path` | TEXT | file path (e.g. `output/2026-05-01_14-30-00/..._blogpost.md`) |
| `html_path` | TEXT | file path |
| `model_used` | TEXT | e.g. `gemma4:26b-ctx128k` |
| `notes` | TEXT | raw tour notes fed into prompt |
| `created_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP |

### `article_images` — one row per image referenced in article

| Column | Type |
|---|---|
| `id` | INTEGER PK (auto-increment) |
| `article_id` | INTEGER FK → articles(id) ON DELETE CASCADE |
| `image_path` | TEXT (relative, e.g. `./images/01_DSCF1234.jpg`) |
| `is_map` | BOOLEAN DEFAULT FALSE |
| `is_elevation_profile` | BOOLEAN DEFAULT FALSE |

### Indexes

- `articles.tour_date` — date range queries
- `articles.generation_timestamp` — "recently generated" ordering
- `articles.tour_duration_hours` — duration range queries

### Tour Duration Logic

1. **GPX primary:** Extract `points[0].time` and `points[-1].time` from `GPXStats.points`. If both non-null, `duration = (end - start)`, source = `'gpx'`.
2. **Photos fallback:** If GPX has no timestamps, use `max(photo.timestamp) - min(photo.timestamp)` from selected images. Source = `'photos'`.
3. **Neither available:** `tour_duration_hours = NULL`, `tour_duration_source = NULL`.

## Architecture

### New Module: `app/db/`

```
app/db/
  __init__.py
  connection.py    # SQLAlchemy engine/session factory + get_db() dependency
  models.py        # ORM models: Article, ArticleImage
  repository.py    # ArticleRepository class (CRUD + filtered queries)
```

`connection.py` reads `DATABASE_URL` from env, defaults to `sqlite:///travel_agent.db`. On first access, creates all tables if they don't exist.

`repository.py` exposes:
- `insert(article_data: dict, images: list[dict]) -> int` — insert article + images, return article id
- `list(filters: ArticleFilters) -> tuple[list[Article], int]` — filtered + paginated query, returns (articles, total_count)
- `get_by_id(id: int) -> Article | None`
- `delete(id: int) -> bool` — deletes from DB (cascade handles images)

### Pipeline Integration

New LangGraph node `persist_article` added after `generate_blog_post`:

```
... → generate_blog_post → persist_article → END
```

- **Node** (`app/nodes/persist_article.py`): Thin wrapper, reads `AppState.blog_post`, `AppState.gpx_stats`, `AppState.images`, `AppState.notes`, `AppState.model`.
- **Service** (`app/services/persist_article.py`): Maps AppState fields to dict, calls `ArticleRepository.insert()`. Emits SSE event on success/failure.

Existing code unchanged:
- `blog_generator.py` stays focused on generation — no DB code added.
- `gpx_analytics.py` already exposes `TrackPoint.time` — no changes needed.

### Dependencies Added to `pyproject.toml`

```
"sqlalchemy>=2.0",
"alembic>=1.14",
```

## API Endpoints

Three new endpoints in `app/api/routes.py`:

### `GET /api/articles` — list with optional filters

Query parameters:
| Param | Type | Example |
|---|---|---|
| `tour_date_from` | date | `2026-04-01` |
| `tour_date_to` | date | `2026-04-30` |
| `duration_min` | float | `2.0` (hours) |
| `duration_max` | float | `8.0` |
| `generated_from` | datetime | `2026-04-01T00:00:00` |
| `generated_to` | datetime | `2026-04-30T23:59:59` |
| `limit` | int | `20` (default) |
| `offset` | int | `0` (default) |

Response: `{ "articles": [...], "total": 42 }` — summary only (no markdown/HTML content).

### `GET /api/articles/{id}` — full article detail

Response: `{ "article": { ..., markdown_content, html_content, images: [...] } }`

### `DELETE /api/articles/{id}` — delete article

Deletes DB row (cascade removes `article_images` rows), then removes `output/<timestamp>/` directory from disk via `shutil.rmtree`.

Response: `{ "deleted": id }`

## Frontend Additions

New Svelte routes:
- `/articles` — list view with filter bar (date range pickers, duration range, generation date). Table/grid of articles. Click navigates to detail.
- `/articles/{id}` — renders `html_content` inline. Back navigation to list.

Navigation link added to existing layout (header/sidebar).

## Error Handling

- **DB unavailable:** Repository raises `DatabaseError`. API returns 500 with message. Pipeline generation still succeeds — persistence is best-effort, files are on disk regardless.
- **Persist failure:** `persist_article` node catches exceptions, emits warning SSE event, sets `article_id: None` in state. Pipeline completes.
- **File system errors on delete:** `shutil.rmtree` is try/except — if files are missing, DB row is still removed.
- **No unique constraints:** Re-running the same GPX+photos creates a new article row (different `generation_timestamp`). User can delete duplicates via API.

## Testing

All tests use SQLite `:memory:` — no Docker needed.

- `tests/test_repository.py` — unit: insert, list with each filter, get_by_id, delete
- `tests/test_persist_article.py` — unit: mock AppState, call service, verify DB row
- `tests/test_api.py` — integration: add test cases for GET/DELETE endpoints alongside existing tests

## Migration

Single Alembic migration creates both tables. Alembic config at `app/db/alembic/`. Migration runs automatically on first DB access via `Base.metadata.create_all()` fallback — no manual `alembic upgrade` needed for initial setup.
