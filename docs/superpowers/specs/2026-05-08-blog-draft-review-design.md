# Blog Draft Review & Revision — Design

**Datum:** 2026-05-08
**Scope:** Blog-Artikel (nicht Photobook)
**Architektur-Ansatz:** Pipeline-Stopp + REST Revision API

---

## 1. Zusammenfassung

Vor der Finalisierung eines Blog-Artikels soll der User optional einen Draft prüfen,
Teile davon markieren und mit Anweisungen zur Überarbeitung an das LLM zurücksenden können.
Nach beliebig vielen Revisions-Runden kann der User den Beitrag akzeptieren (→ DB-Persistenz)
oder verwerfen. Die Funktion ist über eine Checkbox in den Blog-Einstellungen aktivierbar;
ohne Aktivierung bleibt das vollautomatische Verhalten unverändert.

---

## 2. Datenmodell

### 2.1 OutputConfig (`app/state.py`)

Neues Feld:

```python
review_enabled: bool = False  # Aktiviert Draft-Review vor Finalisierung
```

### 2.2 Article-Modell (`app/db/models.py`)

Zwei neue Spalten auf `Article`:

| Spalte | Typ | Default | Beschreibung |
|--------|-----|---------|-------------|
| `status` | `String` | `"published"` | `"draft"` oder `"published"` |
| `revision_round` | `Integer` | `0` | Anzahl der durchgeführten Revisionen |

### 2.3 RunPipelineRequest (`app/api/routes.py`)

Neues Feld:

```python
review_enabled: bool = False
```

### 2.4 AppState — kein neues Feld nötig

`review_enabled` ist bereits in `output_config` enthalten, das durch den Pipeline-Code
aus dem Request-Body befüllt wird.

---

## 3. API-Endpoints

### 3.1 POST /api/pipeline/run (erweitert)

Request-Body erhält zusätzlich `review_enabled: bool`.

### 3.2 SSE "done" Event (erweitert)

Wenn `review_enabled=true`, enthält das done-Event ein zusätzliches Feld:

```json
{"type": "done", "article_id": null, "draft_id": 42, "status": "review_ready"}
```

### 3.3 POST /api/articles/{id}/revise (NEU)

```python
class RevisionItem:
    element_type: Literal["paragraph", "image"]
    element_index: int
    original_content: str
    instruction: str  # Freitext-Anweisung, darf leer sein

class RevisionRequest:
    changes: list[RevisionItem]
```

**Response:**

```json
{
  "markdown": "...",
  "html": "...",
  "revision_round": 2,
  "paragraph_count_changed": false
}
```

**Ablauf im Backend:**
1. Draft aus DB laden (muss `status == "draft"` sein)
2. `full_context` zusammenbauen: `notes`, GPX-Stats aus Article-Row; Weather/POI-Infos aus existierendem Markdown extrahieren (keine separate DB-Speicherung nötig)
3. `revise_blog_post()` Service mit aktuellem Markdown + Changes + Kontext + `article.model_used` aufrufen
4. Neuen HTML via `design_blogpost_service()` erzeugen
5. Draft in DB updaten (markdown, html, `revision_round += 1`)
6. Response zurückgeben

### 3.4 POST /api/articles/{id}/publish (NEU)

```json
{}  // Kein Body nötig
```

**Response:** `{"status": "published", "article_id": 42}`

**Ablauf:**
1. Draft aus DB laden
2. `status` auf `"published"` setzen
3. DB-Update (kein erneuter Image-Copy nötig, da `save_draft` bereits alle Assets gespeichert hat)

### 3.5 GET /api/articles (erweitert)

Neuer Query-Parameter `status` für Filterung nach Draft/Published. Bestehende `ArticleFilters`-Klasse erweitern.

### 3.6 DELETE /api/articles/{id} (unverändert)

Funktioniert für Drafts und Published-Artikel gleichermaßen.

---

## 4. Pipeline-Änderungen

### 4.1 Graph (`app/graph.py`)

Conditional Edge nach `design_blogpost`:

```python
def _route_after_design(state: AppState) -> str:
    if state.output_config.review_enabled:
        return "save_draft"
    return "persist_article"

graph.add_conditional_edges("design_blogpost", _route_after_design, {
    "save_draft": "save_draft",
    "persist_article": "persist_article",
})
```

### 4.2 Neuer Node: `save_draft` (`app/nodes/save_draft.py`)

Schlanker Node, der den bestehenden `persist_article()`-Service mit `status="draft"` aufruft.
Speichert markdown, html, Metadaten und images in der DB.

### 4.3 Hintergrund-Pipeline (`app/api/routes.py`)

`_run_pipeline_in_background()`: Im done-Event `draft_id` statt `article_id` setzen, wenn `review_enabled=true`.

---

## 5. LLM Revision Service

### 5.1 Neue Datei: `app/services/revise_blogpost.py`

```python
def revise_blog_post(
    current_markdown: str,
    changes: list[dict],
    full_context: dict,          # {notes, gpx_stats, weather, poi_list} aus Article-Row + enrichment_context
    available_images: list[str],
    output_config: OutputConfig,
    model: str,                  # Aus Article.model_used oder Request-Body
) -> dict:
```

### 5.2 Prompt-Strategie

- **System-Nachricht:** Persona + Style aus `OutputConfig`
- **User-Nachricht:**
  1. Vollständiger Original-Artikel als Kontext
  2. Liste der markierten Stellen mit Index, Original-Content und User-Anweisung
  3. Strikte Anweisung: Nur markierte Absätze umschreiben, Rest unverändert lassen
  4. Kohärenz zu umgebenden Absätzen wahren
- **Keine Multimodal:** Reiner Text-Call (Bilder wurden initial analysiert), spart Tokens

### 5.3 Validierung

- Prüft ob Absatz-Anzahl gleich geblieben ist → Feld `paragraph_count_changed` in Response
- Kein Hard-Fail bei Strukturänderung, nur Info an Frontend

---

## 6. Frontend

### 6.1 Neue Stores (`pipeline.ts`)

```typescript
export const reviewEnabled = writable<boolean>(false);
export const currentDraftId = writable<string | null>(null);
```

**RunResult-Type erweitern:** `draft_id?: string` hinzufügen.

### 6.2 Neue Komponenten

| Komponente | Pfad | Beschreibung |
|---|---|---|
| `ReviewCheckbox.svelte` | `frontend/src/lib/ReviewCheckbox.svelte` | Checkbox "Entwurf vor Veröffentlichung prüfen", bindet an `reviewEnabled` |
| `DraftReview.svelte` | `frontend/src/lib/DraftReview.svelte` | Kern-Komponente: Draft anzeigen + markieren + revidieren |

### 6.3 Geänderte Komponenten

| Komponente | Änderung |
|---|---|
| `SettingsTabs.svelte` | Zeigt `ReviewCheckbox` an (nur im Blog-Mode) |
| `RunButton.svelte` | Sendet `review_enabled` im Request-Body |
| `App.svelte` | Bei done-Event mit `draft_id`: `currentDraftId` setzen → `DraftReview` mounten |
| `ArticleList.svelte` | Drafts visuell als "Entwurf" kennzeichnen |

### 6.4 DraftReview.svelte — Verhalten

1. **Mount:** `GET /api/articles/{id}` → HTML + Markdown laden
2. **Rendering:** HTML parsen in Blöcke (`<p>`, `<figure>`, `<h2>`). Jeder Block erhält `data-index` und Click-Handler.
3. **Markieren:** Klick auf Block → Toggle. Markierte Blöcke bekommen blauen Rand + `#N`-Badge. Erscheinen im Änderungs-Panel.
4. **Anweisungen:** Pro markiertem Element ein Textfeld für Freitext-Anweisung.
5. **Absenden:** Button "Änderungen senden" → `POST /api/articles/{id}/revise` → neuen Draft empfangen → UI aktualisieren.
6. **Akzeptieren:** Button "Beitrag übernehmen" → `POST /api/articles/{id}/publish` → Navigation zu `#article/{id}`.
7. **Abbrechen:** Button "Verwerfen" → `DELETE /api/articles/{id}` → zurück zur Pipeline-Ansicht.

### 6.5 Layout

Split-Layout:
- **Links (60%):** Gerenderter HTML-Artikel. Überschriften nicht markierbar. Absätze und Bilder sind via Klick markierbar.
- **Rechts (40%):** Änderungs-Panel mit Liste markierter Elemente und ihren Anweisungsfeldern, plus Aktions-Buttons.

### 6.6 Routing

Hash-basiertes Routing erweitern:
- `#draft/{id}` → `DraftReview` anzeigen
- `#article/{id}` → `ArticleDetail` (unverändert)
- Nach Accept: Navigation zu `#article/{id}`

### 6.7 Pipeline-Integration

Wenn die Pipeline im Hintergrund läuft:
1. OutputWindow zeigt Live-Log (wie bisher)
2. Bei done-Event mit `draft_id` → Router navigiert zu `#draft/{id}`
3. DraftReview lädt und zeigt den Draft

---

## 7. Fehlerbehandlung

| Situation | Verhalten |
|---|---|
| Revision schlägt fehl (Ollama down) | 500 Response, Frontend zeigt Error-Toast, behält aktuellen Draft-Status |
| LLM ändert Absatz-Anzahl | `paragraph_count_changed: true` in Response, Frontend zeigt Warnung |
| Leere Anweisung bei markiertem Element | Erlaubt — LLM schreibt trotzdem um |
| Draft nie finalisiert | Bleibt in DB, in ArticleList als "Entwurf" sichtbar, manuell löschbar |
| Browser-Reload während Review | Draft aus DB laden (Markierungen gehen verloren — akzeptabel) |
| "Änderungen senden" ohne Markierungen | Button disabled bis mindestens 1 Element markiert ist |
| Pipeline crashed vor Draft-Speicherung | Standard SSE Error-Event, kein Draft in DB |

---

## 8. Test-Strategie

### Backend-Tests

- `tests/test_revise_api.py`: Test für `/revise` und `/publish` Endpoints
- `tests/test_revise_service.py`: Test für `revise_blog_post()` Prompt-Konstruktion
- `tests/test_draft_persistence.py`: Test für `save_draft` Node + DB Status
- Vorhandene Pipeline-Tests: Sicherstellen dass nichts bricht (unverändert bei `review_enabled=false`)

### Frontend-Tests

- Manuelle Prüfung: Checkbox aktiviert → Draft erscheint nach Pipeline
- Manuelle Prüfung: Checkbox deaktiviert → Pipeline läuft wie bisher durch
- Manuelle Prüfung: Markieren, Revidieren, Akzeptieren Zyklus

### Mocking

- `revise_blog_post()` in API-Tests mocken (keine echte Ollama-Abhängigkeit)
- DB-fixtures mit draft-Artikeln für Revision-Tests
