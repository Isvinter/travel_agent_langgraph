# NEXT_SESSION.md — Fortsetzung Codebase-Härtung

**Branch:** `main` (gemerged: `f2127eb`) — 460 Tests grün
**Gefixt in Runde 1:** 10 Critical + 9 High Issues (Commits `c16d463`, `1b83faa`)
**Gefixt in Runde 2:** 11 weitere High Issues (Commit `f2127eb`)

## Quick-Start

```bash
cd ~/Coding/opnecode/travel_agent_langgraph
uv sync                                  # deps installieren
uv run pytest tests/ -m "not e2e" -v    # 460 tests müssen grün sein
```

## ✅ Bereits erledigt (Runde 2 — Commit f2127eb)

| ID | Thema | Umsetzung |
|----|-------|-----------|
| H1 | Node-Wrapping-Duplizierung | `_add_wrapped()` in `app/graph.py` |
| H3 | Haversine-Distanz dedup | `haversine_distance()` in `app/utils/geo_utils.py` |
| H4 | Repository-Duplizierung | `BaseRepository[T]` in `app/db/base_repository.py` |
| H6/H7/H17 | Blog/Photobook LLM-Call-Dedup | `call_ollama()` in photobook image_selector, plan, generate |
| H9 | Map-Generatoren dedup | `_generate_map()` Helper in `app/nodes/generate_map.py` |
| H20 | newSessionId Side-Effect | `getSessionId()` lazy in `frontend/src/lib/stores/pipeline.ts` |
| H21 | Doppelte Reaktivitäts-Trigger | Redundante `[...markedBlocks]` in DraftReview.svelte entfernt |
| H23 | monkeypatch nach create_app | 13 Tests korrigiert in `tests/test_api_endpoints.py` |
| H25 | Lasche Assertion | Strikte `total_distance`-Prüfung in `test_blog_generator.py` |

## Verbleibende High-Issues (4 offen)

| ID | Thema | Datei(en) | Aufwand |
|----|-------|-----------|---------|
| H10 | Frontend ArticleList/PhotobookList dedup | `frontend/src/lib/ArticleList.svelte`, `PhotobookList.svelte` | 30min |
| H18 | Fehlende AbortController Frontend | `frontend/src/lib/DraftReview.svelte` etc. (5+ Komponenten) | 20min |
| H22 | DB-Boilerplate in API-Tests dupliziert | `tests/test_api_endpoints.py` | 20min |
| H24 | Fragiler Mock in Draft-Persistence-Tests | `tests/test_draft_persistence.py:22-31` | 15min |

## Verbleibende Medium-Issues

| ID | Thema | Datei(en) |
|----|-------|-----------|
| M1 | 6× `Dict[str, Any]` im AppState → Pydantic-Models | `app/state.py` |
| M2 | Kein try/except bei fromisoformat | `app/api/routes.py:494-505` |
| M3 | N+1 Query bei a.images | `app/api/routes.py`, `app/db/repository.py` |
| M4 | SQLite ohne WAL-Mode | `app/db/connection.py:16` |
| M5 | Fehlende FK-Indizes | `app/db/models.py:38-47` |
| M9 | Keine model-Validierung gegen AVAILABLE_MODELS | `app/api/routes.py:285-344` |
| M11 | Unbounded asyncio.Queue | `app/api/events.py:25` |
| M14 | Hartcodiertes output_dir | `app/nodes/generate_map.py:_generate_map()` |
| M17 | ImageData-Feldverlust bei Kompression | `app/nodes/render_photobook_node.py:65-70` |

## Konkrete Fix-Anleitungen für verbleibende High-Issues

### H18: AbortController Pattern

```typescript
// In jeder datenladenden Komponente:
let aborted = false;

$effect(() => {
    aborted = false;
    loadData();
    return () => { aborted = true; };
});

async function loadData() {
    const res = await fetch(url);
    if (aborted) return;
    // ... state update
}
```

Betroffene Komponenten: `DraftReview.svelte`, `ArticleDetail.svelte`, `PhotobookDetail.svelte`, `ArticleList.svelte`, `PhotobookList.svelte`

## Wichtige Notizen

- **Tests vor jedem Commit:** `uv run pytest tests/ -m "not e2e" -v`
- **Code-Kommentare auf Deutsch**
- **Minimale, chirurgische Änderungen** — keine großen Refactors in einem Commit
- **uv ist der einzige Package Manager**
- **Neuer Shared-Code:** `app/services/ollama_client.py` — alle LLM-Calls nutzen `call_ollama()`
- **Neuer Shared-Code:** `app/db/base_repository.py` — generisches `BaseRepository[T, F]`
- **Neuer Shared-Code:** `app/utils/geo_utils.py` — `haversine_distance()`
- **Neue Helper:** `app/utils/tour_metadata.py::build_tour_stats()`, `app/nodes/plan_photobook_node.py::_get_photobook_context()`
