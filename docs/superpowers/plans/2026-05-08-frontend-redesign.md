# Frontend Redesign 2026-05 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Frontend UX redesign in two phases — compact layout with context-dependent sidebar, vertical pipeline timeline stepper, and table polish (icons, right-aligned numbers, range sliders).

**Architecture:** Phase 1 restructures App.svelte layout (compact header, flat tabs, conditional sidebar). Phase 2a adds PipelineTimeline.svelte and aggregation in pipeline.ts. Phase 2b polishes ArticleList/PhotobookList with small focused edits.

**Tech Stack:** Svelte 5 (runes mode), TypeScript, custom CSS with CSS custom properties, Svelte stores, no external CSS framework.

**Worktree:** `.worktrees/frontend-redesign` (branch `feature/frontend-redesign-2026-05`)

**Spec:** `docs/superpowers/specs/2026-05-08-frontend-redesign-design.md`

---

### Task 1: Update Design Tokens (app.css)

**Files:**
- Modify: `frontend/src/app.css`

- [ ] **Step 1: Update error color and text-muted in dark theme**

In `frontend/src/app.css`, change the dark theme `--error` and `--text-muted` values:

Old (line 25):
```css
  --error: #F87171;
```
New:
```css
  --error: #E63946;
```

Old (line 19):
```css
  --text-muted: #6B7280;
```
New:
```css
  --text-muted: #8B95A5;
```

- [ ] **Step 2: Update error badge background in dark theme**

Old (line 33):
```css
  --badge-error-bg: rgba(248, 113, 113, 0.15);
```
New:
```css
  --badge-error-bg: rgba(230, 57, 70, 0.12);
```

- [ ] **Step 3: Update error color in light theme**

Old (line 60):
```css
  --error: #EF4444;
```
New:
```css
  --error: #DC2626;
```

- [ ] **Step 4: Add table header styling token**

Add a new CSS custom property in both themes. After `--radius-sm` in each block:

Dark theme (after line 29):
```css
  --th-bg: var(--panel-2);
  --th-border: var(--border);
```

Light theme (after line 65):
```css
  --th-bg: #F1F3F6;
  --th-border: #E6E8EC;
```

- [ ] **Step 5: Add global table header styling**

Add at the end of `app.css` (after line 151):

```css
/* ── Table Header ── */
thead th {
  background: var(--th-bg);
  font-weight: 600;
  color: var(--text-primary);
  border-bottom: 2px solid var(--th-border);
}

/* ── Numeric table cells ── */
td.num, th.num {
  text-align: right;
  font-variant-numeric: tabular-nums;
}
```

- [ ] **Step 6: Verify the file parses**

Run: `cd frontend && npx svelte-check --no-ts-check 2>&1 | tail -5`
Expected: No errors related to app.css.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/app.css
git commit -m "feat: update design tokens for redesign (error color, text-muted, table headers)"
```

---

### Task 2: Add Pipeline Step Aggregation (pipeline.ts)

**Files:**
- Modify: `frontend/src/lib/stores/pipeline.ts`

- [ ] **Step 1: Add StepState interface and STEP_LABELS constant**

After the `RunResult` interface (after line 20), add:

```ts
export interface StepState {
  stage: string;
  label: string;
  status: "pending" | "running" | "done" | "error";
  message?: string;
  timestamp?: string;
}

