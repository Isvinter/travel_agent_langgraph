# PDF-Export für Artikel — Design

**Datum:** 2026-05-04
**Status:** approved, ready for implementation plan

## Überblick

Zwei Zugangswege für den PDF-Export von Artikeln:

1. **Pipeline-Menü** — Checkbox "Als PDF exportieren" in der Sidebar. Wenn aktiviert, wird nach Pipeline-Abschluss das PDF automatisch generiert und als Download im Browser ausgelöst.
2. **Artikel-Detailansicht** — Grüner Button "Als PDF exportieren" in der Toolbar, links neben dem roten "Löschen"-Button. Löst sofort einen PDF-Download für den jeweiligen Artikel aus.

Beide Wege nutzen denselben Backend-Service zur PDF-Generierung.

## Technische Entscheidung: Headless Chrome via Selenium CDP

Begründung:
- Headless Chrome ist bereits als Abhängigkeit für Map-Screenshots (`app/services/generate_mapimage.py`) vorhanden
- Vollständige CSS3-Unterstützung (Flexbox, Grid etc.) — pixelgenaue Wiedergabe des Artikels
- Zukunftssicher für komplexere Layouts
- Selenium wird bereits genutzt; `Page.printToPDF` via CDP gibt feine Kontrolle über Papierformat, Ränder, Druckhintergrund
- Keine neuen System-Abhängigkeiten

## Architektur

```
┌─ Pipeline Sidebar ──────────────────────────────────────────────┐
│  [x] Als PDF exportieren  ← neue Checkbox (PdfExportCheckbox)    │
│  ▶ Pipeline starten                                              │
└──────────────────────────────────────────────────────────────────┘
                              │ POST /api/pipeline/run
                              │ { pdf_export: true, ... }
                              ▼
┌─ Backend Pipeline ──────────────────────────────────────────────┐
│  ... persist_article → generate_pdf_node (nur wenn pdf_export)  │
│  SSE done: { pdf_available: true, article_id: N }               │
└──────────────────────────────────────────────────────────────────┘
                              │ SSE event
                              ▼
┌─ Frontend SSE Handler ──────────────────────────────────────────┐
│  window.open(`/api/articles/${article_id}/pdf`, "_blank")       │
└──────────────────────────────────────────────────────────────────┘
                              │ GET /api/articles/{id}/pdf
                              ▼
┌─ Backend API ───────────────────────────────────────────────────┐
│  routes.py: GET /api/articles/{id}/pdf                          │
│  → generate_pdf(html_content, output_dir)                       │
│  → Response(pdf_bytes, media_type="application/pdf")            │
└──────────────────────────────────────────────────────────────────┘
```

```
┌─ Artikel-Detailansicht ─────────────────────────────────────────┐
│  [← Zurück zur Liste]    [Als PDF exportieren] [🗑 Löschen]    │
│                           ↑ grüner Button, links vom Löschen    │
│                           window.open(`/api/articles/${id}/pdf`) │
└──────────────────────────────────────────────────────────────────┘
```

## Backend — neue Komponenten

### 1. Service: `app/services/generate_pdf.py`

```python
def generate_pdf(html_content: str, article_output_dir: str) -> bytes:
    """Wandelt Artikel-HTML via Headless Chrome in PDF um.

    Args:
        html_content: Vollständiges HTML des Artikels (mit ./images/ Pfaden)
        article_output_dir: Verzeichnis, in das der Artikel geschrieben wurde
                           (enthält images/ Unterordner)

    Returns:
        PDF als Bytes
    """
```

Ablauf:
1. `./images/` Pfade im HTML durch absolute `file:///` Pfade ersetzen
2. `max-width: 780px` auf `max-width: 100%` setzen (Volle Breite für PDF)
3. CSS für Drucklayout injizieren: `@page { size: A4; margin: 15mm; }`
4. HTML in temporäre Datei schreiben
5. Selenium Chrome (headless) starten
6. `file:///` URL im Driver laden
7. `Page.printToPDF` CDP-Kommando ausführen mit Parametern:
   - `printBackground: True`
   - `paperWidth: 8.27` (A4 in Zoll)
   - `paperHeight: 11.69`
   - `marginTop/Bottom/Left/Right: 0.59` (15mm)
8. Base64-dekodierte PDF-Daten zurückgeben
9. Temporäre Dateien im `finally`-Block aufräumen

Fehlerbehandlung:
- `TimeoutError` bei Selenium-Timeout → `HTTPException(504, "PDF-Generierung hat zu lange gedauert")`
- `WebDriverException` (Chrome nicht verfügbar) → `HTTPException(502, "Chrome/Chromium ist nicht verfügbar")`
- HTML-Inhalt ist `None` oder leer → `HTTPException(400, "Kein HTML-Inhalt für PDF-Generierung")`

### 2. API-Endpoint: `GET /api/articles/{article_id}/pdf`

In `app/api/routes.py`:

