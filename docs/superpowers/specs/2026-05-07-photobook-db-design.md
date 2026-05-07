# Database Persistence for Photobooks

**Date:** 2026-05-07
**Status:** Draft

## Summary

Fotobuecher werden analog zu Blogartikeln persistent in die SQLite-Datenbank geschrieben. Neue Tabellen `photobooks` und `photobook_images` spiegeln das bestehende `articles`/`article_images`-Muster. Der transiente `/api/photobook/{run_id}/pdf`-Endpunkt entfaellt zugunsten persistierter PDF-Abrufe. Das Frontend erhaelt unter "Datenbank" Sub-Tabs zum Umschalten zwischen Blogartikeln und Fotobuechern.

## Approach

Separate Tabellen `photobooks` + `photobook_images` nach dem Vorbild von `articles` + `article_images`. Eigener `PhotobookRepository`, eigene `/api/photobooks`-Endpunkte, eigene Frontend-Komponenten.

**Rejected alternatives:**
- Single table mit Type-Discriminator — viele NULL-Werte, vermischte Entitaeten, Umbau des ArticleRepository noetig.
- `articles`-Tabelle erweitern — Name passt nicht mehr, markdown_content waere fuer Fotobuecher immer NULL, Spalten-Wildwuchs.

## Database Schema

### `photobooks` — eine Zeile pro generiertem Fotobuch

| Column | Type | Source |
|--------|------|--------|
| `id` | INTEGER PK (auto-increment) | auto |
| `title` | TEXT (nullable) | aus GPX-Daten / Fotobuch-Titel |
| `tour_date` | DATE | GPX `points[0].time` |
| `tour_duration_hours` | REAL | `(end - start) / 3600` |
| `tour_duration_source` | TEXT (nullable) | `'gpx'` oder `'photos'` |
| `generation_timestamp` | TIMESTAMP | `datetime.now()` |
| `gpx_file` | TEXT | Pfad zur GPX-Datei |
| `total_distance_km` | REAL | aus GPXStats |
| `elevation_gain_m` | REAL | aus GPXStats |
| `elevation_loss_m` | REAL | aus GPXStats |
| `image_count` | INTEGER | Anzahl verwendeter Bilder |
| `html_content` | TEXT | gerendertes Fotobuch-HTML |
| `html_path` | TEXT | Pfad auf Disk |
| `model_used` | TEXT | z.B. `gemma4:26b-ctx128k` |
| `notes` | TEXT | Tour-Notizen |
| `created_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP |
| `pdf_path` | TEXT (nullable) | Pfad zur PDF-Datei |
| `page_count` | INTEGER (nullable) | Anzahl Seiten im Fotobuch |
| `photobook_size` | TEXT (nullable) | `'short'` / `'normal'` / `'detailed'` |

Keine `markdown_content`/`markdown_path`-Spalten (Fotobuecher haben kein Markdown).

### `photobook_images` — eine Zeile pro Bild im Fotobuch

| Column | Type |
|--------|------|
| `id` | INTEGER PK (auto-increment) |
| `photobook_id` | INTEGER FK → photobooks(id) ON DELETE CASCADE |
| `image_path` | TEXT NOT NULL |
| `is_map` | BOOLEAN DEFAULT FALSE |
| `is_elevation_profile` | BOOLEAN DEFAULT FALSE |

### Indexes

- `photobooks.tour_date`
- `photobooks.generation_timestamp`
- `photobooks.tour_duration_hours`

(Analog zu den bestehenden Indexes auf `articles`.)

## Backend Implementation

### Neue Dateien

| Datei | Zweck |
|-------|-------|
| `app/db/photobook_repository.py` | `PhotobookRepository` — insert, list, get_by_id, delete, delete_batch |
| `app/nodes/persist_photobook.py` | Node-Wrapper: `persist_photobook_node(state) -> state` |
| `app/services/persist_photobook.py` | Business-Logik: Daten extrahieren, HTML sanitizen, in DB schreiben |

### Zu aendernde Dateien

| Datei | Aenderung |
|-------|-----------|
| `app/db/models.py` | `Photobook` + `PhotobookImage` SQLAlchemy-Modelle hinzufuegen |
| `app/db/connection.py` | `get_db()` session-Factory (unveraendert, arbeitet mit beiden Repos) |
| `app/api/routes.py` | Neue Route-Handler: list_photobooks, get_photobook, delete_photobook, delete_photobooks_batch, get_photobook_pdf, get_photobook_image |
| `app/graph.py` | `persist_photobook`-Node in den Fotobuch-Pipeline-Zweig einfuegen (nach `render_photobook`) |
| `app/state.py` | `metadata["photobook_id"]` analog zu `metadata["article_id"]` |

### API Endpoints (alle unter `/api`)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/photobooks` | Liste mit Query-Filtern |
| `GET` | `/api/photobooks/{id}` | Detail inkl. HTML und Bilder |
| `DELETE` | `/api/photobooks/{id}` | Loeschen + Dateien auf Disk |
| `POST` | `/api/photobooks/delete-batch` | Batch-Delete, Body: `{ids: [...]}` |
| `GET` | `/api/photobooks/{id}/pdf` | PDF-Download |
| `GET` | `/api/photobooks/{id}/images/{filename}` | Bild ausliefern |

Query-Filter fuer `/api/photobooks` (analog zu `/api/articles`):
- `tour_date_from`, `tour_date_to`
- `duration_min`, `duration_max`
- `generated_from`, `generated_to`
- `limit` (default 50), `offset` (default 0)

