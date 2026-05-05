# Fotobuch-Frontend-Integration — Design-Dokument

**Datum:** 2026-05-05
**Status:** Design-Phase
**Ziel:** Integration der bestehenden Fotobuch-Backend-Pipeline in das Svelte-Frontend mit zweispaltiger Sidebar

---

## 1. Überblick

Das Backend (`app/photobook/`) und die LangGraph-Nodes für die Fotobuch-Generierung sind bereits implementiert. Dieses Dokument beschreibt die Frontend-Integration: eine zweispaltige Sidebar, in der Blog- und Fotobuch-Einstellungen unabhängig voneinander konfiguriert werden können, mit Modus-Umschaltung via Tabs und separaten Run-Buttons.

### Design-Entscheidungen

| Entscheidung | Gewählte Option |
|---|---|
| Pipeline-Mode-UI | Segmented Control (Blog | Fotobuch) — kein "Beides" |
| Sidebar-Layout | Zweispaltig 50:50, Sidebar auf ~680px verbreitert |
| Modell-Auswahl | Geteilt zwischen Blog und Fotobuch |
| Fotobuch-Umfang | Kurz / Mittel / Lang mit LLM-Spielraum |
| PDF-Export Fotobuch | Immer an (kein Checkbox) |
| Fotobuch-Download | Auto-Download nach Pipeline-Ende |
| Fotobuch-DB | Nicht in diesem Scope — folgt in eigener Session |

---

## 2. Frontend-Layout

### Aktuelles Layout (vorher)
```
┌──────────────────────────────────────────┐
│ Sidebar (340px)    │  Main (Output)       │
│                    │                      │
│ Model              │  OutputWindow        │
│ Files              │                      │
│ OutputDir          │                      │
│ Notes              │                      │
│ Length             │                      │
│ Style              │                      │
│ PDF-Export         │                      │
│ [▶ Starten]        │                      │
└──────────────────────────────────────────┘
```

### Neues Layout
```
┌─────────────────────────────────────────────────────┐
│ Sidebar (~680px)              │  Main (Output)      │
│                               │                     │
│ [Blog] [Fotobuch]  ← Tabs     │  OutputWindow       │
│ Model (shared)                │                     │
│ Files (shared)                │                     │
│ ┌──────────┬──────────────┐   │                     │
│ │ Blog     │ Fotobuch     │   │                     │
│ │          │              │   │                     │
│ │ Artikell.│ Umfang       │   │                     │
│ │ Kurz     │ Kurz         │   │                     │
│ │ Normal ◉ │ Mittel ◉     │   │                     │
│ │ Lang     │ Lang         │   │                     │
│ │          │ 14-18 Seiten │   │                     │
│ │ Stil     │              │   │                     │
│ │ Veteran ◉│ PDF (immer)  │   │                     │
│ │ Reporter │              │   │                     │
│ │          │              │   │                     │
│ │ PDF-Exp. │              │   │                     │
│ │ Notizen  │              │   │                     │
│ │ ┌──────┐ │              │   │                     │
│ │ │Text..│ │              │   │                     │
│ │ └──────┘ │              │   │                     │
│ │ [▶ Start]│ [▶ Start]    │   │                     │
│ └──────────┴──────────────┘   │                     │
└─────────────────────────────────────────────────────┘
```

- Inaktive Spalte wird auf `opacity: 0.45` gesetzt
- Mode-Tabs steuern, welche Spalte "aktiv" ist und welcher Run-Button sichtbar
- Modell und Datei-Upload sind geteilte Komponenten über beiden Spalten

---

## 3. Komponenten-Änderungen

### Neue Komponenten

| Datei | Zweck |
|---|---|
| `ModeTabs.svelte` | Blog / Fotobuch Tab-Umschaltung |
| `PhotobookSizeSelector.svelte` | Kurz / Mittel / Lang für Fotobuch-Umfang |

### Geänderte Komponenten

| Datei | Änderung |
|---|---|
| `App.svelte` | Layout: Sidebar auf 680px, zwei Spalten unter den geteilten Feldern |
| `RunButton.svelte` | Akzeptiert `mode`-Prop, sendet unterschiedliche Payloads |
| `OutputWindow.svelte` | Auto-Download auch bei Fotobuch-PDF (nicht nur Blog) |
| `PdfExportCheckbox.svelte` | Nur in Blog-Spalte sichtbar |

### Entfernte Komponenten

Keine.

---

## 4. Store-Erweiterungen (`pipeline.ts`)

```ts
// Neue Stores
export const pipelineMode = writable<"blog" | "photobook">("blog");
export const photobookSize = writable<"short" | "normal" | "detailed">("normal");

// Bestehende Stores unverändert (selectedModel, pipelineFiles, etc.)
// PdfExport immer true bei Photobuch — kein Store nötig
```

### Store-Verwendung

| Store | Verwendet in |
|---|---|
| `pipelineMode` | ModeTabs, App.svelte (opacity-Logik), RunButton |
| `photobookSize` | PhotobookSizeSelector, RunButton (Payload) |
| `selectedModel` | ModelSelector (unverändert, shared) |
| `pipelineFiles` | FileDropZone (unverändert, shared) |

---

## 5. API-Änderungen

### `POST /api/pipeline/run` — Request-Body

