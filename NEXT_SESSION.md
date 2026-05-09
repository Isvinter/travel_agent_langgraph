# NEXT_SESSION.md — Codebase-Härtung Runde 5

**Branch:** `fix/hardening-round-4` (worktree: `.worktrees/hardening-round-4`)
**Startpunkt:** 464 Tests grün
**Gefixt in Runde 4:** C1, C2, R1–R15, R17 (19 Issues)

## Quick-Start

```bash
cd ~/Coding/opnecode/travel_agent_langgraph/.worktrees/hardening-round-4
uv sync
uv run pytest tests/ -m "not e2e" -v    # 464 tests müssen grün sein
```

## Verbleibende Issues — empfohlene Reihenfolge

### 1. M2: `print()` → Logger (HIGH Impact, LOW Risk)

174 `print()`-Statements auf 34 Dateien. Infrastruktur existiert in `app/logging_setup.py`.

**Vorgehen:**
- Pro Datei: `import logging` + `logger = logging.getLogger(__name__)` am Dateianfang
- Emoji-basierte Heuristik:
  - `❌` → `logger.error(...)`
  - `⚠️` → `logger.warning(...)` 
  - `✅` / `📸` / `📡` / `💾` / `📍` / `🤖` → `logger.info(...)`
- `print(f"⚠️ ...")` → `logger.warning("...")` (f-string auflösen, Emoji entfernen)
- Keine `print()` ohne Emoji → `logger.info(...)`

**Dateien nach print()-Häufigkeit (Top 10):**
| Datei | Count |
|-------|-------|
| `nodes/render_photobook_node.py` | 14 |
| `photobook/generate.py` | 12 |
| `services/blog_generator.py` | 11 |
| `nodes/generate_blogpost.py` | 10 |
| `services/poi_enricher.py` | 9 |
| `nodes/process_gpx.py` | 8 |
| `nodes/design_blogpost.py` | 8 |
| `nodes/load_images.py` | 7 |
| `api/routes.py` | 6 |
| `services/weather_enricher.py` | 5 |

**Gotcha:** `app/logging_setup.py` hat selbst ein `print()` auf Zeile 31 — das ist Absicht (soll loggen BEVOR Logging konfiguriert ist). Nicht anfassen.

---

### 2. M1: 7× `Dict[str, Any]` → Pydantic-Modelle (MEDIUM Risk, MEDIUM Impact)

Betroffene Felder in `app/state.py` und ihre Pydantic-Ziele:

