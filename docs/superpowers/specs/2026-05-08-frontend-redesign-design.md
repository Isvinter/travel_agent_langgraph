# Frontend-Redesign 2026-05: Layout, Pipeline-Timeline & Tabellen-Polish

**Datum:** 2026-05-08
**Status:** approved
**Baut auf:** `2026-05-06-frontend-redesign-design.md`, `2026-05-07-tab-redesign-design.md`
**Betrifft:** `frontend/src/App.svelte`, `frontend/src/lib/OutputWindow.svelte`, `frontend/src/lib/stores/router.ts`, `frontend/src/lib/ArticleList.svelte`, `frontend/src/lib/PhotobookList.svelte`, `frontend/src/lib/RunButton.svelte`, `frontend/src/app.css`, `frontend/src/lib/FileDropZone.svelte`

## Ziel

Das Frontend erhält eine grundlegende UX-Aufwertung in zwei Phasen:

- **Phase 1:** Layout & Navigation — kompakter Header, kontextabhängige Sidebar, flache Tabs
- **Phase 2a:** Pipeline-Timeline — vertikaler Stepper statt Terminal-Log
- **Phase 2b:** Tabellen-Polish — Icons, Zahlenausrichtung, Range-Slider, Kontraste

## Ausgangszustand

- CSS-Grid-Layout: Titlebar (2-zeilig, ~80px) + Sidebar (280px) + Main-Bereich
- Sidebar ist immer sichtbar, auch in der Datenbank-Ansicht
- Navigation: Top-Tabs "Pipeline | Datenbank", bei "Datenbank" erscheint Segmented Control "Blogartikel | Fotobücher"
- OutputWindow: Jedes SSE-Event wird als separate Log-Zeile gerendert (Start + Ende getrennt)
- Tabellen: Text-Buttons ("Ansehen", "Löschen"), linksbündige Zahlen, Textfelder für Dauer-Filter

## Phase 1: Layout & Navigation

### 1.1 Kompakter Header

**`App.svelte` — Template:**

Der bisherige `<header class="titlebar">` (2-zeilig, zentriert, ~80px hoch) wird ersetzt durch eine schmale Top-Navigationsleiste:

```svelte
<header class="topnav">
  <span class="topnav-brand">Tavilo</span>
  <nav class="topnav-tabs">
    <button class="t-tab" class:active={rt.page === "pipeline"} onclick={() => navigateTo({page:"pipeline"})}>Pipeline</button>
    <button class="t-tab" class:active={rt.page === "articles" || rt.page === "article" || rt.page === "draft"} onclick={() => navigateTo({page:"articles"})}>Blogartikel</button>
    <button class="t-tab" class:active={rt.page === "photobooks" || rt.page === "photobook"} onclick={() => navigateTo({page:"photobooks"})}>Fotobücher</button>
  </nav>
  <div class="topnav-spacer"></div>
  <!-- Theme-Toggle unverändert -->
</header>
```

**`App.svelte` — CSS:**

```css
.topnav {
  grid-column: 1 / -1;
  display: flex;
  align-items: center;
  gap: 0;
  height: 44px;
  padding: 0 16px;
  background: var(--header-bg);
  border-bottom: 1px solid var(--border);
}
.topnav-brand {
  font-weight: 700;
  color: var(--accent);
  font-size: 1rem;
  margin-right: 24px;
}
.topnav-tabs {
  display: flex;
  height: 100%;
}
.t-tab {
  padding: 0 16px;
  height: 100%;
  display: flex;
  align-items: center;
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  color: var(--text-secondary);
  font-size: 0.8rem;
  font-weight: 500;
  cursor: pointer;
  transition: color 0.15s, border-color 0.15s;
}
.t-tab.active {
  color: var(--text-primary);
  font-weight: 600;
  border-bottom-color: var(--accent);
}
.t-tab:hover:not(.active) {
  color: var(--text-primary);
}
.topnav-spacer {
  flex: 1;
}
```

**Routing-Mapping für active-Tab:**
- Pipeline-Tab aktiv wenn `rt.page === "pipeline"`
- Blogartikel-Tab aktiv wenn `rt.page` in `{"articles", "article", "draft"}`
- Fotobücher-Tab aktiv wenn `rt.page` in `{"photobooks", "photobook"}`

### 1.2 Kontextabhängige Sidebar

Die Sidebar ist **nur sichtbar**, wenn der Pipeline-Tab aktiv ist. Bei Blogartikel/Fotobücher entfällt sie komplett — die Tabelle nutzt die volle Breite.

