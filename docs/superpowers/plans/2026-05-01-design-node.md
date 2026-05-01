# Design Node Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an LLM-driven CSS design node that wraps raw blog HTML into a styled, self-contained HTML document — independently removable, with zero impact on the rest of the pipeline.

**Architecture:** A new service (`design_blogpost.py`) sends the raw HTML body to Ollama with a design prompt, gets back a complete styled HTML document. A thin node (`design_blogpost_node`) plugs between `generate_blog_post` and `persist_article` in the LangGraph pipeline. Best-effort — failures leave original HTML intact.

**Tech Stack:** Python, LangGraph, Ollama `/api/chat` (text-only, no images), Pydantic (AppState)

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `app/services/design_blogpost.py` | Create | Build prompt, call Ollama, return styled HTML or None |
| `app/nodes/design_blogpost.py` | Create | Thin node: AppState → AppState, guard clauses, call service |
| `app/graph.py` | Modify | Register node + add edge between generate_blog_post and persist_article |
| `tests/test_services/test_design_blogpost.py` | Create | Unit tests for service: prompt construction, response handling, error cases |
| `tests/test_nodes/test_design_blogpost.py` | Create | Unit tests for node: guard clauses, state mutation, service mocking |

---

### Task 1: Create the design service with prompt construction and Ollama call

**Files:**
- Create: `app/services/design_blogpost.py`
- Create: `tests/test_services/test_design_blogpost.py`

- [ ] **Step 1: Write the failing tests for service**

```python
"""Tests for app/services/design_blogpost.py"""
import json
from unittest.mock import patch, Mock

import pytest

from app.services.design_blogpost import (
    design_blogpost_service,
    _build_design_prompt,
    _call_ollama_text,
    _extract_styled_html,
)


class TestBuildDesignPrompt:
    def test_includes_role_and_constraints(self):
        html_body = "<h1>Test Title</h1><p>Some content</p>"
        prompt = _build_design_prompt(html_body)

        assert "Web-Designer" in prompt
        assert "Reiseblogs" in prompt
        assert "NICHT verändert" in prompt
        assert "<style>" in prompt
        assert "kein JavaScript" in prompt
        assert "---CONTENT---" in prompt
        assert "<h1>Test Title</h1>" in prompt

    def test_appends_content_after_delimiter(self):
        html_body = "<p>Hello world</p>"
        prompt = _build_design_prompt(html_body)

        parts = prompt.split("---CONTENT---")
        assert len(parts) == 2
        assert parts[1].strip() == "<p>Hello world</p>"


class TestCallOllamaText:
    def test_returns_content_on_success(self):
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "message": {"content": "<html><head><style>body{}</style></head><body><h1>Hi</h1></body></html>"},
        }

        with patch("app.services.design_blogpost.requests.post", return_value=mock_resp):
            result = _call_ollama_text(
                prompt="Make it pretty",
                model="gemma4:26b-ctx128k",
            )
        assert result is not None
        assert "<html>" in result
        assert "<style>" in result

    def test_returns_none_on_connection_error(self):
        with patch("app.services.design_blogpost.requests.post",
                   side_effect=Exception("Connection refused")):
            result = _call_ollama_text(
                prompt="Make it pretty",
                model="gemma4:26b-ctx128k",
            )
        assert result is None

    def test_returns_none_on_non_200(self):
        mock_resp = Mock()
        mock_resp.status_code = 500
        mock_resp.text = "Internal server error"

        with patch("app.services.design_blogpost.requests.post", return_value=mock_resp):
            result = _call_ollama_text(
                prompt="Make it pretty",
                model="gemma4:26b-ctx128k",
            )
        assert result is None


class TestExtractStyledHtml:
    def test_passes_through_valid_html_with_style(self):
        html = "<!DOCTYPE html><html><head><style>body{color:red}</style></head><body><h1>Hi</h1></body></html>"
        result = _extract_styled_html(html)
        assert result == html

    def test_returns_none_for_empty_string(self):
        assert _extract_styled_html("") is None

    def test_returns_none_for_too_short_response(self):
        assert _extract_styled_html("short") is None

    def test_returns_none_if_no_style_tag(self):
        html = "<html><body><h1>No CSS</h1></body></html>"
        result = _extract_styled_html(html)
        assert result is None


class TestDesignBlogpostServiceIntegration:
    def test_returns_styled_html(self):
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "message": {
                "content": (
                    "<!DOCTYPE html>\n<html>\n<head>\n"
                    "<meta charset='utf-8'>\n"
                    "<style>body{font-family:serif;max-width:800px}</style>\n"
                    "</head>\n<body>\n<h1>Test</h1>\n<p>Content</p>\n</body>\n</html>"
                ),
            },
        }

        with patch("app.services.design_blogpost.requests.post", return_value=mock_resp):
            result = design_blogpost_service(
                html_body="<h1>Test</h1><p>Content</p>",
                model="gemma4:26b-ctx128k",
            )
        assert result is not None
        assert "<style>" in result
        assert "font-family" in result
        assert "<h1>Test</h1>" in result

    def test_returns_none_when_ollama_fails(self):
        with patch("app.services.design_blogpost.requests.post",
                   side_effect=Exception("Connection refused")):
            result = design_blogpost_service(
                html_body="<h1>Test</h1>",
                model="gemma4:26b-ctx128k",
            )
        assert result is None

    def test_returns_none_when_response_lacks_style(self):
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "message": {"content": "<h1>Just content, no CSS</h1>"},
        }

        with patch("app.services.design_blogpost.requests.post", return_value=mock_resp):
            result = design_blogpost_service(
                html_body="<h1>Test</h1>",
                model="gemma4:26b-ctx128k",
            )
        assert result is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_services/test_design_blogpost.py -v
```
Expected: All tests FAIL with `ImportError` or `ModuleNotFoundError`