| Feld | Aktueller Typ | Zieldmodell | Nutzung (# Files) |
|---|---|---|---|
| `image_clusters` | `List[Dict[str, Any]]` | `ImageCluster` (id, images, center_lat, center_lon, ...) | 3 |
| `metadata` | `Dict[str, Any]` | Kein neues Modell — existierende `tour_stats`/`tour_date`/`tour_duration` als flache Felder in AppState | 2 |
| `blog_post` | `Optional[Dict[str, Any]]` | `BlogPostResult` (success, markdown, html, file_paths, selected_images) | 14 |
| `poi_list` | `List[Dict[str, Any]]` | `POI` (name, type, lat, lon, distance_km, wiki_extract?) | 4 |
| `enrichment_context` | `Dict[str, Any]` | `EnrichmentContext` (weather_summary, kept_pois, discarded_weather_fields, image_ratings, coherence_score, flags) | 10 |
| `photobook_plan` | `Optional[Dict[str, Any]]` | `PhotobookPlan` (pages: List[PagePlan], ...) | 7 |
| `slots` (in `PageDescription`) | `List[Dict[str, Any]]` | `PageSlot` (slot_id, text?, image_index?) | 14 |

**Vorgehen:**
1. Neue Pydantic-Modelle in `app/state.py` definieren (hinter die existierenden, z.B. nach `PageDescription`)
2. Felder in `AppState` und `PageDescription` umstellen
3. Alle Zugriffe auf Dict-Keys durch Attribut-Zugriffe ersetzen (z.B. `poi["name"]` → `poi.name`)
4. `metadata`-Dict auflösen: `metadata.get("article_id")` → `state.article_id`, Tour-Stats direkt auf `state` mit `Optional[]`

**Betroffene Dateien (alle brauchen Update):**
`state.py`, `nodes/clustering_image_node.py`, `nodes/generate_blogpost.py`, `nodes/design_blogpost.py`, `nodes/save_draft.py`, `nodes/persist_article.py`, `nodes/enrich_poi_node.py`, `nodes/review_content_node.py`, `nodes/select_images_node.py`, `nodes/process_gpx.py`, `nodes/generate_map.py`, `nodes/plan_photobook_node.py`, `nodes/generate_photobook_node.py`, `nodes/render_photobook_node.py`, `nodes/persist_photobook.py`, `services/blog_generator.py`, `services/content_reviewer.py`, `services/persist_article.py`, `services/persist_photobook.py`, `photobook/validator.py`, `photobook/generate.py`, `photobook/renderer.py`, `photobook/plan.py`, `photobook/presets.py`, `graph.py`, `api/routes.py`

**Achtung:** Tests nutzen Dict-Literale — müssen auf Pydantic-Instanzen umgestellt werden. Ca. 30-40 Testdateien betroffen.

---

### 3. H1: Alembic-Migrationen (LOW Risk, Infrastructure)

Aktuelles Problem: `Base.metadata.create_all()` in `app/db/connection.py:21` kann Tabellen nur ERSTELLEN, nicht migrieren. Bei Schema-Änderungen (neue Spalten, Constraints) schlägt das fehl.

**Vorgehen:**
1. `uv run alembic init migrations` im Projekt-Root
2. `alembic.ini` anpassen: `sqlalchemy.url = sqlite:///data/travel_agent.db`
3. `migrations/env.py`: `target_metadata = Base.metadata` (import von `app.db.models`)
4. `uv run alembic revision --autogenerate -m "initial"` → erzeugt Initial-Migration
5. `migrations/versions/` committen
6. `connection.py` anpassen: `create_all()` durch `alembic.command.upgrade()` ersetzen oder beides behalten (Fallback für neue DBs)

**Tabellen (4 Stück):** `articles`, `article_images`, `photobooks`, `photobook_images`

---

### 4. W24: Force-Navigation in App.svelte (LOW Risk, UX)

**Problem:** `$effect` in `frontend/src/App.svelte:24-30` navigiert den User gewaltsam weg:
- Wenn Pipeline läuft → zwingend zu `/pipeline`
- Wenn Draft-ID gesetzt → zwingend zu `/draft/:id`

**Fix:** `$effect`-Block durch Toast-Notification ersetzen:
- Statt `navigateTo(...)` → Toast-Komponente einblenden mit "Pipeline läuft — [Zur Pipeline]" Link
- Toast nach 8s auto-dismissen
- User kann selbst entscheiden, ob er navigieren will

**Dateien:** `App.svelte:24-30` (entfernen), neue `Toast.svelte` Komponente, `Toast`-Store

---

## Wichtige Notizen

- **Tests vor jedem Schritt:** `uv run pytest tests/ -m "not e2e" -v`
- **uv ist der einzige Package-Manager** (kein pip!)
- **Minimale, chirurgische Änderungen** — pro Phase committen
- **Kein Alembic vor M1/M2** — sonst generiert man Migrationen für Änderungen die man gleich wieder umbaut
- **M2 vor M1** — Logger ist harmlos und reduziert den Diff in M1 (weil man dort sonst `print()` UND neue Felder ändert)
- **print()-Ersatz-Regel:** Weder Emoji noch f-string-Formatierung ins Log — nur Klartext. Emojis im Log sind redundant weil Log-Level (ERROR/WARNING/INFO) die Semantik tragen.