**`App.svelte` — Template-Änderung:**

```svelte
<div class="layout">
  <header class="topnav">...</header>

  {#if rt.page === "pipeline"}
    <aside class="sidebar panel">
      <!-- bestehende Sidebar-Inhalte -->
    </aside>
  {/if}

  <main class="main" class:full-width={rt.page !== "pipeline"}>
    <!-- Content ohne die bisherige top-tab-bar (ist jetzt im Header) -->
    <div class="right-content">
      ...
    </div>
  </main>
</div>
```

**CSS-Änderungen:**
- `.layout` behält `grid-template-columns: 280px 1fr` als default
- Wenn Sidebar ausgeblendet: `main.full-width` setzt `grid-column: 2 / -1` (oder das Grid wird dynamisch umgeschaltet)
- Entfernen: `.top-tab-bar`, `.top-tab`, `.top-tab.active::after`, `.top-tab-bar-spacer`, `.top-tab-bar-line` (CSS-Klassen der alten Tab-Bar)
- Entfernen: `.segmented-control`, `.segment` (Segmented Control ist nicht mehr nötig)
- Entfernen: `.titlebar`, `.titlebar-title`, `.titlebar-subtitle`
- Entfernen: `switchRightTab()`, `switchDbSubTab()` Funktionen, `rightTab` und `dbSubTab` Variablen

**Routing-Vereinfachung:**
```ts
// Alte Logik entfernen:
let rightTab = $derived(rt.page === "pipeline" ? "pipeline" : "datenbank");
let dbSubTab: "articles" | "photobooks" = $state("articles");

// Neue Logik ist einfacher: kein "Datenbank"-Zwischen-Tab mehr.
// Route direkt: /pipeline, /articles, /articles/:id, /draft/:id, /photobooks, /photobooks/:id
```

### 1.3 Sidebar: Visuelle Gruppierung

Die Sidebar-Einstellungen werden in logische Gruppen mit dezenter visueller Trennung gegliedert:

```svelte
<aside class="sidebar panel">
  <div class="sidebar-header">⚙ Einstellungen</div>

  <div class="sidebar-scroll">
    <!-- Gruppe: Daten-Input -->
    <div class="sb-group">
      <div class="sb-group-title">Daten-Input</div>
      <FileDropZone />
      <NotesInput />
    </div>

    <!-- Gruppe: KI-Modell -->
    <div class="sb-group">
      <div class="sb-group-title">KI-Modell</div>
      <ModelSelector />
    </div>

    <!-- Gruppe: Modus -->
    <div class="sb-group">
      <div class="sb-group-title">Modus</div>
      <SettingsTabs />
    </div>

    <!-- Gruppe: Inhalts-Parameter (nur bei Blog-Modus) -->
    <!-- Gruppe: Ausgabe -->
    <div class="sb-group">
      <div class="sb-group-title">Ausgabe</div>
      <OutputDirInput />
    </div>
  </div>

  <div class="run-section">
    <RunButton />
  </div>
</aside>
```

**CSS:**

```css
.sb-group {
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 10px;
  margin-bottom: 10px;
  background: rgba(91, 140, 255, 0.02);
}
.sb-group-title {
  font-size: 0.65rem;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 8px;
}
```

### 1.4 Dropzone-Verbesserung

**`FileDropZone.svelte`:** Füge ein Icon (📂) und deutlicheren Hover-State hinzu:

```css
.dropzone {
  border: 2px dashed var(--border);
  border-radius: var(--radius-sm);
  padding: 18px 10px;
  text-align: center;
  color: var(--text-muted);
  font-size: 0.75rem;
  transition: border-color 0.2s, background 0.2s;
}
.dropzone:hover,
.dropzone.dragover {
  border-color: var(--accent);
  background: rgba(91, 140, 255, 0.06);
}
```

### 1.5 Sticky Run-Button

Der Run-Button bleibt am unteren Rand der Sidebar fixiert, auch wenn die Sidebar-Inhalte scrollen:

```css
.run-section {
  position: sticky;
  bottom: 0;
  flex-shrink: 0;
  padding: 10px 0 16px 0;
  background: var(--panel); /* deckt scrollenden Inhalt ab */
}
```

## Phase 2a: Pipeline-Timeline

### 2.1 Datenmodell

Neues Interface für aggregierte Schritte (ersetzt nicht `LogLine`, sondern wird daraus abgeleitet):