- [ ] **Step 3: Write the service implementation**

```python
# app/services/design_blogpost.py
"""
Design Blogpost Service

Nimmt das rohe HTML-Fragment aus der Blog-Generierung und lässt es von
einem Ollama-Modell in ein vollständiges, gestyltes HTML-Dokument einbetten.
Rein textueller Call — keine Bilder.
"""

from typing import Optional


def _build_design_prompt(html_body: str) -> str:
    """Baut den Prompt für das Design-Modell."""
    return f"""Du bist ein Web-Designer, spezialisiert auf lesbare, elegante Reiseblogs.

Deine Aufgabe: Bette den folgenden HTML-Inhalt in ein vollständiges,
self-contained HTML-Dokument ein.

STRENGE REGELN:
1. Der übergebene HTML-Inhalt darf NICHT verändert, umformuliert, gekürzt
   oder ergänzt werden. Füge NUR die umschließende HTML-Struktur und CSS hinzu.
2. Alle CSS-Regeln gehören in EINEN <style>-Block im <head>.
3. Keine externen Ressourcen, keine CDN-Links, kein JavaScript.
4. Das Dokument muss valides, vollständiges HTML5 sein.
5. Gib NUR das HTML zurück — keine Erklärungen, keine Markdown-Fences.

DESIGN-RICHTUNG:
- Lesbare, gut proportionierte Typographie (serif oder sans-serif)
- Harmonische, naturverbundene Farbpalette (Erdtöne, Waldgrün, warmes Grau)
- Zentriertes Layout mit max-width (700–900px) und ausreichend Padding
- Responsive Bilder: img {{ max-width: 100%; height: auto; }}
- Angenehme Zeilenabstände (line-height: 1.6–1.8)
- Klare visuelle Hierarchie: h1, h2, h3 deutlich unterscheidbar
- Subtile Akzente: dezente Trennlinien, Blockquote-Styling

---CONTENT---
{html_body}"""


def _call_ollama_text(
    prompt: str,
    model: str = "gemma4:26b-ctx128k",
    base_url: str = "http://localhost:11434",
) -> Optional[str]:
    """Ruft Ollama /api/chat für reinen Text auf (keine Bilder).

    Returns:
        Antwort-String oder None bei Fehler.
    """
    try:
        import requests

        url = f"{base_url}/api/chat"

        payload = {
            "model": model,
            "messages": [
                {"role": "user", "content": prompt},
            ],
            "stream": False,
            "options": {
                "temperature": 0.7,
                "top_p": 0.9,
                "num_predict": 4096,
            },
        }

        response = requests.post(url, json=payload, timeout=60)

        if response.status_code == 200:
            result = response.json()
            return result.get("message", {}).get("content", "")
        else:
            print(f"❌ Design Ollama API Error: {response.status_code}")
            print(f"Response: {response.text[:500]}")
            return None

    except requests.exceptions.ConnectionError:
        print("❌ Design: Could not connect to Ollama. Is it running? (ollama serve)")
        return None
    except Exception as e:
        print(f"❌ Design: Error calling Ollama: {e}")
        return None


def _extract_styled_html(response: str) -> Optional[str]:
    """Validiert die LLM-Antwort.

    Gibt die Antwort nur zurück, wenn sie ein vollständiges HTML-Dokument
    mit <style>-Tag enthält. Sonst None.
    """
    if not response or len(response.strip()) < 100:
        print("⚠️  Design: Response zu kurz (< 100 Zeichen)")
        return None

    stripped = response.strip()

    if "<style>" not in stripped and "<style " not in stripped:
        print("⚠️  Design: Kein <style>-Tag in der Antwort gefunden")
        return None

    return stripped


def design_blogpost_service(
    html_body: str,
    model: str = "gemma4:26b-ctx128k",
) -> Optional[str]:
    """Nimmt rohes HTML-Body-Fragment und gibt gestyltes HTML-Dokument zurück.

    Args:
        html_body: Das rohe HTML-Fragment (h1, p, img, ...)
        model: Ollama-Modell-Name

    Returns:
        Vollständiges HTML-Dokument mit inline CSS, oder None bei Fehler.
        Bei None bleibt das Original-HTML erhalten.
    """
    if not html_body or not html_body.strip():
        print("⚠️  Design: Kein HTML-Body zum Stylen vorhanden")
        return None

    prompt = _build_design_prompt(html_body)
    response = _call_ollama_text(prompt, model=model)

    if response is None:
        print("⚠️  Design: Keine Antwort von Ollama — Original-HTML bleibt erhalten")
        return None

    return _extract_styled_html(response)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_services/test_design_blogpost.py -v
```
Expected: All tests PASS