Response-Format:
```json
{
  "photobooks": [{...}],
  "total": 42
}
```

### Serialisierung

**`_photobook_to_summary(p: Photobook)`** — Felder fuer Listen-Ansicht:
id, title, tour_date, tour_duration_hours, tour_duration_source, generation_timestamp, total_distance_km, elevation_gain_m, elevation_loss_m, image_count, model_used, notes, photobook_size, page_count

**`_photobook_to_detail(p: Photobook)`** — Alle Felder inkl. html_content (rewritten), html_path, pdf_path, gpx_file, images-Array.

**`_rewrite_html_content(html, photobook_id)`** — Analog zur Blog-Variante: `<style>` entfernen, `<body>` extrahieren, Bildpfade auf `/api/photobooks/{id}/images/` umschreiben.

### Pipeline-Integration

Der Fotobuch-Pipeline-Zweig in `graph.py` wird um einen Node `persist_photobook` erweitert, der nach `render_photobook` laeuft. Der Node extrahiert Metadaten aus `AppState` und schreibt den Eintrag ueber den `PhotobookRepository`.

Zu extrahierende Daten aus `AppState`:
- `photobook_title` (oder aus GPX-Daten ableiten)
- `photobook_html`, `photobook_html_path`
- `photobook_pdf_path`
- `photobook_images` (Liste von ImageData)
- `photobook_size` (aus PhotobookConfig)
- GPX-Statistiken und Tour-Daten (wie bei Blog-Artikel)

## Frontend Changes

### Routing (`frontend/src/lib/stores/router.ts`)

Zwei neue Hash-Routen:
- `#/photobooks` → `{page: "photobooks"}`
- `#/photobooks/{id}` → `{page: "photobook", id: N}`

### App.svelte

Unter dem "Datenbank"-Tab erscheinen zwei Sub-Tabs:
```
[ Pipeline | Datenbank ]
              ├── [ Blogartikel | Fotobücher ]
```

Wenn `rightTab === "datenbank"` und kein Sub-Tab aktiv → `ArticleList` (default).
Wenn Sub-Tab "Fotobücher" aktiv → `PhotobookList`.
Detail-Routing wie gehabt ueber `rt.page`.

### Neue Komponenten

**`PhotobookList.svelte`** — analog zu `ArticleList.svelte`:
- Tabelle mit Spalten: Checkbox, Titel, Tour-Datum, Dauer, Distanz, Hoehenmeter, Bilder, Groesse, "Ansehen", "Loeschen"
- Filter: tour_date_from, tour_date_to, duration_min, duration_max
- Batch-Delete mit Confirmation-Dialog
- Fetcht `GET /api/photobooks?...`

**`PhotobookDetail.svelte`** — analog zu `ArticleDetail.svelte`:
- Titel, Metadaten-Leiste, Notes (collapsible), HTML-Rendering via `{@html}`
- Buttons: "Zurueck zur Liste", "Als PDF exportieren", "Loeschen"
- PDF-Download via `GET /api/photobooks/{id}/pdf`

### Types (in `PhotobookList.svelte` und `PhotobookDetail.svelte`)

```typescript
interface PhotobookSummary {
  id: number;
  title: string | null;
  tour_date: string | null;
  tour_duration_hours: number | null;
  total_distance_km: number | null;
  elevation_gain_m: number | null;
  image_count: number | null;
  photobook_size: string | null;
  page_count: number | null;
  generation_timestamp: string | null;
}

interface PhotobookDetail extends PhotobookSummary {
  html_content: string | null;
  html_path: string | null;
  pdf_path: string | null;
  gpx_file: string | null;
  model_used: string | null;
  notes: string | null;
  images: PhotobookImage[];
}

interface PhotobookImage {
  id: number;
  image_path: string;
  is_map: boolean;
  is_elevation_profile: boolean;
}
```

## Transienter Endpunkt

Der bestehende Endpunkt `GET /api/photobook/{run_id}/pdf` und das zugehoerige `event_manager`-PDF-Handling werden entfernt. PDFs werden stattdessen ueber `GET /api/photobooks/{id}/pdf` aus der Datenbank abgerufen. Keine Ruecksicht auf parallele alte Runs noetig — die Pipeline laeuft nur einmal pro Session.

## App.svelte Sub-Tab State

Der Sub-Tab-Zustand wird als lokale Svelte-Variable `dbSubTab: "articles" | "photobooks"` in `App.svelte` gehalten. Bei Klick auf "Datenbank" wechselt `rightTab` auf `"datenbank"`. Die Sub-Tabs erscheinen nur, wenn `rightTab === "datenbank"`. Bei Wechsel zu "Pipeline" wird `dbSubTab` nicht zurueckgesetzt (bleibt beim naechsten "Datenbank"-Klick erhalten).

## Gotchas

- Der `persist_photobook`-Node muss **nach** `render_photobook` und `generate_photobook_pdf` im Graphen stehen, da sowohl `html_path` als auch `pdf_path` benoetigt werden.
- `AppState.metadata` wird um `photobook_id` ergaenzt, damit die API bei `GET /api/pipeline/result/{run_id}` die ID zurueckgeben kann.
- Fotobuch-Bilder liegen unter `output/photobook_{timestamp}/images/` — der `_rewrite_html_content`-Helper braucht diesen Pfad.
- Das Loeschen eines Fotobuchs muss analog zum Loeschen eines Artikels auch das `output/photobook_{timestamp}/`-Verzeichnis aufraeumen.