```ts
interface StepState {
  stage: string;          // Technischer Name (process_gpx)
  label: string;          // Deutsche Beschreibung (GPX-Datei analysiert)
  status: "pending" | "running" | "done" | "error";
  message?: string;       // Optionaler Infotext
  timestamp?: string;     // Letzter Zeitstempel
}

const STEP_LABELS: Record<string, string> = {
  process_gpx: "GPX-Datei analysiert",
  load_images: "Bilder geladen",
  extract_metadata: "Metadaten extrahiert",
  clustering_images: "Bilder geclustert",
  generate_map_image: "Karte generiert",
  load_tour_notes: "Notizen geladen & Bilder ausgewählt",
  generate_blog_post: "Blogpost generiert",
};
```

### 2.2 Aggregationslogik

Im `pipeline.ts` store wird `addLine()` so erweitert, dass Log-Zeilen für denselben `stage` aggregiert werden. Statt neuer Zeile wird die existierende aktualisiert.

```ts
// Neue writable store für die aggregierten Steps:
export const pipelineSteps = writable<StepState[]>([]);

export function addLine(stage: string, status: string, message: string) {
  const timestamp = new Date().toLocaleTimeString("de-DE");

  // Bestehende logLines weiter pflegen (für Debugging / Fallback)
  logLines.update((lines) => [...lines, { timestamp, stage, status, message }]);

  // Steps aggregieren
  pipelineSteps.update((steps) => {
    const idx = steps.findIndex((s) => s.stage === stage);
    const label = STEP_LABELS[stage] || stage;
    const stepState = status === "done" || status === "success" ? "done"
      : status === "error" ? "error"
      : status === "running" ? "running"
      : "pending";

    if (idx >= 0) {
      const updated = [...steps];
      updated[idx] = { ...updated[idx], status: stepState, message, timestamp };
      return updated;
    }
    return [...steps, { stage, label, status: stepState, message, timestamp }];
  });
}

// Bei Pipeline-Start: alle Steps initialisieren
export function initSteps(stages: string[]) {
  pipelineSteps.set(stages.map((s) => ({
    stage: s,
    label: STEP_LABELS[s] || s,
    status: "pending" as const,
  })));
}
```

### 2.3 Timeline-Komponente (neue Datei)

**`frontend/src/lib/PipelineTimeline.svelte`** — ersetzt `OutputWindow.svelte` in der Pipeline-Ansicht:

```svelte
<svelte:options runes />

<script lang="ts">
  import type { StepState } from "./stores/pipeline";
  let { steps }: { steps: StepState[] } = $props();
</script>

<div class="timeline">
  {#if steps.length === 0}
    <div class="timeline-empty">
      <div class="timeline-empty-icon">🚀</div>
      <p>Pipeline bereit. Konfiguriere die Einstellungen und starte die Generierung.</p>
    </div>
  {:else}
    {#each steps as step, i}
      <div class="t-step" class:active={step.status === "running"}>
        <div class="t-node">
          {#if step.status === "done"}
            <div class="t-dot done">✓</div>
          {:else if step.status === "running"}
            <div class="t-dot running"><div class="t-spinner"></div></div>
          {:else if step.status === "error"}
            <div class="t-dot error">✕</div>
          {:else}
            <div class="t-dot pending"></div>
          {/if}
          {#if i < steps.length - 1}
            <div class="t-line" class:done={step.status === "done"} class:pending={step.status === "pending"}></div>
          {/if}
        </div>
        <div class="t-body" class:pending={step.status === "pending"} class:error={step.status === "error"}>
          <div class="t-label">{step.label}</div>
          <div class="t-tech">{step.stage}</div>
          {#if step.message}
            <div class="t-msg">{step.message}</div>
          {/if}
        </div>
      </div>
    {/each}
  {/if}
</div>
```

**CSS (in PipelineTimeline.svelte):**

