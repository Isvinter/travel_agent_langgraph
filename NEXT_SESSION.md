# NEXT_SESSION.md — Codebase-Härtung Runde 4

**Branch:** `main` (HEAD: `fb9a41a`) — 460 Tests grün
**Gefixt bisher:** Runde 1 (10C+9H), Runde 2 (11H), Runde 3 (4H + 7M)

## Quick-Start

```bash
cd ~/Coding/opnecode/travel_agent_langgraph
uv sync
uv run pytest tests/ -m "not e2e" -v    # 460 tests müssen grün sein
```

## Verbleibende Issues — priorisiert

### Must-Fix (Critical/High — Sicherheit, Datenintegrität, Bugs)

| ID | Thema | Datei(en) | Aufwand |
|----|-------|-----------|---------|
| C1 | `--no-sandbox` in Chrome (Sicherheit) | `generate_pdf.py:75`, `photobook/generate_pdf.py:51` | 10min |
| C2 | Regex-HTML-Sanitizer bypassbar | `utils/html_sanitizer.py` — regex durch `bleach`/`nh3` ersetzen | 20min |
| **R1** | Kein `rollback` bei `commit`-Fehler | `db/base_repository.py` — alle 4 CRUD-Methoden | 15min |
| **R2** | `requests.get/post` ohne Session-Reuse | `ollama_client.py`, `poi_enricher.py`, `weather_enricher.py` | 20min |
| **R3** | `datetime.fromisoformat` auf EXIF-Format | `utils/tour_metadata.py:48` — EXIF ist `YYYY:MM:DD HH:MM:SS` | 10min |
| **R4** | `assert True` (tautologisch) | `tests/test_graph/test_enrichment_graph.py:69` | 10min |
| **R5** | Dead Test (`pass` ohne Assertions) | `tests/test_pipeline_process_images.py:34-38` | 15min |
| **R6** | `time.sleep()` statt `WebDriverWait` | `generate_mapimage.py:163`, `generate_pdf.py:82`, `photobook/generate_pdf.py:60` | 20min |

### Should-Fix (Medium — Qualität, Wartbarkeit)

| ID | Thema | Datei(en) | Aufwand |
|----|-------|-----------|---------|
| **R7** | `_getexif()` private Pillow-API | `services/metadata_extractor.py:56` → `getexif()` | 5min |
| **R8** | THINKING_PATTERN matcht keine Self-Closing-Tags | `services/ollama_client.py:15-18` | 5min |
| **R9** | `load_all_presets()` 5-8× pro Seite (kein Cache) | `photobook/validator.py` + `generate.py` — `@lru_cache` | 10min |
| **R10** | AVAILABLE_MODELS ist mutable `List` | `state.py:31` → `Tuple[str, ...]` | 5min |
| **R11** | Leere Dateien (`exif_helper.py`, `models.py`) | Löschen + Referenzen in AGENTS.md updaten | 5min |

### Nice-to-Have (Low — Aufräumen)

| ID | Thema | Datei(en) | Aufwand |
|----|-------|-----------|---------|
| **R12** | Dead Code: `gpx_analytics()` nie aufgerufen | `services/gpx_analytics.py:224` | 5min |
| **R13** | Dead Code: `generate_blog_post_poc()` | `services/blog_generator.py:502` | 5min |
| **R14** | Double Cleanup in TTL-Handler | `api/events.py:83,97-101` — prüfen ob run_id noch existiert | 5min |
| **R15** | `except Exception` ohne Logging | `services/metadata_extractor.py:9` | 5min |
| **R16** | Keine Frontend-Tests | `frontend/` — Vitest + Testing Library aufsetzen | 2h |
| **R17** | Kein Test für `save_draft` Node | `nodes/save_draft.py` → `tests/test_save_draft.py` | 30min |

### Später (grössere Refactors)

| ID | Thema | Beschreibung |
|----|-------|-------------|
| M1 | 7× `Dict[str, Any]` → Pydantic | `state.py` — `image_clusters`, `metadata`, `blog_post`, `poi_list`, `enrichment_context`, `photobook_plan`, `slots` |
| H1 | Alembic-Migrations | `alembic.ini` + `migrations/` fehlt — `create_all()` reicht nicht für Schema-Migrationen |
| H2 | `print()` → Logger | 174× `print()` durch `logging.getLogger()` ersetzen (Framework existiert in `logging_setup.py`) |
| W24 | Force-Navigation in App.svelte | `$effect` navigiert User weg — Toast statt Redirect |

## Konkrete Fix-Anleitungen

### R1: Rollback bei Commit-Fehlern

```python
# In BaseRepository.insert/delete/delete_batch/update:
try:
    self.session.commit()
except Exception:
    self.session.rollback()
    raise
```

### R2: requests.Session

```python
# Statt requests.get(url):
_session = requests.Session()
_session.headers.update({"User-Agent": "travel-agent/1.0"})
# Dann: _session.get(url) / _session.post(url)
```

### R3: EXIF-Timestamp-Parsing

```python
# Statt datetime.fromisoformat(str(ts)):
# EXIF ist "YYYY:MM:DD HH:MM:SS", nicht ISO 8601
datetime.strptime(ts_str, "%Y:%m:%d %H:%M:%S")
```

### R6: WebDriverWait

```python
# Statt time.sleep(2):
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
WebDriverWait(driver, 10).until(
    EC.presence_of_element_located((By.TAG_NAME, "body"))
)
```

## Wichtige Notizen

- **Tests vor jedem Commit:** `uv run pytest tests/ -m "not e2e" -v`
- **Minimale, chirurgische Änderungen**
- **uv ist der einzige Package Manager**
- **Neuer Shared-Code aus Runde 3:**
  - `frontend/src/lib/utils/format.ts` — `formatDate`, `formatDuration`
  - `frontend/src/lib/utils/sort.ts` — `sortItems`
  - `app/state.py` — Feld `output_dir` im AppState
