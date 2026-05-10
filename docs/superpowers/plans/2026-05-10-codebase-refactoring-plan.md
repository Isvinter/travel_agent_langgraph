# Refactoring-Plan: Verbleibende Codebase-Verbesserungen

**Datum:** 2026-05-10 | **Basis:** Audit-Report | **Branch:** noch zu erstellen

---

## Übersicht

Nach dem Audit wurden 27 chirurgische Bugfixes umgesetzt (3 Commits: `21db141`, `5e90759`, `ff3c532`).
Die verbleibenden Issues sind strukturelle Refactors, die mehr Planung erfordern und in separaten Sessions bearbeitet werden sollten.

---

## Refactor 1: Frontend-Komponenten-Deduplizierung

**Betroffene Dateien:**
- `frontend/src/lib/ArticleList.svelte` (521 Zeilen)
- `frontend/src/lib/PhotobookList.svelte` (511 Zeilen)

**Problem:** ~90% identischer Code: Filter-Logik, Sortierung, Checkbox-Selektion, Delete-Dialog, Tabellen-Rendering, CSS. Nur API-Endpoints, Spaltennamen und `formatSize` unterscheiden sich.

**Lösung:** Gemeinsame generische `EntityList.svelte`-Komponente mit Props/Slots:
- `entityType: "article" | "photobook"`
- `columns: ColumnDef[]`
- `formatFunctions: Record<string, Function>`
- `apiPrefix: string`

**Risiko:** Mittel — Svelte 5 Runes müssen korrekt propagieren.

**Aufwand:** ~2h

---

## Refactor 2: Detail-Komponenten-Deduplizierung

**Betroffene Dateien:**
- `frontend/src/lib/ArticleDetail.svelte` (220 Zeilen)
- `frontend/src/lib/PhotobookDetail.svelte` (180 Zeilen)

**Problem:** ~70% identisch: fetch, loading/error states, delete dialog, metadata display. Nur Content-Rendering unterscheidet sich (HTML vs iframe).

**Lösung:** Gemeinsame `EntityDetail.svelte` mit Slot für Content-Bereich.

**Risiko:** Gering

**Aufwand:** ~1h

---

## Refactor 3: DraftReview DOM-Walk-Deduplizierung

**Betroffene Datei:** `frontend/src/lib/DraftReview.svelte`

**Problem:** Zwei nahezu identische `walk()`-Funktionen (`parseHtml` L72-103 und `getRenderedHtml` L112-139) — 90% duplizierte DOM-Traversal-Logik.

**Lösung:** Eine `walk()`-Funktion mit Callback für Attribute (block-index, data-marked) statt zwei getrennter Funktionen.

**Risiko:** Gering

**Aufwand:** ~30min

---

## Refactor 4: Validator-Repair-Logik-Deduplizierung

**Betroffene Datei:** `app/photobook/validator.py`

**Problem:** `enforce_fallback` und `_replace_preset` teilen ~70% identische Slot-Repair-Logik (Image-Indizes extrahieren, Text-Slots migrieren, Placeholder füllen, Title-Slot sicherstellen, Dedup). Unterschied: `enforce_fallback` hat Preset-Upgrade-Logik.

**Lösung:** Extrahiere gemeinsame Logik in `_repair_slots(preset, old_slots)` und rufe sie von beiden Funktionen aus auf.

**Risiko:** Mittel — Photobook-Visual-Tests (wenn vorhanden) müssen bestehen.

**Aufwand:** ~1h

---

## Refactor 5: Session-Management-Konsolidierung

**Betroffene Dateien:**
- `app/services/ollama_client.py:17` — `_session = requests.Session()` (nie geschlossen)
- `app/services/poi_enricher.py:14` — eigene `_session`
- `app/services/weather_enricher.py:14` — eigene `_session`

**Problem:** Drei separate `requests.Session`-Instanzen mit duplizierten Headern und je eigenen Connection-Pools. `ollama_client`-Session wird nie geschlossen (Leak im API-Server).

**Lösung:** Zentrale `get_session()`-Factory in `app/services/http_client.py`, die von allen drei Modulen genutzt wird. Mit `atexit`-Cleanup für CLI-Nutzung und FastAPI-Lifespan-Event für Server.

**Risiko:** Gering

**Aufwand:** ~45min

---

## Refactor 6: Prompt-Template-Extraktion

**Betroffene Dateien:**
- `app/services/blog_generator.py` — Prompts als f-Strings
- `app/services/content_reviewer.py` — Prompts als f-Strings
- `app/photobook/generate.py` — 88-zeiliger `_build_generate_prompt`
- `app/photobook/plan.py` — `_build_plan_prompt`

**Problem:** LLM-Prompts sind hartcodiert in Python f-Strings. Prompt-Iteration erfordert Code-Änderungen und Deployments.

**Lösung:** Prompts in separate `.txt`-Dateien unter `app/prompts/` auslagern, mit Platzhalter-Syntax (z.B. `{image_count}`, `{context}`). Ein `PromptLoader`-Modul lädt und füllt Templates.

