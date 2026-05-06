# PDF-Export für Artikel — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add PDF export for blog articles — a pipeline menu checkbox ("Als PDF exportieren") that auto-downloads after generation, and a green button in the article detail view for existing articles.

**Architecture:** Backend generates PDFs using Selenium Chrome's CDP `Page.printToPDF` (same Chrome already used for map screenshots). A new LangGraph pipeline node runs conditionally when `pdf_export=True`. Frontend triggers download via `window.open` on the new `GET /api/articles/{id}/pdf` endpoint.

**Tech Stack:** Python, FastAPI, Selenium/Chrome (existing), LangGraph, Svelte 5 (runes mode), TypeScript

---

## File Structure

| Action | File | Responsibility |
|--------|------|---------------|
| Create | `app/services/generate_pdf.py` | Rewrite HTML image paths → Chrome CDP → return PDF bytes |
| Create | `app/nodes/generate_pdf.py` | Thin pipeline node: AppState → AppState, calls service |
| Create | `tests/test_services/test_generate_pdf.py` | Unit tests for path rewriting + integration tests for PDF generation |
| Modify | `app/state.py:39-43` | Add `pdf_export: bool` to `OutputConfig` |
| Modify | `app/api/routes.py:146-156` | Add `pdf_export: bool` to `RunPipelineRequest` |
| Modify | `app/api/routes.py:414` | Add `GET /api/articles/{id}/pdf` endpoint |
| Modify | `app/api/routes.py:215-295` | Pass `pdf_export` through pipeline, include article_id/pdf_available in done event |
| Modify | `app/api/events.py:31-37` | Add `article_id` and `pdf_available` params to `complete_run` |
| Modify | `app/graph.py` | Add `generate_pdf` node + conditional edge from `persist_article` |
| Modify | `tests/test_api_endpoints.py` | Add test for `/api/articles/{id}/pdf` endpoint |
| Modify | `tests/test_state.py` | Add test for `OutputConfig.pdf_export` default |
| Modify | `frontend/src/lib/stores/pipeline.ts` | Add `pdfExport` writable store |
| Create | `frontend/src/lib/PdfExportCheckbox.svelte` | Checkbox component for pipeline sidebar |
| Modify | `frontend/src/App.svelte` | Import and render `PdfExportCheckbox` |
| Modify | `frontend/src/lib/RunButton.svelte` | Post `pdf_export` field + auto-download on done |
| Modify | `frontend/src/lib/ArticleDetail.svelte:80-90,132-162` | Add green PDF button left of delete, toolbar refactor |

---

### Task 1: Backend PDF Service

**Files:**
- Create: `app/services/generate_pdf.py`
- Create: `tests/test_services/test_generate_pdf.py`

- [ ] **Step 1: Write the unit test for path rewriting**

Create `tests/test_services/test_generate_pdf.py`:

```python
"""Tests for app/services/generate_pdf.py"""
import os
import tempfile
import re
from pathlib import Path

import pytest


class TestRewriteImagePaths:
    """Unit tests for HTML path rewriting (no Chrome needed)."""

    def test_rewrites_relative_image_paths_to_file_urls(self):
        """./images/ Pfade werden zu file:/// Pfaden umgeschrieben."""
        from app.services.generate_pdf import _rewrite_html_for_pdf

        html = '<img src="./images/photo.jpg" alt="Foto"><img src="./images/map.png">'
        result = _rewrite_html_for_pdf(html, "/home/user/output/2026-05-04")

        assert 'src="file:///home/user/output/2026-05-04/images/photo.jpg"' in result
        assert 'src="file:///home/user/output/2026-05-04/images/map.png"' in result
        assert "./images/" not in result

    def test_rewrites_max_width_for_print(self):
        from app.services.generate_pdf import _rewrite_html_for_pdf

        html = '<style>body { max-width: 780px; }</style>'
        result = _rewrite_html_for_pdf(html, "/tmp")

        assert "max-width: 100%" in result
        assert "max-width: 780px" not in result

    def test_injects_print_page_css(self):
        from app.services.generate_pdf import _rewrite_html_for_pdf

        html = '<html><head></head><body>Hallo</body></html>'
        result = _rewrite_html_for_pdf(html, "/tmp")

        assert "@page { size: A4; margin: 15mm; }" in result

    def test_handles_none_html(self):
        from app.services.generate_pdf import _rewrite_html_for_pdf

        result = _rewrite_html_for_pdf(None, "/tmp")
        assert result is None

    def test_handles_empty_html(self):
        from app.services.generate_pdf import _rewrite_html_for_pdf

        result = _rewrite_html_for_pdf("", "/tmp")
        assert result == ""

    def test_output_dir_none_uses_cwd(self):
        from app.services.generate_pdf import _rewrite_html_for_pdf

        html = '<img src="./images/photo.jpg">'
        result = _rewrite_html_for_pdf(html, None)

        # Sollte file:/// mit CWD-Absolutpfad enthalten
        assert "file:///" in result
        assert "images/photo.jpg" in result
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_services/test_generate_pdf.py -v
```
Expected: All FAIL — `_rewrite_html_for_pdf` not defined.

- [ ] **Step 3: Create the service module with rewrite function**

Create `app/services/generate_pdf.py`:

```python
"""PDF-Generierung aus Artikel-HTML via Headless Chrome (Selenium CDP)."""
import base64
import os
import re
import tempfile
import time
from pathlib import Path
from typing import Optional

from selenium import webdriver
from selenium.webdriver.chrome.options import Options


def _rewrite_html_for_pdf(html_content: str | None, article_output_dir: str | None) -> str | None:
    """Bereitet HTML für die PDF-Generierung vor:
    - ./images/ Pfade zu absoluten file:/// Pfaden umschreiben
    - max-width: 780px auf max-width: 100% setzen
    - @page CSS für A4-Drucklayout injizieren
    """
    if not html_content:
        return html_content

    # Basisverzeichnis für Bildpfade
    if article_output_dir and os.path.isdir(article_output_dir):
        base_dir = os.path.abspath(article_output_dir)
    else:
        base_dir = os.path.abspath(".")

    # ./images/ → file:///... absolute Pfade
    html_content = re.sub(
        r'src="\./images/',
        f'src="file://{base_dir}/images/',
        html_content,
    )

    # max-width: 780px → 100% (Volle Breite für PDF)
    html_content = html_content.replace("max-width: 780px", "max-width: 100%")

    # @page CSS für A4-Druck injizieren
    print_css = """
    <style>
        @page {
            size: A4;
            margin: 15mm;
        }
        @media print {
            body {
                max-width: 100% !important;
            }
        }
    </style>"""

    if "</head>" in html_content:
        html_content = html_content.replace("</head>", f"{print_css}\n</head>")
    else:
        html_content = print_css + html_content

    return html_content


def generate_pdf(html_content: str, article_output_dir: str | None = None) -> bytes:
    """Wandelt Artikel-HTML via Headless Chrome in PDF um.

    Args:
        html_content: Vollständiges HTML des Artikels (mit ./images/ Pfaden)
        article_output_dir: Verzeichnis, das den Output-Ordner des Artikels enthält

    Returns:
        PDF als Bytes

    Raises:
        RuntimeError: Wenn Chrome nicht verfügbar ist oder die Generierung fehlschlägt
    """
    if not html_content:
        raise ValueError("Kein HTML-Inhalt für die PDF-Generierung")

    processed_html = _rewrite_html_for_pdf(html_content, article_output_dir)

    # Temporäre HTML-Datei schreiben
    fd, html_path = tempfile.mkstemp(suffix=".html")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(processed_html)

        options = Options()
        options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")

        driver = webdriver.Chrome(options=options)
        try:
            abs_path = os.path.abspath(html_path)
            driver.get(f"file:///{abs_path}")
            time.sleep(1)  # Warten bis Bilder geladen sind

            pdf_result = driver.execute_cdp_cmd("Page.printToPDF", {
                "printBackground": True,
                "paperWidth": 8.27,   # A4
                "paperHeight": 11.69,  # A4
                "marginTop": 0.59,     # 15mm in Zoll
                "marginBottom": 0.59,
                "marginLeft": 0.59,
                "marginRight": 0.59,
                "preferCSSPageSize": True,
            })

            pdf_bytes = base64.b64decode(pdf_result["data"])
            return pdf_bytes
        finally:
            driver.quit()
    finally:
        if os.path.exists(html_path):
            os.unlink(html_path)
```

- [ ] **Step 4: Run the unit tests to verify they pass**

```bash
uv run pytest tests/test_services/test_generate_pdf.py::TestRewriteImagePaths -v
```
Expected: All 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add app/services/generate_pdf.py tests/test_services/test_generate_pdf.py
git commit -m "feat: add PDF generation service using headless Chrome CDP"
```

---

### Task 2: State Model & API Request Model

**Files:**
- Modify: `app/state.py:39-43`
- Modify: `app/api/routes.py:146-156`
- Modify: `tests/test_state.py`

- [ ] **Step 1: Add `pdf_export` field to `OutputConfig`**

In `app/state.py`, change `OutputConfig` (line 39-43):

```python
class OutputConfig(BaseModel):
    """Konfiguration für die Blog-Ausgabe — vom Benutzer vor Pipeline-Start gesetzt."""
    wildcard_max: int = Field(default=12, ge=1, le=50)
    article_length: Literal["short", "normal", "detailed"] = "normal"
    style_persona: Literal["mountain_veteran", "field_reporter"] = "mountain_veteran"
    pdf_export: bool = False
```

- [ ] **Step 2: Add `pdf_export` field to `RunPipelineRequest`**

In `app/api/routes.py`, change `RunPipelineRequest` (line 146-156):

```python
class RunPipelineRequest(BaseModel):
    model: str
    output_dir: str = "output"
    notes: str = ""
    txt_file: str = ""
    gpx_file: str = ""
    image_files: list[str] = []
    wildcard_max: int = Field(default=12, ge=1, le=50)
    article_length: Literal["short", "normal", "detailed"] = "normal"
    style_persona: Literal["mountain_veteran", "field_reporter"] = "mountain_veteran"
    pdf_export: bool = False
```

- [ ] **Step 3: Write test for `OutputConfig.pdf_export` default**

In `tests/test_state.py`, add to class `TestAppStateEnrichment` (after line 53):

```python
class TestOutputConfig:
    def test_pdf_export_defaults_to_false(self):
        from app.state import OutputConfig
        config = OutputConfig()
        assert config.pdf_export is False

    def test_pdf_export_can_be_true(self):
        from app.state import OutputConfig
        config = OutputConfig(pdf_export=True)
        assert config.pdf_export is True
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_state.py::TestAppStateEnrichment tests/test_state.py::TestOutputConfig -v
```
Expected: 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add app/state.py app/api/routes.py tests/test_state.py
git commit -m "feat: add pdf_export field to OutputConfig and RunPipelineRequest"
```

---

### Task 3: API PDF Endpoint

**Files:**
- Modify: `app/api/routes.py` (add endpoint + import)
- Modify: `tests/test_api_endpoints.py`

- [ ] **Step 1: Add the PDF export endpoint**

In `app/api/routes.py`, add import at the top (after existing imports):

```python
import re
```

In `app/api/routes.py`, add the endpoint AFTER the `delete_articles_batch` function (after line 411):

```python
# ── PDF Export ─────────────────────────────────────────

@router.get("/articles/{article_id}/pdf")
async def export_article_pdf(article_id: int):
    """Generiert PDF für einen Artikel und liefert es als Download aus."""
    from app.services.generate_pdf import generate_pdf

    session = get_session()
    try:
        repo = ArticleRepository(session)
        article = repo.get_by_id(article_id)
        if article is None:
            raise HTTPException(status_code=404, detail="Artikel nicht gefunden")
        if not article.html_content:
            raise HTTPException(status_code=400, detail="Artikel hat keinen HTML-Inhalt")

        # Output-Verzeichnis aus html_path ableiten
        output_dir = str(Path(article.html_path).parent) if article.html_path else ""

        try:
            pdf_bytes = generate_pdf(article.html_content, output_dir)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"PDF-Generierung fehlgeschlagen: {e}")

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
    finally:
        session.close()
```

- [ ] **Step 2: Add test for the PDF endpoint**

In `tests/test_api_endpoints.py`, add a new class at the end of the file:

```python
class TestArticlePdf:
    def test_pdf_endpoint_returns_404_for_missing_article(self, client):
        response = client.get("/api/articles/99999/pdf")
        assert response.status_code == 404

    def test_pdf_endpoint_with_valid_article(self, monkeypatch):
        """Testet, dass der Endpunkt einen 200-Status und application/pdf liefert.
        Achtung: Mockt die PDF-Generierung, da Chrome im Test nicht verfügbar ist."""
        import os
        import tempfile
        from app.db import connection as conn_module
        from app.db.models import Base
        from app.db.repository import ArticleRepository
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session, sessionmaker as sm
        from unittest.mock import patch

        tmp = tempfile.mktemp(suffix=".db")
        try:
            engine = create_engine(f"sqlite:///{tmp}", echo=False)
            Base.metadata.create_all(engine)
            session = Session(engine)

            factory = sm(bind=engine)
            monkeypatch.setattr(conn_module, "_engine", engine)
            monkeypatch.setattr(conn_module, "_SessionLocal", factory)
            monkeypatch.setattr(conn_module, "get_session", factory)

            from app.api.server import create_app
            from fastapi.testclient import TestClient
            app = create_app()
            import app.api.routes as routes_mod
            monkeypatch.setattr(routes_mod, "get_session", factory)
            client = TestClient(app)

            repo = ArticleRepository(session)
            article_id = repo.insert(
                article_data={
                    "title": "PDF Test",
                    "markdown_content": "# PDF Test",
                    "html_content": "<h1>PDF Test</h1><p>Content</p>",
                    "markdown_path": "output/test/md.md",
                    "html_path": "output/test/html.html",
                },
                images=[],
            )
            session.commit()

            # Mock generate_pdf um Chrome-Aufruf zu vermeiden
            with patch("app.api.routes.generate_pdf", return_value=b"%PDF-1.4 mock") as mock_gen:
                response = client.get(f"/api/articles/{article_id}/pdf")
                assert response.status_code == 200
                assert response.headers["content-type"] == "application/pdf"
                assert "attachment" in response.headers["content-disposition"]
                assert response.content == b"%PDF-1.4 mock"
                mock_gen.assert_called_once()

            session.close()
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def test_pdf_endpoint_with_no_html_content(self, monkeypatch):
        import os
        import tempfile
        from app.db import connection as conn_module
        from app.db.models import Base
        from app.db.repository import ArticleRepository
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session, sessionmaker as sm

        tmp = tempfile.mktemp(suffix=".db")
        try:
            engine = create_engine(f"sqlite:///{tmp}", echo=False)
            Base.metadata.create_all(engine)
            session = Session(engine)

            factory = sm(bind=engine)
            monkeypatch.setattr(conn_module, "_engine", engine)
            monkeypatch.setattr(conn_module, "_SessionLocal", factory)
            monkeypatch.setattr(conn_module, "get_session", factory)

            from app.api.server import create_app
            from fastapi.testclient import TestClient
            app = create_app()
            import app.api.routes as routes_mod
            monkeypatch.setattr(routes_mod, "get_session", factory)
            client = TestClient(app)

            repo = ArticleRepository(session)
            article_id = repo.insert(
                article_data={"title": "No HTML", "markdown_path": "output/test/md.md"},
                images=[],
            )
            session.commit()

            response = client.get(f"/api/articles/{article_id}/pdf")
            assert response.status_code == 400

            session.close()
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
```

- [ ] **Step 3: Run tests**

```bash
uv run pytest tests/test_api_endpoints.py::TestArticlePdf -v
```
Expected: 3 tests PASS (404, 200 mit Mock, 400 ohne HTML).

- [ ] **Step 4: Commit**

```bash
git add app/api/routes.py tests/test_api_endpoints.py
git commit -m "feat: add GET /api/articles/{id}/pdf endpoint for PDF download"
```

---

### Task 4: Pipeline Graph Integration

**Files:**
- Create: `app/nodes/generate_pdf.py`
- Modify: `app/graph.py`
- Modify: `app/api/events.py:31-37`
- Modify: `app/api/routes.py:215-295`

- [ ] **Step 1: Create the pipeline node**

Create `app/nodes/generate_pdf.py`:

```python
"""Pipeline-Node zur PDF-Generierung aus dem fertigen Blogpost."""
from app.state import AppState
from app.services.generate_pdf import generate_pdf


def generate_pdf_node(state: AppState) -> AppState:
    """Generiert ein PDF aus dem generierten HTML-Blogpost (nur wenn pdf_export=True)."""
    print("📄 Generating PDF from blogpost...")

    if not state.blog_post or not state.blog_post.get("html"):
        print("⚠️ No HTML content available for PDF generation.")
        return state

    html_content = state.blog_post["html"]
    file_paths = state.blog_post.get("file_paths", {})
    html_path = file_paths.get("html", "")

    # Output-Verzeichnis aus html_path ableiten
    if html_path:
        import os
        from pathlib import Path
        output_dir = str(Path(html_path).parent)
    else:
        output_dir = "."

    try:
        pdf_bytes = generate_pdf(html_content, output_dir)
        state.blog_post["pdf_bytes"] = pdf_bytes
        print(f"✅ PDF generated ({len(pdf_bytes)} bytes)")
    except Exception as e:
        print(f"❌ PDF generation failed: {e}")
        state.blog_post["pdf_error"] = str(e)

    return state
```

- [ ] **Step 2: Update events.py to pass article_id and pdf_available**

In `app/api/events.py`, change `complete_run` (line 31-37):

```python
def complete_run(self, run_id: str, status: str, output_dir: str = "",
                 article_id: int = None, pdf_available: bool = False):
    """Signal pipeline completion and store the result."""
    queue = self._runs.get(run_id)
    if queue is None or self._loop is None:
        return
    event = {"stage": "__done__", "status": status, "output_dir": output_dir}
    if article_id is not None:
        event["article_id"] = article_id
    event["pdf_available"] = pdf_available
    self._loop.call_soon_threadsafe(queue.put_nowait, event)
```

- [ ] **Step 3: Update graph.py with conditional edge for generate_pdf**

In `app/graph.py`, add import:

```python
from langgraph.graph import END, StateGraph
```

Change `from langgraph.graph import StateGraph` to `from langgraph.graph import StateGraph, END`.

After the import section, add the node name entry (after line 34):

```python
    "generate_pdf": "PDF generieren",
```

After the `persist_article` node wrapping (after line 103), add:

```python
    gpn = _wrap_node(generate_pdf_node, "generate_pdf", event_emitter) if event_emitter else generate_pdf_node
```

Add the node (after line 117):

```python
    builder.add_node("generate_pdf", gpn)
```

Add conditional routing function before `build_graph` (after line 83) or inline, and the conditional edge + final edge (replace line 132-134):

```python
    def _should_generate_pdf(state: AppState) -> str:
        if state.output_config.pdf_export:
            return "generate_pdf"
        return END

    builder.add_conditional_edges(
        "persist_article",
        _should_generate_pdf,
        {"generate_pdf": "generate_pdf", END: END},
    )
    builder.add_edge("generate_pdf", END)
```

Note: Remove `builder.set_finish_point("persist_article")` since we now use conditional edges.

Full context of changes in `graph.py`:

Line 1: `from langgraph.graph import StateGraph, END`

After line 34, add: `"generate_pdf": "PDF generieren",`

After existing import for persist_article (line 16), add import:
```python
from app.nodes.generate_pdf import generate_pdf_node
```

After line 103 (wrapping persist_article_node), add:
```python
    gpn = _wrap_node(generate_pdf_node, "generate_pdf", event_emitter) if event_emitter else generate_pdf_node
```

After line 117 (builder.add_node("persist_article", pan)), add:
```python
    builder.add_node("generate_pdf", gpn)
```

Replace lines 132-134 (`builder.set_finish_point("persist_article")`) with:
```python
    def _should_generate_pdf(state: AppState) -> str:
        if state.output_config.pdf_export:
            return "generate_pdf"
        return END

    builder.add_conditional_edges(
        "persist_article",
        _should_generate_pdf,
        {"generate_pdf": "generate_pdf", END: END},
    )
    builder.add_edge("generate_pdf", END)
```

- [ ] **Step 4: Update background pipeline runner**

In `app/api/routes.py`, update `_run_pipeline_in_background` signature and `OutputConfig` instantiation (lines 254-258):

```python
        state = AppState(
            gpx_file=gpx_file,
            model=model,
            notes=combined_notes,
            output_config=OutputConfig(
                wildcard_max=body.wildcard_max,
                article_length=body.article_length,
                style_persona=body.style_persona,
                pdf_export=body.pdf_export,
            ),
        )
```

After the graph invoke, update `complete_run` call (replace line 286):

```python
        # Extract article_id and pdf_available from result
        article_id = None
        pdf_available = False
        if hasattr(result, "metadata"):
            article_id = result.metadata.get("article_id")
        if blog_post and isinstance(blog_post, dict) and "pdf_bytes" in blog_post:
            pdf_available = True

        event_manager.complete_run(
            run_id, "success", output_path,
            article_id=article_id,
            pdf_available=pdf_available,
        )
```

- [ ] **Step 5: Run existing tests to verify no regressions**

```bash
uv run pytest tests/ -v --ignore=tests/test_services/test_generate_pdf.py --ignore=tests/test_api_endpoints.py -x
```
Expected: All tests PASS.

- [ ] **Step 6: Run all tests**

```bash
uv run pytest tests/ -v -x
```
Expected: All tests PASS.

- [ ] **Step 7: Commit**

```bash
git add app/nodes/generate_pdf.py app/graph.py app/api/events.py app/api/routes.py
git commit -m "feat: integrate PDF generation node into LangGraph pipeline"
```

---

### Task 5: Frontend — Store & Checkbox Component

**Files:**
- Modify: `frontend/src/lib/stores/pipeline.ts`
- Create: `frontend/src/lib/PdfExportCheckbox.svelte`
- Modify: `frontend/src/App.svelte`

- [ ] **Step 1: Add `pdfExport` store**

In `frontend/src/lib/stores/pipeline.ts`, after line 46 (`export const stylePersona = writable<string>("mountain_veteran");`):

```typescript
export const pdfExport = writable<boolean>(false);
```

- [ ] **Step 2: Create `PdfExportCheckbox.svelte`**

Create `frontend/src/lib/PdfExportCheckbox.svelte`:

```svelte
<svelte:options runes />

<script lang="ts">
  import { pdfExport } from "./stores/pipeline";

  let checked: boolean = $state(false);

  $effect(() => {
    pdfExport.set(checked);
  });
</script>

<label class="pdf-toggle">
  <input type="checkbox" bind:checked />
  <span>Als PDF exportieren</span>
</label>

<style>
  .pdf-toggle {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.8rem;
    color: var(--text);
    cursor: pointer;
    padding: 0.25rem 0;
  }
  .pdf-toggle input[type="checkbox"] {
    width: 16px;
    height: 16px;
    accent-color: var(--accent);
    cursor: pointer;
  }
</style>
```

- [ ] **Step 3: Add `PdfExportCheckbox` to `App.svelte` sidebar**

In `frontend/src/App.svelte`, add import (after line 13):

```svelte
  import PdfExportCheckbox from "./lib/PdfExportCheckbox.svelte";
```

In the sidebar section, after `StyleSelector` (line 48) and before the `run-section` div (line 50):

```svelte
      <PdfExportCheckbox />
```

- [ ] **Step 4: Verify TypeScript compiles**

```bash
cd frontend && npm run check 2>&1 | head -20
```
Expected: No errors related to new code.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/stores/pipeline.ts frontend/src/lib/PdfExportCheckbox.svelte frontend/src/App.svelte
git commit -m "feat: add PDF export checkbox to pipeline sidebar"
```

---

### Task 6: Frontend — RunButton SSE Auto-Download

**Files:**
- Modify: `frontend/src/lib/RunButton.svelte`

- [ ] **Step 1: Add `pdf_export` to POST body and SSE auto-download**

In `frontend/src/lib/RunButton.svelte`, add import (after existing imports):

```typescript
  import { pdfExport } from "./stores/pipeline";
```

In the `body` of the POST request (around line 40), add `pdf_export`:

```typescript
        body: JSON.stringify({
          model,
          output_dir: dir,
          notes,
          txt_file: txtFile || "",
          gpx_file: gpxFile,
          image_files: imageFiles,
          wildcard_max: wc,
          article_length: length,
          style_persona: persona,
          pdf_export: get(pdfExport),
        }),
```

Also add `pdfExport` to the destructured `get()` calls at line 19-26:

```typescript
  async function handleRun() {
    const model = get(selectedModel);
    const { gpxFile, imageFiles, txtFile } = get(pipelineFiles);
    const dir = get(outputDir);
    const notes = get(notesField);
    const wc = get(wildcardCount);
    const length = get(articleLength);
    const persona = get(stylePersona);
    const pdf = get(pdfExport);
```

And use `pdf` in the body:
```typescript
          pdf_export: pdf,
```

**Now add auto-download logic in the SSE `done` event handler.** The `done` event listener is defined in `pipeline.ts` `startStream` function (lines 79-93). We need to modify that function.

In `frontend/src/lib/stores/pipeline.ts`, in the `startStream` function, update the `done` event listener (lines 79-93):

```typescript
  eventSource.addEventListener("done", async (e: MessageEvent) => {
    eventSource?.close();
    const data = JSON.parse(e.data);
    const isSuccess = data.status === "success";
    addLine("__done__", data.status, `Pipeline ${isSuccess ? "erfolgreich" : "fehlgeschlagen"}.`);
    runState.set(isSuccess ? "done" : "failed");

    // Auto-download PDF if available
    if (data.pdf_available && data.article_id) {
      window.open(`/api/articles/${data.article_id}/pdf`, "_blank");
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

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd frontend && npm run check 2>&1 | head -20
```
Expected: No errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/RunButton.svelte frontend/src/lib/stores/pipeline.ts
git commit -m "feat: auto-download PDF after pipeline completion when pdf_export checked"
```

---

### Task 7: Frontend — ArticleDetail PDF Button

**Files:**
- Modify: `frontend/src/lib/ArticleDetail.svelte`

- [ ] **Step 1: Add green PDF button and toolbar refactor**

In `frontend/src/lib/ArticleDetail.svelte`, add the `handlePdfExport` function (after `handleDelete`, after line 61):

```typescript
  function handlePdfExport() {
    window.open(`/api/articles/${id}/pdf`, "_blank");
  }
```

Replace the toolbar section (lines 80-90) with:

```svelte
<div class="toolbar">
  <button class="back-btn" onclick={() => navigateTo({ page: "articles" })}>
    ← Zurück zur Liste
  </button>
  {#if article}
    <div class="toolbar-right">
      <button class="pdf-btn" onclick={handlePdfExport}>Als PDF exportieren</button>
      <button class="delete-btn" onclick={handleDelete} disabled={deleting}>
        {deleting ? "Lösche..." : "🗑 Löschen"}
      </button>
    </div>
  {/if}
</div>
```

Replace the CSS `.toolbar` rule (lines 139-143) and `delete-btn` (lines 155-162) + add new styles after them:

```css
  .toolbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1rem;
  }
  .toolbar-right {
    display: flex;
    gap: 0.5rem;
  }
  .back-btn, .delete-btn, .pdf-btn {
    padding: 0.4rem 0.75rem;
    font-size: 0.8rem;
  }
  .back-btn {
    background: var(--surface-alt);
    color: var(--text);
  }
  .back-btn:hover {
    background: var(--accent);
  }
  .pdf-btn {
    background: #27ae60;
    color: white;
  }
  .pdf-btn:hover {
    background: #219a52;
  }
  .delete-btn {
    background: var(--error);
    color: white;
  }
  .delete-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd frontend && npm run check 2>&1 | head -20
```
Expected: No errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/ArticleDetail.svelte
git commit -m "feat: add green PDF export button to article detail view"
```

---

### Task 8: Final Verification

- [ ] **Step 1: Run all backend tests**

```bash
uv run pytest tests/ -v
```
Expected: All tests PASS.

- [ ] **Step 2: Run TypeScript check**

```bash
cd frontend && npm run check
```
Expected: No errors.

- [ ] **Step 3: Verify `pyproject.toml` has no new dependencies**

```bash
uv pip list --format=freeze | grep -E "weasyprint|playwright|pdfkit|wkhtmltopdf"
```
Expected: No matches — no new dependencies.

- [ ] **Step 4: Commit final verification**

```bash
git add -A
git commit -m "chore: final verification — all tests pass, no new dependencies"
```
