# Photobook Frontend Integration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate the existing photobook backend pipeline into the Svelte frontend with a two-column sidebar, mode tabs, and per-mode settings.

**Architecture:** Sidebar expands to ~680px with shared fields (model, files) on top and two 50:50 columns below for blog and photobook settings. A segmented control switches between modes, dimming the inactive column. Each column has its own Run button. Backend receives `mode` and `photobook_size` in the pipeline request, maps size to PhotobookConfig ranges.

**Tech Stack:** Svelte 5 runes, TypeScript, FastAPI, Pydantic

**Spec:** `docs/superpowers/specs/2026-05-05-photobook-frontend-integration-design.md`

---

## File Structure

| Path | Action | Responsibility |
|---|---|---|
| `app/state.py` | Modify | Add `size`, `page_range` to `PhotobookConfig`, add `PHOTOBOOK_SIZE_MAP` |
| `app/api/routes.py` | Modify | Extend `RunPipelineRequest`, photobook size→config mapping, PDF download route |
| `tests/test_state.py` | Modify | Tests for new PhotobookConfig fields |
| `tests/test_api_endpoints.py` | Modify | Tests for new route and request fields |
| `frontend/src/lib/stores/pipeline.ts` | Modify | Add `pipelineMode` and `photobookSize` stores |
| `frontend/src/lib/ModeTabs.svelte` | Create | Blog/Fotobuch segmented control |
| `frontend/src/lib/PhotobookSizeSelector.svelte` | Create | Short/Medium/Long radio buttons |
| `frontend/src/App.svelte` | Modify | Two-column layout with shared fields + per-column sections |
| `frontend/src/lib/RunButton.svelte` | Modify | Mode-aware payload building |

---

### Task 1: Extend PhotobookConfig with size and page_range

**Files:**
- Modify: `app/state.py:39-41`
- Modify: `tests/test_state.py` (add tests)

- [ ] **Step 1: Add size and page_range fields to PhotobookConfig**

```python
# In app/state.py, replace the PhotobookConfig class:

class PhotobookConfig(BaseModel):
    """Konfiguration fuer die Fotobuch-Ausgabe."""
    photo_count: int = Field(default=20, ge=5, le=30)
    page_range: str = "14-18"
    size: Literal["short", "normal", "detailed"] = "normal"
```

- [ ] **Step 2: Add PHOTOBOOK_SIZE_MAP constant**

```python
# In app/state.py, add after PhotobookConfig class:

PHOTOBOOK_SIZE_MAP = {
    "short":    {"photo_count": 14, "page_range": "8-12"},
    "normal":   {"photo_count": 20, "page_range": "14-18"},
    "detailed": {"photo_count": 26, "page_range": "20-24"},
}
```

- [ ] **Step 3: Add function to apply size mapping to PhotobookConfig**

```python
# In app/state.py, add after PHOTOBOOK_SIZE_MAP:

def apply_photobook_size(size: str) -> PhotobookConfig:
    """Erzeugt PhotobookConfig aus Grössenstufe (short/normal/detailed)."""
    mapping = PHOTOBOOK_SIZE_MAP.get(size, PHOTOBOOK_SIZE_MAP["normal"])
    return PhotobookConfig(
        photo_count=mapping["photo_count"],
        page_range=mapping["page_range"],
        size=size,
    )
```

- [ ] **Step 4: Write tests for new PhotobookConfig fields**

```python
# In tests/test_state.py, add to TestPhotobookConfig class:

def test_size_field_defaults_to_normal(self):
    """size ist standardmässig 'normal'."""
    from app.state import PhotobookConfig
    config = PhotobookConfig()
    assert config.size == "normal"

def test_page_range_default(self):
    """page_range ist standardmässig '14-18'."""
    from app.state import PhotobookConfig
    config = PhotobookConfig()
    assert config.page_range == "14-18"

def test_size_short(self):
    """size='short' ist erlaubt."""
    from app.state import PhotobookConfig
    config = PhotobookConfig(size="short", page_range="8-12", photo_count=14)
    assert config.size == "short"
    assert config.page_range == "8-12"
```