**Alternativ:** Minimal-Variante: Prompts als `TEMPLATE = """..."""`-Konstanten am Modul-Anfang sammeln, getrennt von der Business-Logik.

**Risiko:** Mittel — Prompt-Änderungen können LLM-Output-Qualität beeinflussen.

**Aufwand:** ~2h

---

## Refactor 7: Frontend-Test-Infrastruktur

**Betroffene Dateien:** `frontend/` (ganzes Verzeichnis, keine Tests vorhanden)

**Problem:** Null Test-Coverage im Frontend. Kein Test-Runner, keine Test-Dependencies in `package.json`.

**Lösung:**
1. Vitest + `@testing-library/svelte` installieren
2. `vitest.config.ts` erstellen
3. Unit-Tests für Utilities (`format.ts`, `sort.ts`)
4. Unit-Tests für Stores (`pipeline.ts`, `router.ts`, `theme.ts`)
5. Component-Tests für kritische Komponenten (`DraftReview`, `FileDropZone`)

**Risiko:** Gering

**Aufwand:** ~3h

---

## Refactor 8: Dead Code & Minimalsäuberung

**Betroffene Dateien:**
- `app/state.py:164` — `selected_image_count: Optional[int] = None` (nie verwendet)
- `frontend/src/lib/stores/pipeline.ts:72` — `sessionId` Store (nie importiert)
- `frontend/src/lib/stores/router.ts:1` — `import { derived }` (nie verwendet)
- `frontend/tsconfig.json` — `noUnusedLocals: false`, `noUnusedParameters: false`

**Lösung:** Löschen + TypeScript-Strictness aktivieren.

**Risiko:** Minimal

**Aufwand:** ~15min

---

## Refactor 9: Datenbank-Index auf `articles.status`

**Betroffene Datei:** `app/db/connection.py:61-72`

**Problem:** `/api/articles`-Endpoint filtert nach `status`, aber kein DB-Index existiert → Full Table Scan.

**Lösung:** `_ensure_indexes()` um `idx_articles_status` auf `(status, generation_timestamp)` erweitern. Alembic-Migration ergänzen.

**Risiko:** Gering (SQLite/PostgreSQL handled CREATE INDEX IF NOT EXISTS)

**Aufwand:** ~15min

---

## Refactor 10: Fehlende Generics & Type Hints

**Betroffene Dateien:**
- `app/db/base_repository.py:102` — `_apply_filters(self, q, filters: F)` → `q` untyped
- `app/services/persist_article.py:27` — `images: list` → `List[ImageData]`
- Diverse Services mit `Any`-Typen für `gpx_stats`, `weather`, etc.

**Lösung:** Gezielte Typ-Annotationen ergänzen, `Any` durch konkrete Typen ersetzen wo eindeutig.

**Risiko:** Minimal

**Aufwand:** ~30min

---

## Priorisierung

| Prio | Refactor | Aufwand | Impact |
|------|----------|---------|--------|
| 1 | Dead Code + TypeScript Strictness | 15min | Niedrig |
| 2 | DB-Index `articles.status` | 15min | Mittel (Performance) |
| 3 | Session-Konsolidierung | 45min | Mittel (Ressourcen) |
| 4 | Type Hints ergänzen | 30min | Mittel (Wartbarkeit) |
| 5 | DraftReview Walk-Deduplizierung | 30min | Mittel (Wartbarkeit) |
| 6 | Validator-Repair-Deduplizierung | 1h | Mittel (Wartbarkeit) |
| 7 | FE Detail-Deduplizierung | 1h | Hoch (Wartbarkeit) |
| 8 | FE List-Deduplizierung | 2h | Hoch (Wartbarkeit) |
| 9 | Prompt-Template-Extraktion | 2h | Hoch (Iterierbarkeit) |
| 10 | Frontend-Test-Infrastruktur | 3h | Hoch (Qualität) |

**Empfohlene Reihenfolge:** 1-4 (schnelle Wins) → 5-6 (Python-Cleanup) → 7-8 (FE-Cleanup) → 9-10 (größere Umbauten)

---

## Abhängigkeiten

- **Refactor 2** hängt von **Refactor 1** ab (Detail nutzt gleiche Patterns wie List)
- **Refactor 9** vor **Refactor 8** (Prompt-Design vor Template-Extraktion verstehen)
- Keine anderen Abhängigkeiten zwischen den Refactors

---

## Test-Strategie

- Alle Refactors: bestehende 464 Tests müssen grün bleiben
- Refactors 1-2: manuelle Smoke-Tests im Frontend (Liste laden, filtern, navigieren)
- Refactor 5: `test_ollama_client.py`, `test_poi_enricher.py`, `test_weather_enricher.py` prüfen
- Refactor 9: Dedizierte Prompt-Unit-Tests schreiben
- Refactor 10: Tests nach jedem Meilenstein hinzufügen