```css
.timeline { max-width: 640px; margin: 0 auto; padding: 20px 0; }
.timeline-empty { text-align: center; padding: 60px 20px; color: var(--text-muted); }
.timeline-empty-icon { font-size: 3rem; margin-bottom: 12px; }

.t-step { display: flex; align-items: flex-start; gap: 12px; }
.t-step.active .t-body {
  background: rgba(91, 140, 255, 0.06);
  border-left: 2px solid var(--accent);
  border-radius: var(--radius);
  padding: 8px 10px;
  margin: -6px -10px;
}
.t-step.active .t-label { color: var(--text-primary); }
.t-body.pending { opacity: 0.45; }
.t-body.error .t-label { color: var(--error); }

.t-node { display: flex; flex-direction: column; align-items: center; min-width: 24px; }
.t-dot { width: 24px; height: 24px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 11px; }
.t-dot.done { background: var(--success); color: white; }
.t-dot.running { background: var(--accent); }
.t-dot.error { background: var(--error); color: white; }
.t-dot.pending { background: var(--panel-2); border: 2px solid var(--border); }

.t-spinner { width: 10px; height: 10px; border: 2px solid white; border-top-color: transparent; border-radius: 50%; animation: spin 1s linear infinite; }

.t-line { width: 2px; flex: 1; min-height: 24px; background: var(--border); }
.t-line.done { background: var(--success); opacity: 0.5; }
.t-line.pending { opacity: 0.4; }

.t-body { flex: 1; padding-bottom: 14px; }
.t-label { font-size: 0.82rem; font-weight: 600; color: var(--text-secondary); margin-bottom: 2px; }
.t-tech { font-size: 0.65rem; color: var(--text-muted); font-family: monospace; }
.t-msg { font-size: 0.7rem; color: var(--text-muted); margin-top: 4px; }
```

HINWEIS: `@keyframes spin` ist bereits in `app.css` definiert, kann wiederverwendet werden.

### 2.4 Erfolgsmeldung nach Pipeline-Abschluss

Nach Abschluss der Pipeline (alle Steps "done") erscheint oberhalb der Timeline ein Success-Banner:

```svelte
{#if allDone}
  <div class="success-banner">
    <div class="success-icon">🎉</div>
    <div class="success-text">
      <strong>Dein Artikel wurde erfolgreich generiert!</strong>
      <span class="success-meta">{title} &middot; {duration} Tage &middot; {distance} km</span>
    </div>
    <div class="success-actions">
      <button class="btn-accent" onclick={...}>Artikel ansehen</button>
      <button class="btn-secondary" onclick={...}>Zur Übersicht</button>
    </div>
  </div>
{/if}
```

### 2.5 Run-Button im Running-Zustand

**`RunButton.svelte`:**
- Idle: `background: var(--accent)`, Text "🚀 Pipeline starten"
- Running: `background: var(--panel-2)`, Text mit Spinner "Läuft...", `cursor: not-allowed`, kein Klick

```svelte
{#if $runState === "running"}
  <div class="run-btn running" disabled>
    <div class="btn-spinner"></div>
    Läuft...
  </div>
{:else}
  <button class="run-btn">🚀 Pipeline starten</button>
{/if}
```

## Phase 2b: Tabellen-Polish

### 2.6 Icon-Buttons

**`ArticleList.svelte` und `PhotobookList.svelte`:**
Text-Buttons ersetzen durch Icons mit Tooltips:

```svelte
<td class="actions-cell">
  <button class="icon-btn" title="Ansehen" onclick={...}>
    {#if $theme === "dark"} 👁 {:else} <svg ...> {/if}
  </button>
  <button class="icon-btn icon-delete" title="Löschen" onclick={...}>
    🗑
  </button>
</td>
```

Besser: inline SVGs statt Emojis für konsistentes Rendering plattformübergreifend.

```css
.actions-cell { text-align: center; white-space: nowrap; }
.icon-btn {
  background: none;
  border: none;
  cursor: pointer;
  padding: 4px;
  opacity: 0.6;
  transition: opacity 0.15s, color 0.15s;
  font-size: 1.1rem;
}
.icon-btn:hover { opacity: 1; }
.icon-delete:hover { color: var(--error); }
```

### 2.7 Zahlen rechtsbündig

CSS für Tabellenzellen mit numerischen Werten:

```css
.num { text-align: right; font-variant-numeric: tabular-nums; }
```

Template: `<td class="num">{duration}</td>`, `<td class="num">{distance}</td>`, `<td class="num">{elevation}</td>`, `<td class="num">{imageCount}</td>`

### 2.8 Dauer-Filter: Range-Slider

**`ArticleList.svelte` — Filter-Bereich:**
Textfelder für `durationMin`/`durationMax` ersetzen durch Range-Slider:

```svelte
<div class="filter-group">
  <label class="filter-label">Dauer</label>
  <input type="range" min={1} max={21} bind:value={durationMin} />
  <span class="range-val">{durationMin}</span>
  <span class="filter-sep">–</span>
  <input type="range" min={1} max={21} bind:value={durationMax} />
  <span class="range-val">{durationMax}</span>
  <span class="filter-unit">Tage</span>
</div>
```

### 2.9 Löschen-Button deaktiviert

Der "Auswahl löschen"-Button ist nur aktiv, wenn mindestens eine Checkbox markiert ist:

```svelte
<button
  class="btn-delete"
  disabled={selectedIds.length === 0}
  onclick={confirmBatchDelete}
>
  🗑 Auswahl löschen{selectedIds.length > 0 ? ` (${selectedIds.length})` : ""}
</button>
```

```css
.btn-delete:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}
.btn-delete:not(:disabled) {
  background: var(--error);
  color: white;
}
```

### 2.10 Design-Token-Anpassungen

**`app.css`:**
- `--error`: `#E63946` (klares Dunkelrot, vorher `#F87171` Lachs-Rosa)
- `--text-muted`: `#8B95A5` (helleres Grau für bessere Lesbarkeit, vorher `#6B7280`)
- Löschen-Badge-Hintergrund: `rgba(230, 57, 70, 0.12)`
- Tabellen-Header-Hintergrund: `var(--panel-2)` mit `font-weight: 600`

### 2.11 Bessere Zeilenabstände in Tabellen

```css
td, th {
  padding: 10px 12px; /* vorher ~6px */
}
thead tr {
  border-bottom: 2px solid var(--border);
}
```

## Route-Struktur (neu)

| Hash | Route | Sidebar | Inhalt |
|------|-------|---------|--------|
| `#/` oder `#/pipeline` | `{ page: "pipeline" }` | Ja | PipelineTimeline |
| `#/articles` | `{ page: "articles" }` | Nein | ArticleList (volle Breite) |
| `#/articles/:id` | `{ page: "article", id }` | Nein | ArticleDetail |
| `#/draft/:id` | `{ page: "draft", id }` | Nein | DraftReview |
| `#/photobooks` | `{ page: "photobooks" }` | Nein | PhotobookList |
| `#/photobooks/:id` | `{ page: "photobook", id }` | Nein | PhotobookDetail |

## Datei-Änderungen im Überblick

### Neue Dateien
- `frontend/src/lib/PipelineTimeline.svelte` — Vertikaler Stepper

### Geänderte Dateien
- `frontend/src/App.svelte` — Neues Layout (Header, Sidebar-Logik, kein "Datenbank"-Tab)
- `frontend/src/app.css` — Design-Token-Updates (`--error`, `--text-muted`), Tabellen-Styling
- `frontend/src/lib/stores/pipeline.ts` — `addLine()` erweitert um Aggregation, neue `pipelineSteps` store, `STEP_LABELS`
- `frontend/src/lib/stores/router.ts` — Routing-Logik vereinfacht (kein `rightTab`, kein `dbSubTab`)
- `frontend/src/lib/OutputWindow.svelte` — Entfällt als Pipeline-Hauptansicht (bleibt ggf. als Fallback erhalten)
- `frontend/src/lib/RunButton.svelte` — Running-State mit Spinner
- `frontend/src/lib/ArticleList.svelte` — Icons, rechtsbündige Zahlen, Range-Slider, deaktivierter Delete-Button
- `frontend/src/lib/PhotobookList.svelte` — Gleiche Änderungen wie ArticleList
- `frontend/src/lib/FileDropZone.svelte` — Icon + Hover-State

### Nicht angefasst
- Backend (keine Änderungen)
- `ArticleDetail.svelte`, `PhotobookDetail.svelte`, `DraftReview.svelte` — Keine strukturellen Änderungen
- `SettingsTabs.svelte` und alle Settings-Komponenten (`ModelSelector`, `LengthSelector`, etc.) — Layout-Änderung nur in App.svelte

## Risiken

1. **Sidebar-Grid-Umschaltung**: Layout muss zwischen `grid-template-columns: 260px 1fr` (Pipeline) und `1fr` (keine Sidebar) wechseln. CSS Grid benötigt dynamische Klassen oder inline styles.
2. **SSE-Aggregations-Timing**: Events kommen asynchron. Falls ein "done" vor dem "start" ankommt (Edge Case), muss der Step korrekt initialisiert werden.
3. **Browser-Kompatibilität**: `font-variant-numeric: tabular-nums` wird von modernen Browsern unterstützt. Range-Slider-Styling ist browserabhängig — `accent-color` wird als Minimum verwendet.

## Nicht-Ziele (YAGNI)

- Keine CSS-Framework-Migration (kein Tailwind)
- Keine SvelteKit-Migration
- Keine Animationen über das definierte Minimum hinaus
- Keine Internationalisierung
- Keine Backend-Änderungen