- [ ] **Step 5: Write tests for apply_photobook_size**

```python
# In tests/test_state.py, add new class:

class TestApplyPhotobookSize:
    def test_short_maps_correctly(self):
        from app.state import apply_photobook_size
        config = apply_photobook_size("short")
        assert config.photo_count == 14
        assert config.page_range == "8-12"
        assert config.size == "short"

    def test_normal_maps_correctly(self):
        from app.state import apply_photobook_size
        config = apply_photobook_size("normal")
        assert config.photo_count == 20
        assert config.page_range == "14-18"
        assert config.size == "normal"

    def test_detailed_maps_correctly(self):
        from app.state import apply_photobook_size
        config = apply_photobook_size("detailed")
        assert config.photo_count == 26
        assert config.page_range == "20-24"
        assert config.size == "detailed"

    def test_unknown_size_falls_back_to_normal(self):
        from app.state import apply_photobook_size
        config = apply_photobook_size("invalid")
        assert config.photo_count == 20
        assert config.size == "normal"
```

- [ ] **Step 6: Run tests**

```bash
uv run pytest tests/test_state.py -v -k "TestPhotobookConfig or TestApplyPhotobookSize"
```
Expected: 8 passed (5 new + 3 existing PhotobookConfig tests)

- [ ] **Step 7: Commit**

```bash
git add app/state.py tests/test_state.py
git commit -m "feat: add size/page_range to PhotobookConfig with size mapping"
```

---

### Task 2: Extend API for photobook mode

**Files:**
- Modify: `app/api/routes.py:147-158` (RunPipelineRequest)
- Modify: `app/api/routes.py:217-311` (_run_pipeline_in_background)
- Modify: `app/api/routes.py` (add photobook PDF route)

- [ ] **Step 1: Add photobook_size to RunPipelineRequest**

```python
# In app/api/routes.py, modify RunPipelineRequest:
# Add after line 157 (pdf_export: bool = False):

    photobook_size: Literal["short", "normal", "detailed"] | None = None
```

- [ ] **Step 2: Apply photobook_size mapping in _run_pipeline_in_background**

```python
# In app/api/routes.py, in _run_pipeline_in_background,
# add after line 249 (state = AppState(...)):
# Before the state = AppState() block, add photobook config logic:

        # Fotobuch-Konfiguration aus Grössenstufe ableiten
        from app.state import apply_photobook_size
        photobook_config = apply_photobook_size(body.photobook_size or "normal")

        state = AppState(
            gpx_file=gpx_file,
            model=model,
            notes=combined_notes,
            output_config=OutputConfig(
                wildcard_max=body.wildcard_max,
                article_length=body.article_length,
                style_persona=body.style_persona,
                pdf_export=body.pdf_export,
                photobook=photobook_config,
            ),
        )
```

- [ ] **Step 3: Store photobook PDF path in result and __done__ event**

```python
# In app/api/routes.py, in _run_pipeline_in_background,
# replace the result storage section (lines 276-302) with:

        # Extract output paths
        blog_post = result.blog_post if hasattr(result, "blog_post") else None
        photobook_html = result.photobook_html if hasattr(result, "photobook_html") else None
        photobook_pdf_path = result.photobook_pdf_path if hasattr(result, "photobook_pdf_path") else None

        output_paths = {}
        if blog_post and isinstance(blog_post, dict):
            output_paths = blog_post.get("file_paths", {})

        event_manager.store_result(run_id, {
            "markdown": blog_post.get("markdown", "") if blog_post else "",
            "html": blog_post.get("html", "") if blog_post else "",
            "file_paths": output_paths,
            "success": True,
            "photobook_pdf_path": photobook_pdf_path,
        })

        output_path = output_paths.get("markdown", output_dir)

        article_id = None
        pdf_available = False
        if hasattr(result, "metadata"):
            article_id = result.metadata.get("article_id")
        if blog_post and isinstance(blog_post, dict) and "pdf_bytes" in blog_post:
            pdf_available = True

        # Fotobuch: PDF verfügbar wenn Pfad gesetzt ist
        if photobook_pdf_path:
            pdf_available = True

        event_manager.complete_run(
            run_id, "success", output_path,
            article_id=article_id,
            pdf_available=pdf_available,
        )
```

