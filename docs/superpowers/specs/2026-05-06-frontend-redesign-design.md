# Frontend-Redesign

**Datum:** 2026-05-06
**Status:** approved

## Ziel

Das Frontend-Layout wird restrukturiert: Die statische rechte Seite bekommt Tabs (Pipeline/Datenbank), die linke Sidebar wird verschlankt auf einen vertikalen Formular-Ablauf mit Settings-Tabs.

## Neues Layout

```
┌─────────────────────┬──────────────────────────────────────┐
│ LEFT SIDEBAR (340px)│ RIGHT SIDE (flex: 1)                 │
│                     │                                      │
│ TRAVEL AGENT        │ [Pipeline]  [Datenbank]              │
│                     │ ┌──────────────────────────────────┐ │
│ Modell: ▾           │ │ OutputWindow / ArticleList       │ │
│                     │ │                                  │ │
│ ┌─Dateien──┐        │ │                                  │ │
│ │  Drop    │        │ │                                  │ │
│ │  Zone    │        │ │                                  │ │
│ └──────────┘        │ └──────────────────────────────────┘ │
│                     │                                      │
│ Tour-Notizen        │                                      │
│ ┌──────────┐        │                                      │
│ │ textarea │        │                                      │
│ └──────────┘        │                                      │
│                     │                                      │
│ Ausgabe-Verzeichnis │                                      │
│ [___________]       │                                      │
│                     │                                      │
│ Einstellungen       │                                      │
│ [Blog] [Fotobuch]   │                                      │
│ ┌─────────────────┐ │                                      │
│ │ Settings        │ │                                      │
│ └─────────────────┘ │                                      │
│                     │                                      │
│ [▶ Pipeline starten]│                                      │
└─────────────────────┴──────────────────────────────────────┘
```

## Linke Sidebar (von oben nach unten)

1. **Titel** "Travel Agent" — unverändert
2. **ModelSelector** — Dropdown (nur Ollama-Modelle), kein "eigenes Modell"-Checkbox-Feld mehr. Custom-Model-Eingabe entfällt ersatzlos.
3. **FileDropZone** — unverändert (Drag & Drop + Dateiauswahl)
4. **NotesInput** — "Tour-Notizen" Textarea (unverändert)
5. **OutputDirInput** — "Ausgabe-Verzeichnis" Textfeld (unverändert)
6. **SettingsTabs** (NEU) — Container mit zwei Tabs:
   - **Blog**: WildcardCount, LengthSelector, StyleSelector, PdfExportCheckbox
   - **Fotobuch**: PhotobookSizeSelector
   - Nur der aktive Tab wird angezeigt. Keine 2-Spalten-Anordnung mehr.
   - Tab-Auswahl steuert den `pipelineMode` Store.
7. **RunButton** — ein einzelner Button "Pipeline starten". Liest den Mode aus dem `pipelineMode` Store (kein `mode` Prop mehr). Führt den Workflow des im Settings-Tab aktiven Modes aus.

## Rechte Seite

- **Tabs**: `[Pipeline]` `[Datenbank]`
- **Pipeline-Tab**: Zeigt OutputWindow (Pipeline-Logs)
- **Datenbank-Tab**: Zeigt ArticleList (Übersicht) → ArticleDetail (Detail-Ansicht). Aktuell nur Blog-Artikel; Fotobuch-DB-Integration folgt später, das Frontend wird dann erweitert.
- Bei Klick auf "Pipeline starten" → automatischer Wechsel der rechten Seite zum Pipeline-Tab.

## Routing

Hash-basiertes Routing bleibt bestehen. Routen-Definition:

| Hash | Route | Bedeutung |
|---|---|---|
| `#/` | `{ page: "pipeline" }` | Pipeline-Tab (OutputWindow) |
| `#/articles` | `{ page: "datenbank" }` | Datenbank-Tab (ArticleList) |
| `#/articles/:id` | `{ page: "article", id }` | Datenbank-Tab (ArticleDetail) |

Die rechten Tabs setzen die Route per `navigateTo()`. Die linke Sidebar hat keine Navigation mehr.

## Komponenten-Änderungen

| Komponente | Änderung |
|---|---|
| `App.svelte` | Komplettes Layout-Rewrite: keine linke Navigation, keine 2-Spalten, SettingsTabs integrieren, rechte Seite bekommt Tabs |
| `ModelSelector.svelte` | Entfernt: "eigenes Modell" Checkbox + custom-input Textfeld. Reines Dropdown. |
| `ModeTabs.svelte` | **Gelöscht** — ersetzt durch SettingsTabs |
| `RunButton.svelte` | Entfernt `mode` Prop; liest `pipelineMode` direkt aus Store |
| `router.ts` | Keine strukturelle Änderung nötig, ggf. Typ umbenennen |

## Neue Komponente

- **`SettingsTabs.svelte`** — Container mit Blog/Fotobuch Tab-Umschaltung, rendert die Settings des aktiven Tabs. Nutzt `pipelineMode` Store.

## Nicht geändert

- `FileDropZone.svelte`, `NotesInput.svelte`, `OutputDirInput.svelte` — unverändert
- `WildcardCount.svelte`, `LengthSelector.svelte`, `StyleSelector.svelte`, `PdfExportCheckbox.svelte`, `PhotobookSizeSelector.svelte` — unverändert
- `OutputWindow.svelte`, `ArticleList.svelte`, `ArticleDetail.svelte` — unverändert
- `pipeline.ts` Store — unverändert
- `app.css` — unverändert

## Verhalten

- Nur der aktuell aktive Settings-Tab wird angezeigt (keine zwei ausgegrauten Spalten)
- Pipeline starten startet den Workflow für den im Settings-Tab gewählten Mode
- Bei Pipeline-Start wechselt die rechte Seite automatisch zum Pipeline-Tab
- Datenbank-Tab zeigt aktuell nur Blog-Artikel; Fotobuch-DB folgt in eigenem Feature
