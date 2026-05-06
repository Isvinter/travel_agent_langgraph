# Frontend-Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure the Svelte 5 frontend: move navigation tabs from left to right sidebar, introduce settings tabs (Blog/Fotobuch) on the left, consolidate to single run button, remove custom model input.

**Architecture:** Single-page Svelte 5 app with hash-based routing. Left sidebar (340px fixed) contains a vertical form: ModelSelector, FileDropZone, NotesInput, OutputDirInput, SettingsTabs (Blog|Fotobuch), RunButton. Right side (flex: 1) has two tabs: Pipeline (OutputWindow) and Datenbank (ArticleList/ArticleDetail). No frontend test framework exists; verification is manual via dev server.

**Tech Stack:** Svelte 5 (runes mode), TypeScript, Vite 6, svelte/store

---

### Task 1: Create SettingsTabs component

**Files:**
- Create: `frontend/src/lib/SettingsTabs.svelte`

- [ ] **Step 1: Create the component file**

```svelte
<svelte:options runes />

<script lang="ts">
  import { pipelineMode } from "./stores/pipeline";
  import WildcardCount from "./WildcardCount.svelte";
  import LengthSelector from "./LengthSelector.svelte";
  import StyleSelector from "./StyleSelector.svelte";
  import PdfExportCheckbox from "./PdfExportCheckbox.svelte";
  import PhotobookSizeSelector from "./PhotobookSizeSelector.svelte";

  let current = $derived($pipelineMode);

  function select(mode: "blog" | "photobook") {
    pipelineMode.set(mode);
  }
</script>

<div class="settings-tabs">
  <label class="settings-label">Einstellungen</label>

  <div class="tabs">
    <button
      class="tab"
      class:active={current === "blog"}
      onclick={() => select("blog")}
    >
      Blog
    </button>
    <button
      class="tab"
      class:active={current === "photobook"}
      onclick={() => select("photobook")}
    >
      Fotobuch
    </button>
  </div>

  <div class="content">
    {#if current === "blog"}
      <WildcardCount />
      <LengthSelector />
      <StyleSelector />
      <PdfExportCheckbox />
    {:else}
      <PhotobookSizeSelector />
      <div class="pdf-info">
        PDF-Export immer aktiv
      </div>
    {/if}
  </div>
</div>

<style>
  .settings-tabs {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }
  .settings-label {
    font-size: 0.75rem;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  .tabs {
    display: flex;
    gap: 0.25rem;
  }
  .tab {
    flex: 1;
    padding: 0.4rem 0.75rem;
    background: var(--bg);
    color: var(--text-muted);
    font-size: 0.7rem;
    font-weight: 500;
    text-align: center;
    border: 1px solid var(--border);
    border-radius: 3px;
    cursor: pointer;
    transition: background 0.15s, color 0.15s;
  }
  .tab.active {
    background: var(--accent);
    color: white;
    border-color: var(--accent);
    font-weight: bold;
  }
  .tab:hover:not(.active) {
    background: var(--surface-alt);
    color: var(--text);
  }
  .content {
    display: flex;
    flex-direction: column;
    gap: 0.6rem;
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 0.75rem;
  }
  .pdf-info {
    font-size: 0.65rem;
    color: var(--text-muted);
    font-style: italic;
    padding: 0.1rem 0;
  }
</style>
```

- [ ] **Step 2: Verify file was created**

Check that `frontend/src/lib/SettingsTabs.svelte` exists and contains the content above.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/SettingsTabs.svelte
git commit -m "feat: add SettingsTabs component (Blog/Fotobuch)"
```

---

### Task 2: Simplify ModelSelector — remove custom model

**Files:**
- Modify: `frontend/src/lib/ModelSelector.svelte`

- [ ] **Step 1: Replace the component content**

Replace the entire file with the simplified version (no `useCustom`, no `custom` state, no checkbox, no custom input):

```svelte
<script lang="ts">
  import { onMount } from "svelte";
  import { selectedModel } from "./stores/pipeline";

  let models: string[] = $state([]);
  let selected: string = $state("");
  let fetchError: boolean = $state(false);

  onMount(async () => {
    try {
      const res = await fetch("/api/models");
      const data = await res.json();
      models = data.models;
      if (models.length > 0) {
        selected = models[0];
        selectedModel.set(selected);
      }
    } catch (e) {
      console.error("Failed to fetch models:", e);
      fetchError = true;
    }
  });

  function handleModelChange() {
    if (selected) {
      selectedModel.set(selected);
    }
  }