**Vorher (nur Blog):**
```json
{
  "model": "gemma4:26b-ctx128k",
  "gpx_file": "...",
  "image_files": [...],
  "output_dir": "output",
  "notes": "",
  "article_length": "normal",
  "style_persona": "mountain_veteran",
  "pdf_export": false,
  "wildcard_max": 12
}
```

**Neu (Routing-Felder):**
```json
{
  "model": "gemma4:26b-ctx128k",
  "gpx_file": "...",
  "image_files": [...],
  "output_dir": "output",
  "notes": "",
  "mode": "blog",                              // NEU
  "article_length": "normal",
  "style_persona": "mountain_veteran",
  "pdf_export": false,
  "wildcard_max": 12,
  "photobook_size": "normal"                   // NEU (optional)
}
```

### Backend-Änderungen

| Datei | Änderung |
|---|---|
| `routes.py` | `RunPipelineRequest` um `photobook_size` ergänzt, `mode` aus Request in `OutputConfig` übernehmen |
| `state.py` | `PhotobookConfig` um `size` und `page_range` Felder ergänzt, Mapping `size → config`-Hilfsfunktion |
| `graph.py` | Keine Änderung (Routing über `output_config.mode` existiert bereits) |

### Neue Route

| Methode | Pfad | Zweck |
|---|---|---|
| `GET` | `/api/photobook/{run_id}/pdf` | Fotobuch-PDF einer Pipeline-Run-ID herunterladen |

### `PhotobookConfig` Erweiterung

```python
class PhotobookConfig(BaseModel):
    photo_count: int = Field(default=20, ge=5, le=30)
    page_range: str = "14-18"            # NEU
    size: Literal["short", "normal", "detailed"] = "normal"  # NEU
```

### `size → config` Mapping

```python
PHOTOBOOK_SIZE_MAP = {
    "short":    {"photo_count": 14, "page_range": "8-12"},
    "normal":   {"photo_count": 20, "page_range": "14-18"},
    "detailed": {"photo_count": 26, "page_range": "20-24"},
}
```

Dieses Mapping wird im Backend ausgewertet, bevor `PhotobookConfig` in `OutputConfig` gesetzt wird.

### PDF-Download-Flow

1. Fotobuch-Pipeline läuft → `photobook_pdf_path` wird gesetzt
2. `generate_photobook_pdf_node` speichert PDF unter vorhersehbarem Pfad: `data/uploads/{session_id}/photobook.pdf`
3. SSE `__done__` Event enthält `pdf_available: true`
4. Frontend triggert `GET /api/photobook/{run_id}/pdf`
5. Server liefert PDF als `FileResponse` mit `Content-Disposition: attachment`

---

## 6. Graph-Pipeline (unverändert)

Der bestehende Graph-Zweig bleibt:

```
generate_enriched_map
       ↓
  MODE = ?
  ↙         ↘
blog        photobook
(pfad       (pfad
bestehend)  unverändert)
```

Keine Änderungen an `graph.py` nötig — `output_config.mode` setzt bereits den korrekten Pfad.

---

## 7. Fehlerbehandlung

| Fehlerfall | Behandlung |
|---|---|
| Keine GPX-Datei | Beide Run-Buttons zeigen Validierungsfehler |
| Keine Bilder für Fotobuch | Backend macht Fallback-Layout; Frontend zeigt Log-Warnung |
| PDF-Generierung schlägt fehl | Event mit `pdf_available: false`, kein Download |
| Ollama nicht erreichbar | SSE `error`-Event, OutputWindow zeigt Fehler |

---

## 8. Scope-Abgrenzung

### In Scope
- Mode-Tabs (Blog / Fotobuch)
- Zweispaltige Sidebar (50:50, ~680px)
- Fotobuch-Größenstufen (Kurz / Mittel / Lang)
- Geteiltes Modell-Feld
- Pro-Spalte Run-Button
- Auto-Download des Fotobuch-PDFs
- API-Erweiterung um `mode` und `photobook_size`

### Außerhalb Scope (eigene Sessions)
- Fotobuch-Datenbank-Persistenz
- Fotobuch-Liste / Detail-Ansicht
- `mode="both"` (Blog + Fotobuch in einem Durchlauf)
- Weitere Fotobuch-Optionen (Seitenformat, Orientierung, etc.)
- Image-Selection-Vorschau vor Pipeline-Start

---

## 9. Zusammenfassung der Datei-Änderungen

| Pfad | Art | Beschreibung |
|---|---|---|
| `frontend/src/App.svelte` | Ändern | Layout auf zweispaltig umbauen |
| `frontend/src/lib/ModeTabs.svelte` | Neu | Blog/Fotobuch Tab-Umschaltung |
| `frontend/src/lib/PhotobookSizeSelector.svelte` | Neu | Kurz/Mittel/Lang Radio-Buttons |
| `frontend/src/lib/RunButton.svelte` | Ändern | Mode-abhängige Payload |
| `frontend/src/lib/stores/pipeline.ts` | Ändern | Neue Stores pipelineMode, photobookSize |
| `app/api/routes.py` | Ändern | RunPipelineRequest erweitern, PDF-Route |
| `app/state.py` | Ändern | PhotobookConfig um size/page_range |

Gesamt: 4 neue/geänderte Frontend-Dateien + Bestandsänderungen, 2 Backend-Dateien.