const STEP_LABELS: Record<string, string> = {
  process_gpx: "GPX-Datei analysiert",
  load_images: "Bilder geladen",
  extract_metadata: "Metadaten extrahiert",
  clustering_images: "Bilder geclustert",
  generate_map_image: "Karte generiert",
  load_tour_notes: "Notizen geladen & Bilder ausgewählt",
  select_images: "Notizen geladen & Bilder ausgewählt",
  generate_blog_post: "Blogpost generiert",
};
```

- [ ] **Step 2: Add pipelineSteps writable store**

After `export const logLines` (after line 30), add:

```ts
export const pipelineSteps = writable<StepState[]>([]);
```

- [ ] **Step 3: Modify addLine() to aggregate steps**

Replace the existing `addLine` function (lines 61-69):

```ts
export function addLine(stage: string, status: string, message: string) {
  const timestamp = new Date().toLocaleTimeString("de-DE");

  // Bestehende logLines weiter pflegen
  logLines.update((lines) => [...lines, { timestamp, stage, status, message }]);

  // Steps aggregieren: ein Eintrag pro Stage, Status wird aktualisiert
  pipelineSteps.update((steps) => {
    const idx = steps.findIndex((s) => s.stage === stage);
    const label = STEP_LABELS[stage] || stage;
    const stepStatus = status === "done" || status === "success" ? "done"
      : status === "error" ? "error"
      : status === "running" ? "running"
      : "pending";

    if (idx >= 0) {
      const updated = [...steps];
      updated[idx] = { ...updated[idx], status: stepStatus, message, timestamp };
      return updated;
    }
    return [...steps, { stage, label, status: stepStatus, message, timestamp }];
  });
}
```

- [ ] **Step 4: Update resetPipeline() to also clear pipelineSteps**

Replace the existing `resetPipeline` function (lines 136-143):

```ts
export function resetPipeline() {
  stopStream();
  logLines.set([]);
  pipelineSteps.set([]);
  runState.set("idle");
  currentRunId.set(null);
  result.set(null);
  currentDraftId.set(null);
}
```

- [ ] **Step 5: Run svelte-check to verify**

Run: `cd frontend && npx svelte-check --no-ts-check 2>&1 | tail -10`
Expected: No new errors from pipeline.ts.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/lib/stores/pipeline.ts
git commit -m "feat: add step aggregation and pipelineSteps store for timeline view"
```

---

### Task 3: Create PipelineTimeline Component

**Files:**
- Create: `frontend/src/lib/PipelineTimeline.svelte`

- [ ] **Step 1: Write the component file**

Create `frontend/src/lib/PipelineTimeline.svelte`:

```svelte
<svelte:options runes />

<script lang="ts">
  import { pipelineSteps, result, runState } from "./stores/pipeline";
  import { navigateTo } from "./stores/router";
  import type { StepState } from "./stores/pipeline";

  let steps = $derived($pipelineSteps);
  let state = $derived($runState);
  let res = $derived($result);
</script>

<div class="timeline-wrapper">
  {#if steps.length === 0}
    <div class="timeline-empty">
      <div class="timeline-empty-icon">🚀</div>
      <p>Pipeline bereit. Konfiguriere die Einstellungen und starte die Generierung.</p>
    </div>
  {:else}
    {#if state === "done" && res}
      <div class="success-banner">
        <div class="success-icon">🎉</div>
        <div class="success-body">
          <div class="success-title">
            {res.draft_id ? "Dein Entwurf wurde erstellt!" : "Dein Artikel wurde erfolgreich generiert!"}
          </div>
        </div>
        <div class="success-actions">
          {#if res.draft_id}
            <button class="btn-accent" onclick={() => navigateTo({ page: "draft", id: res.draft_id! })}>
              Entwurf ansehen
            </button>
          {:else if res.article_id}
            <button class="btn-accent" onclick={() => navigateTo({ page: "article", id: res.article_id! })}>
              Artikel ansehen
            </button>
          {/if}
          <button class="btn-secondary" onclick={() => navigateTo({ page: "articles" })}>
            Zur Übersicht
          </button>
        </div>
      </div>
    {/if}

    <div class="timeline">
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
    </div>
  {/if}
</div>

<style>
  .timeline-wrapper {
    flex: 1;
    overflow-y: auto;
    padding: 0 1rem;
  }
  .timeline-empty {
    text-align: center;
    padding: 60px 20px;
    color: var(--text-muted);
  }
  .timeline-empty-icon {
    font-size: 3rem;
    margin-bottom: 12px;
  }
  .timeline {
    max-width: 640px;
    margin: 0 auto;
    padding: 20px 0;
  }

  .success-banner {
    display: flex;
    align-items: center;
    gap: 12px;
    background: rgba(74, 222, 128, 0.08);
    border: 1px solid rgba(74, 222, 128, 0.3);
    border-radius: var(--radius);
    padding: 14px 16px;
    margin-bottom: 20px;
    max-width: 640px;
  }
  .success-icon { font-size: 28px; flex-shrink: 0; }
  .success-body { flex: 1; }
  .success-title { font-size: 0.9rem; font-weight: 700; color: var(--success); }
  .success-actions { display: flex; gap: 6px; flex-shrink: 0; }
  .btn-accent {
    padding: 6px 12px;
    background: var(--accent);
    color: white;
    border: none;
    border-radius: var(--radius);
    font-size: 0.75rem;
    font-weight: 500;
    cursor: pointer;
    white-space: nowrap;
  }
  .btn-accent:hover { background: var(--accent-hover); }
  .btn-secondary {
    padding: 6px 12px;
    background: var(--panel-2);
    color: var(--text-primary);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    font-size: 0.75rem;
    font-weight: 500;
    cursor: pointer;
    white-space: nowrap;
  }
  .btn-secondary:hover { background: var(--border); }

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
  .t-dot { width: 24px; height: 24px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 11px; flex-shrink: 0; }
  .t-dot.done { background: var(--success); color: white; }
  .t-dot.running { background: var(--accent); }
  .t-dot.error { background: var(--error); color: white; }
  .t-dot.pending { background: var(--panel-2); border: 2px solid var(--border); }

  .t-spinner { width: 10px; height: 10px; border: 2px solid white; border-top-color: transparent; border-radius: 50%; animation: spin 1s linear infinite; }

  .t-line { width: 2px; flex: 1; min-height: 24px; background: var(--border); }
  .t-line.done { background: var(--success); opacity: 0.5; }
  .t-line.pending { opacity: 0.4; }

  .t-body { flex: 1; padding-bottom: 14px; min-width: 0; }
  .t-label { font-size: 0.82rem; font-weight: 600; color: var(--text-secondary); margin-bottom: 2px; }
  .t-tech { font-size: 0.65rem; color: var(--text-muted); font-family: monospace; }
  .t-msg { font-size: 0.7rem; color: var(--text-muted); margin-top: 4px; }

  @keyframes spin { to { transform: rotate(360deg); } }
</style>
```