```python
@router.get("/articles/{article_id}/pdf")
def export_article_pdf(article_id: int, session=Depends(get_session)):
    """Generiert PDF für einen Artikel und liefert es als Download aus."""
    repo = ArticleRepository(session)
    article = repo.get_by_id(article_id)
    if not article:
        raise HTTPException(404, "Artikel nicht gefunden")
    if not article.html_content:
        raise HTTPException(400, "Artikel hat keinen HTML-Inhalt")

    # Output-Verzeichnis aus html_path ableiten
    output_dir = str(Path(article.html_path).parent) if article.html_path else ""

    pdf_bytes = generate_pdf(article.html_content, output_dir)

    # Dateiname: Titel ohne Sonderzeichen, Fallback "artikel"
    safe_title = re.sub(r"[^\w\- ]", "", article.title or "artikel").strip()[:100]
    filename = f"{safe_title}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-cache",
        },
    )
```

### 3. Pipeline-Integration

**Zustandsmodell (`app/state.py`):**
- `OutputConfig` erhält neues Feld: `pdf_export: bool = False`

**API-Modell (`app/api/routes.py`):**
- `RunPipelineRequest` erhält neues Feld: `pdf_export: bool = False`

**Graph-Node (`app/nodes/generate_pdf.py`):**
- Neue optionale Node `generate_pdf_node(state: AppState) -> AppState`
- Nur aktiv wenn `state.output_config.pdf_export == True`
- Ruft `generate_pdf` auf und speichert Ergebnis in `state.generated_pdf_bytes`
- Bedingte Kante im Graph: `persist_article → generate_pdf_node` nur bei `pdf_export=True`, sonst direkt zu `__end__`

**SSE-Done-Event:**
- Wenn `pdf_export=True` und PDF erfolgreich generiert, enthält das `done`-Event:
  ```json
  {
    "status": "success",
    "article_id": 42,
    "pdf_available": true
  }
  ```

## Frontend — Änderungen

### 1. Store (`pipeline.ts`)

Neues writable store (nach Zeile 46):
```typescript
export const pdfExport = writable<boolean>(false);
```

### 2. Neue Komponente: `PdfExportCheckbox.svelte`

Einfache Checkbox im Stil der bestehenden Formularelemente. Bindet bidirektional an den `pdfExport`-Store. Wird in `App.svelte` zwischen `StyleSelector` und der `run-section` eingefügt.

### 3. Änderung: `RunButton.svelte`

- Importiert `pdfExport` aus stores
- Fügt `pdf_export: get(pdfExport)` zum POST-Body hinzu
- Im SSE-`done`-Event-Handler: prüft auf `pdf_available: true` und löst `window.open()` aus

### 4. Änderung: `App.svelte`

- Importiert `<PdfExportCheckbox />`
- Platziert es nach `<StyleSelector />`, vor dem `run-section`-Div (Zeile 48-49)

### 5. Änderung: `ArticleDetail.svelte`

**Toolbar (Zeilen 80-90):**
- Toolbar-Rechts wird zu einer Flex-Gruppe mit Gap zusammengefasst
- Neuer grüner Button "Als PDF exportieren" links vom Löschen-Button
- `handlePdfExport()`-Funktion öffnet `window.open("/api/articles/{id}/pdf", "_blank")`

**CSS-Zusätze:**
```css
.pdf-btn {
  background: #27ae60;
  color: white;
  padding: 0.4rem 0.75rem;
  font-size: 0.8rem;
}
.pdf-btn:hover {
  background: #219a52;
}
.toolbar-right {
  display: flex;
  gap: 0.5rem;
}
```

## Datenfluss — Übersicht

```
Pipeline-Weg:
  PdfExportCheckbox → pdfExport store → RunButton POST → Backend Route
  → OutputConfig.pdf_export → Graph.lazy_edge → generate_pdf_node
  → SSE done {pdf_available} → Frontend → window.open(download-URL)

Artikelansicht-Weg:
  ArticleDetail "Als PDF exportieren" Button → window.open("/api/articles/{id}/pdf")
  → Backend Route → Repository.get_by_id → generate_pdf() → Response(PDF)
```

## Fehlerfälle

| Fehler | HTTP-Status | Frontend-Reaktion |
|---|---|---|
| Artikel nicht gefunden | 404 | Standard-Fehlerseite |
| Kein HTML-Inhalt | 400 | Browser zeigt leere Seite / Download schlägt fehl |
| Chrome nicht verfügbar | 502 | Browser zeigt Server-Fehler |
| PDF-Generierung Timeout | 504 | Browser zeigt Gateway Timeout |
| Bildpfade existieren nicht | 200 (PDF mit Platzhaltern) | Chrome zeigt gebrochene Bild-Icons im PDF |

## Tests

### Unit-Tests (`tests/test_generate_pdf.py`)
- `test_rewrite_image_paths` — prüft Pfad-Ersetzung von `./images/` zu `file:///`
- `test_inject_print_css` — prüft CSS-Injektion (@page, max-width)
- `test_empty_html_raises` — `generate_pdf` mit None/leerem HTML wirft Exception

### Integration-Tests
- `test_pdf_endpoint_returns_pdf` — GET `/api/articles/{id}/pdf` liefert `application/pdf` und PDF-Bytes
- `test_pdf_endpoint_404` — GET mit nicht-existenter ID → 404

### E2E-Tests (optional, benötigt Chrome + Ollama)
- Pipeline-Durchlauf mit `pdf_export=True` prüft, dass `done`-Event `pdf_available` enthält

## Abhängigkeiten

Keine neuen Python-Abhängigkeiten. Chrome/Chromium und Selenium sind bereits in `pyproject.toml` deklariert (`selenium>=4.41.0`).
