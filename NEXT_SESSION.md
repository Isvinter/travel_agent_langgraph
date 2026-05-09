# NEXT_SESSION.md — Fortsetzung Codebase-Härtung

**Worktree:** `.worktrees/bugfix-codebase-hardening` (Branch: `bugfix/codebase-hardening`)
**Letzter Commit:** `1b83faa` — 460 Tests grün
**Bereits gefixt:** 10 Critical + 9 High Issues (Commits `c16d463`, `1b83faa`)

## Quick-Start für neue Session

```bash
cd ~/Coding/opnecode/travel_agent_langgraph/.worktrees/bugfix-codebase-hardening
uv sync                                  # deps installieren
uv run pytest tests/ -m "not e2e" -v    # 460 tests müssen grün sein
```

## Verbleibende Issues (aus CODEBASE_ANALYSIS_REPORT.md)

### High Priority (ca. 15, noch offen)

| ID | Thema | Datei(en) | Aufwand |
|----|-------|-----------|---------|
| H1 | Node-Wrapping-Duplizierung | `app/graph.py:107-149` | 30min |
| H3 | Haversine-Distanz 3× dupliziert | `app/services/generate_mapimage.py`, `app/services/poi_enricher.py` | 20min |
| H4 | Repository-Code-Duplizierung (~90%) | `app/db/repository.py`, `app/db/photobook_repository.py` | 45min |
| H6 | Blog/Photobook image_selector dedup | `app/services/image_selector.py`, `app/photobook/image_selector.py` | 30min |
| H7 | Blog/Photobook generate_pdf dedup | `app/services/generate_pdf.py`, `app/photobook/generate_pdf.py` | 30min |
| H9 | Map-Generatoren dedup | `app/nodes/generate_map.py`, `app/nodes/generate_enriched_map.py` | 20min |
| H10 | Frontend ArticleList/PhotobookList dedup | `frontend/src/lib/ArticleList.svelte`, `PhotobookList.svelte` | 30min |
| H17 | Doppelte Base64-Encodierung Photobook | `app/photobook/image_selector.py` | 15min |
| H18 | Fehlende AbortController Frontend | `frontend/src/lib/DraftReview.svelte` etc. (5+ Komponenten) | 20min |
| H20 | newSessionId Side-Effect beim Modul-Import | `frontend/src/lib/stores/pipeline.ts:58-62` | 10min |
| H21 | Doppelte Reaktivitäts-Trigger | `frontend/src/lib/DraftReview.svelte:169,182` | 15min |
| H22 | DB-Boilerplate in API-Tests dupliziert | `tests/test_api_endpoints.py` | 20min |
| H23 | monkeypatch nach create_app in Tests | `tests/test_api_endpoints.py:163-168` (7 Tests) | 15min |
| H24 | Fragiler Mock in Draft-Persistence-Tests | `tests/test_draft_persistence.py:22-31` | 15min |
| H25 | Lasche Assertion in Blog-Generator-Test | `tests/test_services/test_blog_generator.py:64` | 5min |

### Medium Priority (wichtigste)

| ID | Thema | Datei(en) |
|----|-------|-----------|
| M1 | 6× `Dict[str, Any]` im AppState → Pydantic-Models | `app/state.py` |
| M2 | Kein try/except bei fromisoformat | `app/api/routes.py:494-505` |
| M3 | N+1 Query bei a.images | `app/api/routes.py`, `app/db/repository.py` |
| M4 | SQLite ohne WAL-Mode | `app/db/connection.py:16` |
| M5 | Fehlende FK-Indizes | `app/db/models.py:38-47` |
| M9 | Keine model-Validierung gegen AVAILABLE_MODELS | `app/api/routes.py:285-344` |
| M11 | Unbounded asyncio.Queue | `app/api/events.py:25` |
| M14 | Hartcodiertes output_dir | `app/nodes/generate_map.py:14` |
| M17 | ImageData-Feldverlust bei Kompression | `app/nodes/render_photobook_node.py:65-70` |

## Konkrete Fix-Anleitungen für die wichtigsten High-Issues

### H1: Node-Wrapping in graph.py deduplizieren

```python
# In build_graph() einen Helper nutzen:
def _add_wrapped(builder, name, fn, emitter):
    wrapped = _wrap_node(fn, name, emitter) if emitter else fn
    builder.add_node(name, wrapped)

# Dann alle add_node-Aufrufe ersetzen, z.B.:
_add_wrapped(builder, "process_gpx", process_gpx_node, event_emitter)
```

### H3: Haversine in app/utils/geo_utils.py extrahieren

```python
def haversine_distance(lat1, lon1, lat2, lon2) -> float:
    """Berechnet Distanz zwischen zwei Koordinaten in Metern."""
    import math
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
```

### H4: BaseRepository[T] in app/db/repository.py

```python
from typing import Generic, TypeVar
T = TypeVar("T")

class BaseRepository(Generic[T]):
    model: type  # SQLAlchemy model class
    
    def __init__(self, session): ...
    def insert(self, data, image_records) -> int: ...
    def get_by_id(self, id) -> Optional[T]: ...
    def list(self, filters) -> list[T]: ...
    def delete(self, id) -> Optional[T]: ...
    def delete_batch(self, ids) -> int: ...
    def update(self, id, data) -> Optional[T]: ...
```

### H6/H7: Blog/Photobook Dedup

- H6: Gemeinsame Basisklasse in `app/utils/ollama_batch_selector.py`
- H7: Gemeinsame `_html_to_pdf_via_chrome()` in `app/utils/pdf_utils.py`

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

- **Worktree-Konvention:** Alle Edits nur im Worktree `.worktrees/bugfix-codebase-hardening`
- **Tests vor jedem Commit:** `uv run pytest tests/ -m "not e2e" -v`
- **Code-Kommentare auf Deutsch**
- **Minimale, chirurgische Änderungen** — keine großen Refactors in einem Commit
- **uv ist der einzige Package Manager**
- **Neuer Shared-Code:** `app/services/ollama_client.py` wurde bereits erstellt — alle neuen LLM-Calls sollten `call_ollama()` nutzen
- **Neue Helper:** `app/utils/tour_metadata.py::build_tour_stats()`, `app/nodes/plan_photobook_node.py::_get_photobook_context()`