- [ ] **Step 4: Add photobook PDF download route**

```python
# In app/api/routes.py, add after the existing PDF export section (after line 466):

# ── Photobook PDF Download ─────────────────────────────

@router.get("/photobook/{run_id}/pdf")
async def download_photobook_pdf(run_id: str):
    """Liefert das generierte Fotobuch-PDF eines Pipeline-Runs aus."""
    result = event_manager.get_result(run_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Run nicht gefunden oder noch nicht abgeschlossen")

    pdf_path = result.get("photobook_pdf_path")
    if not pdf_path:
        raise HTTPException(status_code=400, detail="Kein PDF für diesen Run verfügbar")

    path = Path(pdf_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="PDF-Datei nicht gefunden")

    return FileResponse(
        path,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{path.name}"',
            "Cache-Control": "no-cache",
        },
    )
```

- [ ] **Step 5: Write test for RunPipelineRequest with photobook_size**

```python
# In tests/test_api_endpoints.py, add to TestPipelineRun class:

def test_run_with_photobook_size_returns_run_id(self, client):
    """Pipeline-Run mit photobook_size='normal' akzeptiert."""
    response = client.post("/api/pipeline/run", json={
        "model": "gemma4:26b-ctx128k",
        "gpx_file": "tests/fixtures/nonexistent.gpx",
        "image_files": [],
        "photobook_size": "normal",
    })
    assert response.status_code == 200
    data = response.json()
    assert "run_id" in data

def test_run_with_invalid_photobook_size_fails(self, client):
    """Ungültige photobook_size wird abgelehnt."""
    response = client.post("/api/pipeline/run", json={
        "model": "gemma4:26b-ctx128k",
        "gpx_file": "tests/fixtures/nonexistent.gpx",
        "image_files": [],
        "photobook_size": "invalid_value",
    })
    assert response.status_code == 422
```

- [ ] **Step 6: Write test for photobook PDF download route**

```python
# In tests/test_api_endpoints.py, add new class:

class TestPhotobookPdf:
    def test_missing_run_returns_404(self, client):
        response = client.get("/api/photobook/nonexistent-run/pdf")
        assert response.status_code == 404

    def test_run_without_pdf_returns_400(self, monkeypatch):
        """Run existiert, aber hat kein photobook_pdf_path."""
        from app.api.events import PipelineEventManager
        mgr = PipelineEventManager()
        mgr.store_result("test-run-no-pdf", {"success": True})
        monkeypatch.setattr("app.api.routes.event_manager", mgr)
        from fastapi.testclient import TestClient
        from app.api.server import create_app
        app = create_app()
        client = TestClient(app)
        response = client.get("/api/photobook/test-run-no-pdf/pdf")
        assert response.status_code == 400

    def test_valid_pdf_served(self, monkeypatch, tmp_path):
        """PDF-Datei wird korrekt ausgeliefert."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 mock photobook")

        from app.api.events import PipelineEventManager
        mgr = PipelineEventManager()
        mgr.store_result("test-run-pdf", {
            "success": True,
            "photobook_pdf_path": str(pdf_file),
        })
        monkeypatch.setattr("app.api.routes.event_manager", mgr)
        from fastapi.testclient import TestClient
        from app.api.server import create_app
        app = create_app()
        client = TestClient(app)

        response = client.get("/api/photobook/test-run-pdf/pdf")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert "attachment" in response.headers["content-disposition"]
        assert response.content == b"%PDF-1.4 mock photobook"
```

- [ ] **Step 7: Run API tests**

```bash
uv run pytest tests/test_api_endpoints.py -v -k "TestPipelineRun or TestPhotobookPdf"
```
Expected: 6 passed

- [ ] **Step 8: Commit**

```bash
git add app/api/routes.py tests/test_api_endpoints.py
git commit -m "feat: add photobook_size to pipeline API and PDF download route"
```

---

### Task 3: Add pipelineMode and photobookSize to frontend stores