- [ ] **Step 2: Run svelte-check to verify**

Run: `cd frontend && npx svelte-check --no-ts-check 2>&1 | tail -10`
Expected: No new errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/PipelineTimeline.svelte
git commit -m "feat: add PipelineTimeline vertical stepper component"
```

---

### Task 4: Restructure App.svelte Layout

**Files:**
- Modify: `frontend/src/App.svelte`

- [ ] **Step 1: Replace the script block**

Replace the entire `<script>` block (lines 1-54) with:

```svelte
<svelte:options runes />

<script lang="ts">
  import { route, navigateTo } from "./lib/stores/router";
  import { runState, currentDraftId } from "./lib/stores/pipeline";
  import { theme, toggleTheme } from "./lib/stores/theme";
  import ModelSelector from "./lib/ModelSelector.svelte";
  import FileDropZone from "./lib/FileDropZone.svelte";
  import OutputDirInput from "./lib/OutputDirInput.svelte";
  import NotesInput from "./lib/NotesInput.svelte";
  import SettingsTabs from "./lib/SettingsTabs.svelte";
  import RunButton from "./lib/RunButton.svelte";
  import PipelineTimeline from "./lib/PipelineTimeline.svelte";
  import OutputWindow from "./lib/OutputWindow.svelte";
  import ArticleList from "./lib/ArticleList.svelte";
  import ArticleDetail from "./lib/ArticleDetail.svelte";
  import PhotobookList from "./lib/PhotobookList.svelte";
  import PhotobookDetail from "./lib/PhotobookDetail.svelte";
  import DraftReview from "./lib/DraftReview.svelte";

  let rt = $derived($route);
  let showSidebar = $derived(rt.page === "pipeline");

  $effect(() => {
    if ($runState === "running" && rt.page !== "pipeline") {
      navigateTo({ page: "pipeline" });
    }
    if ($currentDraftId !== null && rt.page !== "draft") {
      navigateTo({ page: "draft", id: $currentDraftId });
    }
  });