</script>

<div class="selector">
  <label for="model-select">Modell</label>
  {#if models.length === 0 && !fetchError}
    <select disabled><option>Modelle werden geladen…</option></select>
  {:else if models.length === 0 && fetchError}
    <select disabled><option>Fehler beim Laden der Modelle</option></select>
  {:else}
    <select id="model-select" bind:value={selected} onchange={handleModelChange}>
      {#each models as m}
        <option value={m}>{m}</option>
      {/each}
    </select>
  {/if}
</div>

<style>
  .selector {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }
  label {
    font-size: 0.75rem;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  select {
    width: 100%;
  }
</style>
```

- [ ] **Step 2: Verify with dev server**

```bash
cd frontend && npm run dev
```

Open the app, verify the model dropdown works without the "eigenes Modell" checkbox.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/ModelSelector.svelte
git commit -m "refactor: remove custom model input from ModelSelector"
```

---

### Task 3: Adapt RunButton — read mode from store

**Files:**
- Modify: `frontend/src/lib/RunButton.svelte`

- [ ] **Step 1: Remove the `mode` prop and read from store**

In the `Props` interface, remove `mode`. In the file, change the `mode` usage to read from `pipelineMode` store.

Replace the file content:

```svelte
<script lang="ts">
  import { get } from "svelte/store";
  import {
    runState,
    addLine,
    startStream,
    resetPipeline,
    selectedModel,
    pipelineFiles,
    outputDir,
    notesField,
    wildcardCount,
    articleLength,
    stylePersona,
    pdfExport,
    photobookSize,
    pipelineMode,
  } from "./stores/pipeline";

  let loading: boolean = $state(false);

  async function handleRun() {
    const mode = get(pipelineMode);
    const model = get(selectedModel);
    const { gpxFile, imageFiles, txtFile } = get(pipelineFiles);
    const dir = get(outputDir);
    const notes = get(notesField);

    if (!gpxFile) {
      addLine("validation", "error", "Keine GPX-Datei ausgewählt.");
      return;
    }

    resetPipeline();
    loading = true;

    try {
      const body: Record<string, unknown> = {
        model,
        output_dir: dir,
        notes,
        txt_file: txtFile || "",
        gpx_file: gpxFile,
        image_files: imageFiles,
        mode,
      };

      if (mode === "blog") {
        const wc = get(wildcardCount);
        const length = get(articleLength);
        const persona = get(stylePersona);
        const pdf = get(pdfExport);
        body.wildcard_max = wc;
        body.article_length = length;
        body.style_persona = persona;
        body.pdf_export = pdf;
      } else {
        const size = get(photobookSize);
        body.photobook_size = size;
      }

      const res = await fetch("/api/pipeline/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      if (!res.ok) {
        const err = await res.json();
        addLine("validation", "error", err.detail || "Fehler beim Starten der Pipeline.");
        loading = false;
        return;
      }

      const data = await res.json();
      startStream(data.run_id);
    } catch (e: any) {
      addLine("connection", "error", `Verbindungsfehler: ${e.message}`);
    } finally {
      loading = false;
    }
  }

  let rs = $derived($runState);
  let buttonLabel = $derived(
    rs === "running" || loading
      ? "Läuft…"
      : rs === "done"
        ? "✓ Abgeschlossen"
        : rs === "failed"
          ? "✗ Fehlgeschlagen — Erneut"
          : "▶ Pipeline starten"
  );
</script>

<button
  class="run-btn"
  disabled={rs === "running" || loading}
  onclick={handleRun}
>
  {#if rs === "running" || loading}
    <span class="spinner"></span>
    Läuft…
  {:else}
    {buttonLabel}
  {/if}
</button>

<style>
  .run-btn {
    width: 100%;
    padding: 0.6rem;
    background: var(--accent);
    color: white;
    font-weight: bold;
    font-size: 0.75rem;
    letter-spacing: 0.03em;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
    transition: background 0.2s;
  }
  .run-btn:hover:not(:disabled) {
    background: var(--accent-hover);
  }
  .run-btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
  .spinner {
    width: 14px;
    height: 14px;
    border: 2px solid rgba(255, 255, 255, 0.3);
    border-top-color: white;
    border-radius: 50%;
    animation: spin 0.6s linear infinite;
  }
  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }
</style>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/lib/RunButton.svelte
git commit -m "refactor: RunButton reads pipelineMode from store instead of prop"
```

---

### Task 4: Delete ModeTabs component

**Files:**
- Delete: `frontend/src/lib/ModeTabs.svelte`

- [ ] **Step 1: Delete the file**

```bash
rm frontend/src/lib/ModeTabs.svelte
```

- [ ] **Step 2: Commit**

```bash
git rm frontend/src/lib/ModeTabs.svelte
git commit -m "refactor: remove ModeTabs (replaced by SettingsTabs)"
```

---

### Task 5: Rewrite App.svelte layout

**Files:**
- Modify: `frontend/src/App.svelte`

- [ ] **Step 1: Replace App.svelte with the new layout**

```svelte
<svelte:options runes />

<script lang="ts">
  import { route, navigateTo } from "./lib/stores/router";
  import { pipelineMode, runState } from "./lib/stores/pipeline";
  import ModelSelector from "./lib/ModelSelector.svelte";
  import FileDropZone from "./lib/FileDropZone.svelte";
  import OutputDirInput from "./lib/OutputDirInput.svelte";
  import NotesInput from "./lib/NotesInput.svelte";
  import SettingsTabs from "./lib/SettingsTabs.svelte";
  import RunButton from "./lib/RunButton.svelte";
  import OutputWindow from "./lib/OutputWindow.svelte";
  import ArticleList from "./lib/ArticleList.svelte";
  import ArticleDetail from "./lib/ArticleDetail.svelte";

  let rt = $derived($route);
  let currentMode = $derived($pipelineMode);
  let rightTab = $state<"pipeline" | "datenbank">(
    rt.page === "pipeline" ? "pipeline" : "datenbank"
  );

  function switchRightTab(tab: "pipeline" | "datenbank") {
    rightTab = tab;
    if (tab === "pipeline") {
      navigateTo({ page: "pipeline" });
    } else {
      navigateTo({ page: "articles" });
    }
  }

  // Wenn Pipeline gestartet wird, automatisch zum Pipeline-Tab wechseln
  $effect(() => {
    if ($runState === "running" && rightTab !== "pipeline") {
      rightTab = "pipeline";
      navigateTo({ page: "pipeline" });
    }
  });
</script>

<div class="layout">
  <!-- LINKE SIDEBAR -->
  <aside class="sidebar">
    <h1 class="title">Travel Agent</h1>

    <ModelSelector />
    <FileDropZone />
    <NotesInput />
    <OutputDirInput />
    <SettingsTabs />

    <div class="run-section">
      <RunButton />
    </div>
  </aside>

  <!-- RECHTE SEITE -->
  <main class="main">
    <nav class="right-tabs">
      <button
        class="right-tab"
        class:active={rightTab === "pipeline"}
        onclick={() => switchRightTab("pipeline")}
      >
        Pipeline
      </button>
      <button
        class="right-tab"
        class:active={rightTab === "datenbank"}
        onclick={() => switchRightTab("datenbank")}
      >
        Datenbank
      </button>
    </nav>

    <div class="right-content">
      {#if rightTab === "pipeline"}
        <OutputWindow />
      {:else if rt.page === "article"}
        <ArticleDetail id={rt.id} />
      {:else}
        <ArticleList />
      {/if}
    </div>
  </main>
</div>

<style>
  .layout {
    display: flex;
    height: 100vh;
    width: 100vw;
  }
  .sidebar {
    width: 340px;
    min-width: 340px;
    background: var(--surface);
    border-right: 1px solid var(--border);
    padding: 1.25rem;
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    overflow-y: auto;
  }
  .title {
    font-size: 1rem;
    font-weight: bold;
    color: var(--accent);
    letter-spacing: 0.05em;
    text-transform: uppercase;
  }
  .run-section {
    margin-top: auto;
    padding-top: 0.25rem;
  }

  .main {
    flex: 1;
    display: flex;
    flex-direction: column;
    padding: 1rem;
    overflow: hidden;
  }
  .right-tabs {
    display: flex;
    gap: 0.25rem;
    margin-bottom: 0.75rem;
    flex-shrink: 0;
  }
  .right-tab {
    padding: 0.5rem 1rem;
    background: var(--surface);
    color: var(--text-muted);
    font-size: 0.8rem;
    font-weight: 500;
    border: 1px solid var(--border);
    border-radius: 4px;
    cursor: pointer;
    transition: background 0.15s, color 0.15s;
  }
  .right-tab.active {
    background: var(--accent);
    color: white;
    border-color: var(--accent);
  }
  .right-tab:hover:not(.active) {
    background: var(--surface-alt);
    color: var(--text);
  }
  .right-content {
    flex: 1;
    display: flex;
    flex-direction: column;
    min-height: 0;
  }
</style>
```

- [ ] **Step 2: Start dev server and verify layout**

```bash
cd frontend && npm run dev
```

Verify:
1. Left sidebar has: title, model dropdown, file dropzone, notes, output dir, settings tabs, run button
2. Right side has two tabs: Pipeline, Datenbank
3. Blog/Fotobuch tabs inside SettingsTabs switch correctly
4. Run button uses the active settings tab mode
5. Clicking run switches to Pipeline tab
6. Datenbank tab shows article list, clicking "Ansehen" shows detail, "Zurück" returns to list

- [ ] **Step 3: Build to verify no compilation errors**

```bash
cd frontend && npm run build
```

Expected: Build succeeds with no errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/App.svelte
git commit -m "refactor: restructure App layout with right-side tabs and settings tabs"
```

---

### Task 6: Verify router integration

**Files:**
- No changes needed to `frontend/src/lib/stores/router.ts`
- The existing `navigateTo({ page: "articles" })` calls in `ArticleList.svelte` and `ArticleDetail.svelte` still work correctly

- [ ] **Step 1: Verify no changes needed**

The router already handles `#/`, `#/articles`, and `#/articles/:id`. The new `App.svelte` uses `navigateTo({ page: "articles" })` for the Datenbank tab and `navigateTo({ page: "pipeline" })` for the Pipeline tab. No changes required.

- [ ] **Step 2: Verify by building**

```bash
cd frontend && npm run build
```

Expected: Build succeeds with no TypeScript errors.

---

### Task 7: Final verification

- [ ] **Step 1: Start the full dev environment**

```bash
# Terminal 1: FastAPI backend
uv run uvicorn app.api.server:app --reload --host 0.0.0.0 --port 8000

# Terminal 2: Svelte frontend
cd frontend && npm run dev
```

- [ ] **Step 2: Smoke test checklist**

- [ ] Model dropdown loads Ollama models correctly
- [ ] File dropzone accepts files (drop + browse)
- [ ] Notes input works
- [ ] Output directory input works
- [ ] Settings tabs switch between Blog and Fotobuch settings
- [ ] Blog settings: WildcardCount, LengthSelector, StyleSelector, PdfExportCheckbox all visible and functional
- [ ] Fotobuch settings: PhotobookSizeSelector visible and functional
- [ ] Run button starts the active mode's pipeline
- [ ] Pipeline tab auto-switches on run
- [ ] OutputWindow shows log lines
- [ ] Datenbank tab shows article list
- [ ] Article detail navigation works
- [ ] "Zurück zur Liste" returns to article list within Datenbank tab

- [ ] **Step 3: Final build check**

```bash
cd frontend && npm run build
```

Expected: Clean build, no errors.