**Files:**
- Modify: `frontend/src/lib/stores/pipeline.ts`

- [ ] **Step 1: Add new stores to pipeline.ts**

```typescript
// In frontend/src/lib/stores/pipeline.ts, add after line 47 (pdfExport):

export const pipelineMode = writable<"blog" | "photobook">("blog");
export const photobookSize = writable<"short" | "normal" | "detailed">("normal");
```

- [ ] **Step 2: Verify TypeScript compilation**

```bash
cd frontend && npm run check 2>&1 | head -20
```
Expected: No new errors related to pipeline.ts

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/stores/pipeline.ts
git commit -m "feat: add pipelineMode and photobookSize stores"
```

---

### Task 4: Create ModeTabs component

**Files:**
- Create: `frontend/src/lib/ModeTabs.svelte`

- [ ] **Step 1: Write the component**

```svelte
<svelte:options runes />

<script lang="ts">
  import { pipelineMode } from "./stores/pipeline";

  let current: "blog" | "photobook" = $state("blog");

  function select(mode: "blog" | "photobook") {
    current = mode;
    pipelineMode.set(mode);
  }

  $effect(() => {
    pipelineMode.set(current);
  });
</script>

<div class="mode-tabs">
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

<style>
  .mode-tabs {
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
</style>
```

- [ ] **Step 2: Verify TypeScript compilation**

```bash
cd frontend && npm run check 2>&1 | head -20
```
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/ModeTabs.svelte
git commit -m "feat: add ModeTabs component for Blog/Fotobuch switching"
```

---

### Task 5: Create PhotobookSizeSelector component

**Files:**
- Create: `frontend/src/lib/PhotobookSizeSelector.svelte`

- [ ] **Step 1: Write the component**

```svelte
<svelte:options runes />

<script lang="ts">
  import { photobookSize } from "./stores/pipeline";

  let selected: string = $state("normal");

  const options = [
    { value: "short", label: "Kurz", desc: "8-12 Seiten" },
    { value: "normal", label: "Mittel", desc: "14-18 Seiten" },
    { value: "detailed", label: "Lang", desc: "20-24 Seiten" },
  ];

  function handleChange() {
    photobookSize.set(selected as "short" | "normal" | "detailed");
  }
</script>

<div class="size">
  <label>Umfang</label>
  <div class="options-compact">
    {#each options as opt}
      <label class="option-compact">
        <input
          type="radio"
          name="photobook-size"
          value={opt.value}
          bind:group={selected}
          onchange={handleChange}
        />
        <div class="option-text">
          <span class="option-label">{opt.label}</span>
          <span class="option-desc">{opt.desc}</span>
        </div>
      </label>
    {/each}
  </div>
</div>

<style>
  .size {
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
  }
  label:first-child {
    font-size: 0.7rem;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  .options-compact {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }
  .option-compact {
    display: flex;
    align-items: flex-start;
    gap: 0.4rem;
    cursor: pointer;
    font-size: 0.75rem;
    color: var(--text);
    padding: 0.2rem 0;
  }
  .option-compact input[type="radio"] {
    accent-color: var(--accent);
    margin-top: 0.12rem;
    flex-shrink: 0;
  }
  .option-text {
    display: flex;
    flex-direction: column;
    gap: 0.05rem;
  }
  .option-label {
    font-weight: 500;
  }
  .option-desc {
    font-size: 0.65rem;
    color: var(--text-muted);
  }
</style>
```

- [ ] **Step 2: Verify TypeScript compilation**

```bash
cd frontend && npm run check 2>&1 | head -20
```
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/PhotobookSizeSelector.svelte
git commit -m "feat: add PhotobookSizeSelector component"
```

---

### Task 6: Refactor App.svelte for two-column sidebar

**Files:**
- Modify: `frontend/src/App.svelte`
- Modify: `frontend/src/app.css` (check if sidebar width variable exists)

- [ ] **Step 1: Read app.css to check existing CSS variables**

```bash
cat frontend/src/app.css | head -50
```

- [ ] **Step 2: Refactor App.svelte with two-column layout**

Replace the full content of `frontend/src/App.svelte`:

```svelte
<svelte:options runes />

<script lang="ts">
  import { route, navigateTo } from "./lib/stores/router";
  import { pipelineMode } from "./lib/stores/pipeline";
  import ModelSelector from "./lib/ModelSelector.svelte";
  import FileDropZone from "./lib/FileDropZone.svelte";
  import OutputDirInput from "./lib/OutputDirInput.svelte";
  import ModeTabs from "./lib/ModeTabs.svelte";
  import LengthSelector from "./lib/LengthSelector.svelte";
  import StyleSelector from "./lib/StyleSelector.svelte";
  import PdfExportCheckbox from "./lib/PdfExportCheckbox.svelte";
  import NotesInput from "./lib/NotesInput.svelte";
  import WildcardCount from "./lib/WildcardCount.svelte";
  import PhotobookSizeSelector from "./lib/PhotobookSizeSelector.svelte";
  import RunButton from "./lib/RunButton.svelte";
  import OutputWindow from "./lib/OutputWindow.svelte";
  import ArticleList from "./lib/ArticleList.svelte";
  import ArticleDetail from "./lib/ArticleDetail.svelte";

  let rt = $derived($route);
  let currentMode = $derived($pipelineMode);
</script>

<div class="layout">
  <aside class="sidebar" class:sidebar-blog={rt.page === "pipeline"}>
    <h1 class="title">Travel Agent</h1>

    <nav class="nav-tabs">
      <button
        class="nav-tab"
        class:active={rt.page === "pipeline"}
        onclick={() => navigateTo({ page: "pipeline" })}
      >
        Pipeline
      </button>
      <button
        class="nav-tab"
        class:active={rt.page === "articles" || rt.page === "article"}
        onclick={() => navigateTo({ page: "articles" })}
      >
        Artikel
      </button>
    </nav>

    {#if rt.page === "pipeline"}
      <ModeTabs />

      <ModelSelector />
      <FileDropZone />
      <OutputDirInput />

      <div class="columns">
        <div class="column" class:inactive={currentMode !== "blog"}>
          <div class="column-badge">Blog</div>
          <NotesInput />
          <WildcardCount />
          <LengthSelector />
          <StyleSelector />
          <PdfExportCheckbox />
          <div class="run-section">
            <RunButton mode="blog" />
          </div>
        </div>

        <div class="column" class:inactive={currentMode !== "photobook"}>
          <div class="column-badge">Fotobuch</div>
          <PhotobookSizeSelector />
          <div class="pdf-info">
            PDF-Export immer aktiv
          </div>
          <div class="run-section">
            <RunButton mode="photobook" />
          </div>
        </div>
      </div>
    {/if}
  </aside>

  <main class="main">
    {#if rt.page === "pipeline"}
      <OutputWindow />
    {:else if rt.page === "articles"}
      <ArticleList />
    {:else if rt.page === "article"}
      <ArticleDetail id={rt.id} />
    {/if}
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
    transition: width 0.2s;
  }
  .sidebar.sidebar-blog {
    width: 680px;
    min-width: 680px;
  }
  .title {
    font-size: 1rem;
    font-weight: bold;
    color: var(--accent);
    letter-spacing: 0.05em;
    text-transform: uppercase;
  }
  .nav-tabs {
    display: flex;
    gap: 0.25rem;
  }
  .nav-tab {
    flex: 1;
    padding: 0.5rem 0.75rem;
    background: var(--bg);
    color: var(--text-muted);
    font-size: 0.8rem;
  }
  .nav-tab.active {
    background: var(--accent);
    color: white;
  }
  .nav-tab:hover:not(.active) {
    background: var(--surface-alt);
    color: var(--text);
  }

  .columns {
    display: flex;
    gap: 0.75rem;
    flex: 1;
    min-height: 0;
  }
  .column {
    flex: 1;
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 0.75rem;
    display: flex;
    flex-direction: column;
    gap: 0.6rem;
    position: relative;
    transition: opacity 0.2s;
  }
  .column.inactive {
    opacity: 0.45;
    pointer-events: none;
  }
  .column-badge {
    position: absolute;
    top: -0.55rem;
    left: 0.5rem;
    background: var(--bg);
    color: var(--accent);
    font-size: 0.6rem;
    font-weight: bold;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    padding: 0 0.35rem;
  }
  .run-section {
    margin-top: auto;
    padding-top: 0.25rem;
  }
  .pdf-info {
    font-size: 0.65rem;
    color: var(--text-muted);
    font-style: italic;
    padding: 0.1rem 0;
  }

  .main {
    flex: 1;
    display: flex;
    flex-direction: column;
    padding: 1rem;
    overflow: hidden;
  }
</style>
```

- [ ] **Step 2: Verify TypeScript compilation**

```bash
cd frontend && npm run check 2>&1
```
Expected: No errors (may have warnings about existing code)

- [ ] **Step 3: Commit**

```bash
git add frontend/src/App.svelte
git commit -m "feat: two-column sidebar layout with Blog/Fotobuch columns"
```

---

### Task 7: Refactor RunButton for mode-aware payload

**Files:**
- Modify: `frontend/src/lib/RunButton.svelte`

- [ ] **Step 1: Update RunButton to accept mode prop**

Replace the full content of `frontend/src/lib/RunButton.svelte`:

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
  } from "./stores/pipeline";

  interface Props {
    mode: "blog" | "photobook";
  }

  let { mode }: Props = $props();

  let loading: boolean = $state(false);

  async function handleRun() {
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
          : `▶ ${mode === "blog" ? "Blog" : "Fotobuch"} generieren`
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

- [ ] **Step 2: Update startStream in pipeline.ts for photobook PDF download**

```typescript
// In frontend/src/lib/stores/pipeline.ts, modify the "done" event listener (lines 80-99):

  eventSource.addEventListener("done", async (e: MessageEvent) => {
    eventSource?.close();
    const data = JSON.parse(e.data);
    const isSuccess = data.status === "success";
    addLine("__done__", data.status, `Pipeline ${isSuccess ? "erfolgreich" : "fehlgeschlagen"}.`);
    runState.set(isSuccess ? "done" : "failed");

    // Auto-download PDF if available
    if (data.pdf_available) {
      if (data.article_id) {
        window.open(`/api/articles/${data.article_id}/pdf`, "_blank");
      } else {
        window.open(`/api/photobook/${get(currentRunId)}/pdf`, "_blank");
      }
    }

    try {
      const res = await fetch(`/api/pipeline/result/${runId}`);
      if (res.ok) {
        result.set(await res.json());
      }
    } catch (err) {
      console.error("Failed to fetch result:", err);
    }
  });
```

- [ ] **Step 3: Verify TypeScript compilation**

```bash
cd frontend && npm run check 2>&1
```
Expected: No errors

- [ ] **Step 4: Commit**

```bash
git add frontend/src/lib/RunButton.svelte frontend/src/lib/stores/pipeline.ts
git commit -m "feat: mode-aware RunButton with per-mode payload and photobook PDF download"
```

---

### Task 8: Integration verification

**Files:**
- Verify: All changed files compile and tests pass

- [ ] **Step 1: Run all backend tests**

```bash
uv run pytest tests/test_state.py tests/test_api_endpoints.py -v
```
Expected: All tests pass

- [ ] **Step 2: Run full test suite**

```bash
uv run pytest tests/ -v --ignore=tests/test_photobook --ignore=tests/test_services/test_blog_generator.py --ignore=tests/test_nodes/test_generate_blogpost.py --ignore=tests/test_services/test_content_reviewer.py --ignore=tests/test_services/test_blog_prompt_enrichment.py --ignore=tests/test_api/test_enrichment_e2e.py --ignore=tests/test_graph/test_pipeline_e2e.py --ignore=tests/test_graph/test_enrichment_graph.py
```
Expected: All tests pass

- [ ] **Step 3: Verify frontend builds**

```bash
cd frontend && npm run build 2>&1
```
Expected: Build succeeds

- [ ] **Step 4: Verify lint passes**

```bash
uv run ruff check app/state.py app/api/routes.py
```
Expected: No lint errors

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "chore: verify tests and build for photobook frontend integration"
```