- [ ] **Step 5: Commit service**

```bash
git add app/services/design_blogpost.py tests/test_services/test_design_blogpost.py
git commit -m "feat: add design_blogpost service for LLM-driven CSS styling"
```

---

### Task 2: Create the design blogpost node

**Files:**
- Create: `app/nodes/design_blogpost.py`
- Create: `tests/test_nodes/test_design_blogpost.py`

- [ ] **Step 1: Write the failing tests for node**

```python
"""Tests for app/nodes/design_blogpost.py"""
import os
import tempfile
from unittest.mock import patch

from app.nodes.design_blogpost import design_blogpost_node
from app.state import AppState


class TestDesignBlogpostNode:
    def test_returns_unchanged_when_no_blog_post(self):
        state = AppState()
        result = design_blogpost_node(state)
        assert result.blog_post is None

    def test_returns_unchanged_when_blog_post_not_successful(self):
        state = AppState(blog_post={"success": False, "html": "<h1>X</h1>"})
        result = design_blogpost_node(state)
        assert result.blog_post["html"] == "<h1>X</h1>"

    def test_returns_unchanged_when_html_empty(self):
        state = AppState(blog_post={"success": True, "html": ""})
        result = design_blogpost_node(state)
        assert result.blog_post["html"] == ""

    def test_updates_html_when_service_succeeds(self):
        state = AppState(blog_post={
            "success": True,
            "html": "<h1>Old</h1>",
            "markdown": "# Old",
            "file_paths": {},
        })
        styled = "<html><head><style>body{}</style></head><body><h1>Old</h1></body></html>"
        with patch("app.nodes.design_blogpost.design_blogpost_service",
                   return_value=styled):
            result = design_blogpost_node(state)
        assert result.blog_post["html"] == styled
        assert result.blog_post["markdown"] == "# Old"

    def test_keeps_original_html_when_service_fails(self):
        state = AppState(blog_post={
            "success": True,
            "html": "<h1>Old</h1>",
            "markdown": "# Old",
        })
        with patch("app.nodes.design_blogpost.design_blogpost_service",
                   return_value=None):
            result = design_blogpost_node(state)
        assert result.blog_post["html"] == "<h1>Old</h1>"

    def test_overwrites_html_file_when_service_succeeds(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            html_path = os.path.join(tmpdir, "test.html")
            with open(html_path, "w") as f:
                f.write("<h1>Old</h1>")

            state = AppState(blog_post={
                "success": True,
                "html": "<h1>Old</h1>",
                "markdown": "# Old",
                "file_paths": {"html": html_path, "markdown": "/tmp/nonexistent.md"},
            })
            styled = "<html><head><style>body{}</style></head><body><h1>Old</h1></body></html>"
            with patch("app.nodes.design_blogpost.design_blogpost_service",
                       return_value=styled):
                design_blogpost_node(state)

            with open(html_path, "r") as f:
                content = f.read()
            assert content == styled
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_nodes/test_design_blogpost.py -v
```
Expected: All tests FAIL with `ImportError` or `ModuleNotFoundError`

- [ ] **Step 3: Write the node implementation**

```python
# app/nodes/design_blogpost.py
from app.state import AppState
from app.services.design_blogpost import design_blogpost_service


def design_blogpost_node(state: AppState) -> AppState:
    """Wendet LLM-gesteuertes CSS-Styling auf das Blog-HTML an.

    Liest state.blog_post["html"], sendet es an Ollama zur Gestaltung,
    überschreibt state.blog_post["html"] und die .html-Datei mit dem
    gestylten Ergebnis.

    Best-Effort: Bei Fehlern bleibt das Original-HTML erhalten.
    """
    print("🎨 Applying design styling to blog HTML...")

    if not state.blog_post or not state.blog_post.get("success"):
        print("⚠️  Design: Kein erfolgreicher Blog-Post — überspringe")
        return state

    html = state.blog_post.get("html", "")
    if not html:
        print("⚠️  Design: Kein HTML-Inhalt — überspringe")
        return state

    styled = design_blogpost_service(html, model=state.model)

    if styled:
        state.blog_post["html"] = styled
        print("✅ Design styling applied successfully")

        html_path = state.blog_post.get("file_paths", {}).get("html")
        if html_path:
            try:
                with open(html_path, "w", encoding="utf-8") as f:
                    f.write(styled)
                print(f"💾 Styled HTML written to: {html_path}")
            except Exception as e:
                print(f"⚠️  Design: Could not write styled HTML file: {e}")
    else:
        print("⚠️  Design: Styling failed — Original-HTML bleibt erhalten")

    return state
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_nodes/test_design_blogpost.py -v
```
Expected: All tests PASS

- [ ] **Step 5: Commit node**

```bash
git add app/nodes/design_blogpost.py tests/test_nodes/test_design_blogpost.py
git commit -m "feat: add design_blogpost node with guard clauses and file writing"
```

---

### Task 3: Wire the design node into the graph

**Files:**
- Modify: `app/graph.py`

- [ ] **Step 1: Add import and node registration**

Add the import at the top of `app/graph.py` (after the existing `design_blogpost` import line is not yet there — insert it alphabetically with the other node imports):

The import block in `app/graph.py` currently ends at line 15. Insert the new import between `generate_blogpost` and `enrich_weather`:

```python
from app.nodes.design_blogpost import design_blogpost_node
```

Add a node name entry to `NODE_NAMES`:

```python
    "design_blogpost": "Design anwenden",
```

Add the node function variable (after `gbp` on line 94):

```python
    dsn = _wrap_node(design_blogpost_node, "design_blogpost", event_emitter) if event_emitter else design_blogpost_node
```

Add the node to the builder (after `generate_blog_post` on line 109):

```python
    builder.add_node("design_blogpost", dsn)
```

Change the edge from `generate_blog_post → persist_article` to route through `design_blogpost`:

Replace line 127:
```python
    builder.add_edge("generate_blog_post", "design_blogpost")
    builder.add_edge("design_blogpost", "persist_article")
```

The final `build_graph` function should look like this (only showing the changed sections):

```python
def build_graph(event_emitter: Optional[EventEmitter] = None) -> StateGraph[AppState]:
    builder = StateGraph(AppState)

    # Wähle Node-Funktionen (ggf. mit Event-Wrapper)
    pgn = _wrap_node(process_gpx_node, "process_gpx", event_emitter) if event_emitter else process_gpx_node
    lin = _wrap_node(load_images_node, "load_images", event_emitter) if event_emitter else load_images_node
    emn = _wrap_node(metadata_node, "extract_metadata", event_emitter) if event_emitter else metadata_node
    cin = _wrap_node(clustering_image_node, "clustering_images", event_emitter) if event_emitter else clustering_image_node
    gmi = _wrap_node(generate_map_image_node, "generate_map_image", event_emitter) if event_emitter else generate_map_image_node
    ltn = _wrap_node(load_tour_notes_node, "load_tour_notes", event_emitter) if event_emitter else load_tour_notes_node
    sin = _wrap_node(select_images_node, "select_images", event_emitter) if event_emitter else select_images_node
    gbp = _wrap_node(generate_blog_post_node, "generate_blog_post", event_emitter) if event_emitter else generate_blog_post_node
    dsn = _wrap_node(design_blogpost_node, "design_blogpost", event_emitter) if event_emitter else design_blogpost_node

    # Enrichment nodes
    ewn = _wrap_node(enrich_weather_node, "enrich_weather", event_emitter) if event_emitter else enrich_weather_node
    epn = _wrap_node(enrich_poi_node, "enrich_poi", event_emitter) if event_emitter else enrich_poi_node
    rcn = _wrap_node(review_content_node, "review_content", event_emitter) if event_emitter else review_content_node
    pan = _wrap_node(persist_article_node, "persist_article", event_emitter) if event_emitter else persist_article_node

    builder.add_node("process_gpx", pgn)
    builder.add_node("load_images", lin)
    builder.add_node("extract_metadata", emn)
    builder.add_node("generate_map_image", gmi)
    builder.add_node("clustering_images", cin)
    builder.add_node("load_tour_notes", ltn)
    builder.add_node("select_images", sin)
    builder.add_node("generate_blog_post", gbp)
    builder.add_node("design_blogpost", dsn)
    builder.add_node("enrich_weather", ewn)
    builder.add_node("enrich_poi", epn)
    builder.add_node("review_content", rcn)
    builder.add_node("persist_article", pan)

    builder.set_entry_point("process_gpx")

    builder.add_edge("process_gpx", "load_images")
    builder.add_edge("load_images", "extract_metadata")
    builder.add_edge("extract_metadata", "clustering_images")
    builder.add_edge("clustering_images", "generate_map_image")
    builder.add_edge("generate_map_image", "load_tour_notes")
    builder.add_edge("load_tour_notes", "enrich_weather")
    builder.add_edge("enrich_weather", "enrich_poi")
    builder.add_edge("enrich_poi", "select_images")
    builder.add_edge("select_images", "review_content")
    builder.add_edge("review_content", "generate_blog_post")
    builder.add_edge("generate_blog_post", "design_blogpost")
    builder.add_edge("design_blogpost", "persist_article")

    builder.set_finish_point("persist_article")

    return builder.compile()
```

- [ ] **Step 2: Run existing tests to verify no regressions**

```bash
uv run pytest tests/ -v --ignore=tests/test_api --ignore=tests/test_api_endpoints.py -k "not test_pipeline_e2e"
```
Expected: All tests PASS (e2e test skipped since it requires real Ollama/GPX data)

- [ ] **Step 3: Run the new design tests to verify integration**

```bash
uv run pytest tests/test_services/test_design_blogpost.py tests/test_nodes/test_design_blogpost.py -v
```
Expected: All tests PASS

- [ ] **Step 4: Commit graph wiring**

```bash
git add app/graph.py
git commit -m "feat: wire design_blogpost node into pipeline graph"
```