</script>
```

- [ ] **Step 2: Replace the entire template**

Replace lines 56-158 (everything from `<div class="layout">` through `</div>` before the `<style>` block) with:

```svelte
<div class="layout" class:has-sidebar={showSidebar}>

  <header class="topnav">
    <span class="topnav-brand">Tavilo</span>
    <nav class="topnav-tabs">
      <button
        class="t-tab"
        class:active={rt.page === "pipeline"}
        onclick={() => navigateTo({ page: "pipeline" })}
      >Pipeline</button>
      <button
        class="t-tab"
        class:active={rt.page === "articles" || rt.page === "article" || rt.page === "draft"}
        onclick={() => navigateTo({ page: "articles" })}
      >Blogartikel</button>
      <button
        class="t-tab"
        class:active={rt.page === "photobooks" || rt.page === "photobook"}
        onclick={() => navigateTo({ page: "photobooks" })}
      >Fotobücher</button>
    </nav>
    <div class="topnav-spacer"></div>
    <button
      class="theme-toggle"
      onclick={toggleTheme}
      title={$theme === "dark" ? "Helles Design" : "Dunkles Design"}
    >
      {#if $theme === "dark"}
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="5"/>
          <line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/>
          <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
          <line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/>
          <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
        </svg>
      {:else}
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
        </svg>
      {/if}
    </button>
  </header>

  {#if showSidebar}
    <aside class="sidebar panel">
      <div class="sidebar-header">⚙ Einstellungen</div>

      <div class="sidebar-scroll">
        <div class="sb-group">
          <div class="sb-group-title">Daten-Input</div>
          <FileDropZone />
          <NotesInput />
        </div>

        <div class="sb-group">
          <div class="sb-group-title">KI-Modell</div>
          <ModelSelector />
        </div>

        <div class="sb-group">
          <div class="sb-group-title">Modus</div>
          <SettingsTabs />
        </div>

        <div class="sb-group">
          <div class="sb-group-title">Ausgabe</div>
          <OutputDirInput />
        </div>
      </div>

      <div class="run-section">
        <RunButton />
      </div>
    </aside>
  {/if}

  <main class="main">
    <div class="right-content">
      {#if rt.page === "pipeline"}
        <PipelineTimeline />
      {:else if rt.page === "draft"}
        <DraftReview id={rt.id} />
      {:else if rt.page === "article"}
        <ArticleDetail id={rt.id} />
      {:else if rt.page === "photobook"}
        <PhotobookDetail id={rt.id} />
      {:else if rt.page === "photobooks"}
        <PhotobookList />
      {:else}
        <ArticleList />
      {/if}
    </div>
  </main>
</div>
```

- [ ] **Step 3: Replace the entire `<style>` block**

Replace lines 160-336 (the entire `<style>` block) with:

```svelte
<style>
  .layout {
    display: grid;
    grid-template-columns: 1fr;
    grid-template-rows: 44px 1fr;
    height: 100vh;
    width: 100vw;
    background: var(--bg);
  }
  .layout.has-sidebar {
    grid-template-columns: 260px 1fr;
  }

  /* ── Top Navigation ── */
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
  .theme-toggle {
    padding: 0.5rem;
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    color: var(--text-secondary);
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    line-height: 1;
    flex-shrink: 0;
  }
  .theme-toggle:hover {
    background: var(--panel-2);
    color: var(--text-primary);
  }

  /* ── Sidebar ── */
  .sidebar {
    background: var(--panel);
    border-right: 1px solid var(--border);
    padding: 14px 14px 0 14px;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }
  .sidebar-header {
    font-size: 0.7rem;
    font-weight: 600;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 12px;
    flex-shrink: 0;
  }
  .sidebar-scroll {
    flex: 1;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 0;
  }
  .sb-group {
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 10px;
    margin-bottom: 10px;
    background: rgba(91, 140, 255, 0.02);
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }
  .sb-group-title {
    font-size: 0.6rem;
    font-weight: 600;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }
  .run-section {
    flex-shrink: 0;
    padding: 0.5rem 0 14px 0;
    background: var(--panel);
  }

  /* ── Main Content ── */
  .main {
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }
  .right-content {
    flex: 1;
    display: flex;
    flex-direction: column;
    min-height: 0;
  }
</style>
```

- [ ] **Step 4: Run svelte-check to verify**

Run: `cd frontend && npx svelte-check --no-ts-check 2>&1 | tail -10`
Expected: No errors.

- [ ] **Step 5: Start dev server and visually verify layout works**

Run in terminal 1: `cd frontend && npm run dev`
Open browser. Verify: compact header, 3 tabs work, sidebar appears only on Pipeline tab, Blogartikel/Fotobücher show full width.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/App.svelte
git commit -m "feat: restructure layout with compact header, flat tabs, conditional sidebar"
```

---

### Task 5: Improve FileDropZone (Icon + Hover)

**Files:**
- Modify: `frontend/src/lib/FileDropZone.svelte`

- [ ] **Step 1: Remove type badge text from file list items**

In the template, replace the file-type span. Old (lines 135-136):
```svelte
          <span class="file-type">{f.type.toUpperCase()}</span>
          <span class="file-name">{f.name}</span>
```

New:
```svelte
          <span class="file-icon">
            {#if f.type === "gpx"}📍
            {:else if f.type === "image"}🖼
            {:else if f.type === "txt"}📄
            {:else}📎
            {/if}
          </span>
          <span class="file-name">{f.name}</span>
```

- [ ] **Step 2: Add upload icon to the drop zone**

In the template, add an icon before the zone-text. Old (line 124):
```svelte
    <p class="zone-text">Dateien hier ablegen</p>
```
New:
```svelte
    <p class="zone-icon">📂</p>
    <p class="zone-text">Dateien hier ablegen</p>
```

- [ ] **Step 3: Update CSS**

Replace the `.zone` CSS (lines 155-166):
```css
  .zone {
    border: 2px dashed var(--border);
    border-radius: 6px;
    padding: 1.5rem 1rem;
    text-align: center;
    transition: border-color 0.2s, background 0.2s;
    cursor: pointer;
  }
  .zone:hover {
    border-color: var(--accent);
    background: rgba(91, 140, 255, 0.04);
  }
  .zone.active {
    border-color: var(--accent);
    background: rgba(91, 140, 255, 0.08);
  }
  .zone-icon {
    font-size: 1.5rem;
    margin-bottom: 0.2rem;
  }
```

Replace the `.file-type` CSS (lines 199-204) with `.file-icon`:
```css
  .file-icon {
    font-size: 0.8rem;
    min-width: 1.2rem;
    text-align: center;
  }
```

- [ ] **Step 4: Run svelte-check**

Run: `cd frontend && npx svelte-check --no-ts-check 2>&1 | tail -10`
Expected: No new errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/FileDropZone.svelte
git commit -m "feat: add icon and hover state to dropzone"
```

---

### Task 6: Polish ArticleList (Icons, Right-Aligned Numbers, Range Slider)

**Files:**
- Modify: `frontend/src/lib/ArticleList.svelte`

- [ ] **Step 1: Change duration min/max to number type with slider**

Replace the duration filter inputs in the template. Old (lines 194-201):
```svelte
    <label>
      Dauer (min h):
      <input type="number" bind:value={durationMin} placeholder="z.B. 2" step="0.5" />
    </label>
    <label>
      Dauer (max h):
      <input type="number" bind:value={durationMax} placeholder="z.B. 8" step="0.5" />
    </label>
```
New:
```svelte
    <div class="filter-duration">
      <span class="filter-duration-label">Dauer</span>
      <input type="range" min={0} max={21} bind:value={durationMin} />
      <span class="range-val">{durationMin || "0"}</span>
      <span class="filter-sep">–</span>
      <input type="range" min={0} max={21} bind:value={durationMax} />
      <span class="range-val">{durationMax || "21"}</span>
      <span class="filter-unit">Tage</span>
    </div>
```

- [ ] **Step 2: Add right-alignment classes to numeric columns**

Replace the table header row (lines 216-244) to add `num` class to numeric columns:

```svelte
            <th class="th-check">
              <input
                type="checkbox"
                checked={selectedIds.size === articles.length && articles.length > 0}
                onchange={toggleSelectAll}
              />
            </th>
            <th class="sortable" onclick={() => handleSort("title")}>
              Titel {sortColumn === "title" ? (sortDirection === "asc" ? "▲" : "▼") : ""}
            </th>
            <th class="sortable" onclick={() => handleSort("tour_date")}>
              Tour-Datum {sortColumn === "tour_date" ? (sortDirection === "asc" ? "▲" : "▼") : ""}
            </th>
            <th class="sortable num" onclick={() => handleSort("tour_duration_hours")}>
              Dauer {sortColumn === "tour_duration_hours" ? (sortDirection === "asc" ? "▲" : "▼") : ""}
            </th>
            <th class="sortable num" onclick={() => handleSort("total_distance_km")}>
              Distanz {sortColumn === "total_distance_km" ? (sortDirection === "asc" ? "▲" : "▼") : ""}
            </th>
            <th class="sortable num" onclick={() => handleSort("elevation_gain_m")}>
              Höhenmeter {sortColumn === "elevation_gain_m" ? (sortDirection === "asc" ? "▲" : "▼") : ""}
            </th>
            <th class="sortable num" onclick={() => handleSort("image_count")}>
              Bilder {sortColumn === "image_count" ? (sortDirection === "asc" ? "▲" : "▼") : ""}
            </th>
            <th class="actions-header"></th>
```

Replace the body rows (lines 246-275) to add `num` class:

```svelte
            <tr>
              <td class="td-check">
                <input
                  type="checkbox"
                  checked={selectedIds.has(a.id)}
                  onchange={() => toggleSelect(a.id)}
                />
              </td>
              <td>
                {a.title || "Ohne Titel"}
                {#if a.status === "draft"}
                  <span class="draft-badge">Entwurf</span>
                {/if}
              </td>
              <td>{formatDate(a.tour_date)}</td>
              <td class="num">{formatDuration(a.tour_duration_hours)}</td>
              <td class="num">{a.total_distance_km ? `${a.total_distance_km} km` : "\u2014"}</td>
              <td class="num">{a.elevation_gain_m ? `${a.elevation_gain_m} m` : "\u2014"}</td>
              <td class="num">{a.image_count ?? "\u2014"}</td>
              <td class="actions-cell">
                <button class="icon-btn" title="Ansehen" onclick={() => handleView(a.id)}>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                    <circle cx="12" cy="12" r="3"/>
                  </svg>
                </button>
                <button class="icon-btn icon-delete" title="Löschen" onclick={() => openSingleDelete(a.id)}>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <polyline points="3 6 5 6 21 6"/>
                    <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                  </svg>
                </button>
              </td>
            </tr>
```

- [ ] **Step 3: Update the delete button in header to use icon**

Replace the batch delete button (lines 176-183):
```svelte
    <button
      class="batch-delete-btn"
      disabled={selectedIds.size === 0}
      onclick={openBatchDelete}
    >
      🗑 Auswahl löschen ({selectedIds.size})
    </button>
```


- [ ] **Step 4: Add new CSS and update existing CSS**

Add to the `<style>` block:

```css
  .filter-duration {
    display: flex;
    align-items: center;
    gap: 4px;
    font-size: 0.75rem;
    color: var(--text-muted);
  }
  .filter-duration-label {
    margin-right: 4px;
  }
  .filter-duration input[type="range"] {
    width: 70px;
    accent-color: var(--accent);
    padding: 0;
    margin: 0;
  }
  .range-val {
    min-width: 18px;
    text-align: center;
    color: var(--text-primary);
    font-size: 0.75rem;
  }
  .filter-sep {
    color: var(--text-muted);
  }
  .filter-unit {
    color: var(--text-muted);
    font-size: 0.7rem;
  }
```

Replace the existing `th`, `td`, `.view-btn`, `.delete-btn` CSS with:

```css
  th {
    text-align: left;
    color: var(--text-muted);
    font-weight: 600;
    padding: 10px 12px;
    border-bottom: 2px solid var(--border);
    white-space: nowrap;
    position: sticky;
    top: 0;
    background: var(--th-bg);
    z-index: 1;
    font-size: 0.72rem;
  }
  td {
    padding: 10px 12px;
    border-bottom: 1px solid var(--border);
    white-space: nowrap;
  }
  .actions-header {
    width: 70px;
  }
  .actions-cell {
    text-align: center;
    white-space: nowrap;
  }
  .icon-btn {
    background: none;
    border: none;
    cursor: pointer;
    padding: 4px;
    opacity: 0.5;
    transition: opacity 0.15s, color 0.15s;
    color: var(--text-secondary);
    display: inline-flex;
    align-items: center;
  }
  .icon-btn:hover {
    opacity: 1;
    color: var(--accent);
  }
  .icon-delete:hover {
    color: var(--error);
  }
```

Replace the existing `.batch-delete-btn` CSS with:

```css
  .batch-delete-btn {
    padding: 0.4rem 0.75rem;
    font-size: 0.8rem;
    background: var(--error);
    color: white;
    white-space: nowrap;
    border: none;
    border-radius: var(--radius);
    cursor: pointer;
  }
  .batch-delete-btn:disabled {
    opacity: 0.35;
    cursor: not-allowed;
    background: var(--panel-2);
    color: var(--text-muted);
  }
  .batch-delete-btn:not(:disabled):hover {
    opacity: 0.9;
  }
```

- [ ] **Step 5: Remove unused CSS for old view-btn and delete-btn**

Remove these style blocks (no longer used with icons):
```css
  .view-btn { ... }
  .view-btn:hover { ... }
  .delete-btn { ... }
  .delete-btn:hover { ... }
```
(These are currently lines 405-422.)

- [ ] **Step 6: Run svelte-check**

Run: `cd frontend && npx svelte-check --no-ts-check 2>&1 | tail -10`
Expected: No errors.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/lib/ArticleList.svelte
git commit -m "feat: polish article list with icons, right-aligned numbers, range slider"
```

---

### Task 7: Polish PhotobookList (Icons, Right-Aligned Numbers, Range Slider)

**Files:**
- Modify: `frontend/src/lib/PhotobookList.svelte`

- [ ] **Step 1: Change duration min/max to range slider**

Replace the duration filter inputs in the template. Old (lines 198-205):
```svelte
    <label>
      Dauer (min h):
      <input type="number" bind:value={durationMin} placeholder="z.B. 2" step="0.5" />
    </label>
    <label>
      Dauer (max h):
      <input type="number" bind:value={durationMax} placeholder="z.B. 8" step="0.5" />
    </label>
```
New:
```svelte
    <div class="filter-duration">
      <span class="filter-duration-label">Dauer</span>
      <input type="range" min={0} max={21} bind:value={durationMin} />
      <span class="range-val">{durationMin || "0"}</span>
      <span class="filter-sep">–</span>
      <input type="range" min={0} max={21} bind:value={durationMax} />
      <span class="range-val">{durationMax || "21"}</span>
      <span class="filter-unit">Tage</span>
    </div>
```

- [ ] **Step 2: Add num class and icon buttons to table**

Replace the header row (lines 219-251) to add `num` class:

```svelte
            <th class="th-check">
              <input
                type="checkbox"
                checked={selectedIds.size === photobooks.length && photobooks.length > 0}
                onchange={toggleSelectAll}
              />
            </th>
            <th class="sortable" onclick={() => handleSort("title")}>
              Titel {sortColumn === "title" ? (sortDirection === "asc" ? "▲" : "▼") : ""}
            </th>
            <th class="sortable" onclick={() => handleSort("tour_date")}>
              Tour-Datum {sortColumn === "tour_date" ? (sortDirection === "asc" ? "▲" : "▼") : ""}
            </th>
            <th class="sortable num" onclick={() => handleSort("tour_duration_hours")}>
              Dauer {sortColumn === "tour_duration_hours" ? (sortDirection === "asc" ? "▲" : "▼") : ""}
            </th>
            <th class="sortable num" onclick={() => handleSort("total_distance_km")}>
              Distanz {sortColumn === "total_distance_km" ? (sortDirection === "asc" ? "▲" : "▼") : ""}
            </th>
            <th class="sortable num" onclick={() => handleSort("elevation_gain_m")}>
              Höhenmeter {sortColumn === "elevation_gain_m" ? (sortDirection === "asc" ? "▲" : "▼") : ""}
            </th>
            <th class="sortable num" onclick={() => handleSort("image_count")}>
              Bilder {sortColumn === "image_count" ? (sortDirection === "asc" ? "▲" : "▼") : ""}
            </th>
            <th class="sortable" onclick={() => handleSort("photobook_size")}>
              Grösse {sortColumn === "photobook_size" ? (sortDirection === "asc" ? "▲" : "▼") : ""}
            </th>
            <th class="actions-header"></th>
```

Replace the body rows (lines 253-277) to add `num` class and icon buttons:

```svelte
              <tr>
                <td class="td-check">
                  <input
                    type="checkbox"
                    checked={selectedIds.has(p.id)}
                    onchange={() => toggleSelect(p.id)}
                  />
                </td>
                <td>{p.title || "Ohne Titel"}</td>
                <td>{formatDate(p.tour_date)}</td>
                <td class="num">{formatDuration(p.tour_duration_hours)}</td>
                <td class="num">{p.total_distance_km ? `${p.total_distance_km} km` : "\u2014"}</td>
                <td class="num">{p.elevation_gain_m ? `${p.elevation_gain_m} m` : "\u2014"}</td>
                <td class="num">{p.image_count ?? "\u2014"}</td>
                <td>{formatSize(p.photobook_size)}</td>
                <td class="actions-cell">
                  <button class="icon-btn" title="Ansehen" onclick={() => handleView(p.id)}>
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                      <circle cx="12" cy="12" r="3"/>
                    </svg>
                  </button>
                  <button class="icon-btn icon-delete" title="Löschen" onclick={() => openSingleDelete(p.id)}>
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                      <polyline points="3 6 5 6 21 6"/>
                      <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                    </svg>
                  </button>
                </td>
              </tr>
```

- [ ] **Step 3: Update CSS to match ArticleList**

Add these CSS blocks to the `<style>` block:

```css
  .filter-duration {
    display: flex;
    align-items: center;
    gap: 4px;
    font-size: 0.75rem;
    color: var(--text-muted);
  }
  .filter-duration-label {
    margin-right: 4px;
  }
  .filter-duration input[type="range"] {
    width: 70px;
    accent-color: var(--accent);
    padding: 0;
    margin: 0;
  }
  .range-val {
    min-width: 18px;
    text-align: center;
    color: var(--text-primary);
    font-size: 0.75rem;
  }
  .filter-sep {
    color: var(--text-muted);
  }
  .filter-unit {
    color: var(--text-muted);
    font-size: 0.7rem;
  }
```

Replace `th`, `td`, `.view-btn`, `.delete-btn` CSS with:

```css
  th {
    text-align: left;
    color: var(--text-muted);
    font-weight: 600;
    padding: 10px 12px;
    border-bottom: 2px solid var(--border);
    white-space: nowrap;
    position: sticky;
    top: 0;
    background: var(--th-bg);
    z-index: 1;
    font-size: 0.72rem;
  }
  td {
    padding: 10px 12px;
    border-bottom: 1px solid var(--border);
    white-space: nowrap;
  }
  .actions-header {
    width: 70px;
  }
  .actions-cell {
    text-align: center;
    white-space: nowrap;
  }
  .icon-btn {
    background: none;
    border: none;
    cursor: pointer;
    padding: 4px;
    opacity: 0.5;
    transition: opacity 0.15s, color 0.15s;
    color: var(--text-secondary);
    display: inline-flex;
    align-items: center;
  }
  .icon-btn:hover {
    opacity: 1;
    color: var(--accent);
  }
  .icon-delete:hover {
    color: var(--error);
  }
```

Replace `.batch-delete-btn` CSS:

```css
  .batch-delete-btn {
    padding: 0.4rem 0.75rem;
    font-size: 0.8rem;
    background: var(--error);
    color: white;
    white-space: nowrap;
    border: none;
    border-radius: var(--radius);
    cursor: pointer;
  }
  .batch-delete-btn:disabled {
    opacity: 0.35;
    cursor: not-allowed;
    background: var(--panel-2);
    color: var(--text-muted);
  }
  .batch-delete-btn:not(:disabled):hover {
    opacity: 0.9;
  }
```

Remove unused `.view-btn` and `.delete-btn` CSS blocks.

- [ ] **Step 4: Run svelte-check**

Run: `cd frontend && npx svelte-check --no-ts-check 2>&1 | tail -10`
Expected: No errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/PhotobookList.svelte
git commit -m "feat: polish photobook list with icons, right-aligned numbers, range slider"
```

---

## Self-Review Checklist

1. **Spec coverage:** Each spec section maps to a task:
   - 1.1 Kompakter Header → Task 4
   - 1.2 Sidebar nur bei Pipeline → Task 4
   - 1.3 Gruppierte Sidebar → Task 4
   - 1.4 Dropzone-Icon → Task 5
   - 1.5 Sticky Run-Button → Task 4 (sidebar CSS)
   - 2.1 Datenmodell → Task 2
   - 2.2 Aggregationslogik → Task 2
   - 2.3 Timeline-Komponente → Task 3
   - 2.4 Erfolgsmeldung → Task 3
   - 2.5 Run-Button Running → Already handled (existing code in RunButton)
   - 2.6 Icon-Buttons → Tasks 6, 7
   - 2.7 Zahlen rechtsbündig → Tasks 6, 7
   - 2.8 Range-Slider → Tasks 6, 7
   - 2.9 Löschen-Button deaktiviert → Tasks 6, 7
   - 2.10 Design-Tokens → Task 1
   - 2.11 Zeilenabstände → Tasks 6, 7

2. **Placeholder scan:** No TBD, TODO, or vague instructions. All code is concrete.

3. **Type consistency:**
   - `StepState` interface matches usage in both `pipeline.ts` and `PipelineTimeline.svelte`
   - `STEP_LABELS` keys match backend stage names
   - CSS class names consistent between tasks

---

## Execution

**Plan complete.** File at `docs/superpowers/plans/2026-05-08-frontend-redesign.md`. All 7 tasks, commit after each.

Two execution options:

1. **Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration
2. **Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints
