# Multimodale Photopuch-Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Pass 1 (plan.py) and Pass 2 (generate.py) multimodal so the LLM sees images and generates meaningful layouts, captions, and page titles.

**Architecture:** Add `encode_image_base64()` to shared utility. Both plan.py and generate.py encode all photobook images as base64 and send them via Ollama's `"images"` array. Add `title` slot to all 8 templates with CSS styling and renderer support.

**Tech Stack:** Python 3.12+, Pillow, Pydantic, pytest, Ollama multimodal API

---

### Task 1: Add encode_image_base64 to shared utility

**Files:**
- Modify: `app/utils/image_utils.py`
- Modify: `tests/test_utils/test_image_utils.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_utils/test_image_utils.py`:

```python
    @pytest.mark.unit
    def test_encode_image_base64_returns_base64_string(self, tmp_path):
        """encode_image_base64 muss einen validen Base64-String zurückgeben."""
        from app.utils.image_utils import encode_image_base64
        src = str(tmp_path / "src.jpg")
        img = Image.new("RGB", (1200, 800), color="blue")
        img.save(src)

        result = encode_image_base64(src, max_size=600)
        assert result is not None
        assert isinstance(result, str)
        # Base64-Strings sind nur alphanumerisch + / + = 
        import re
        assert re.match(r'^[A-Za-z0-9+/]+=*$', result) is not None

    @pytest.mark.unit
    def test_encode_image_base64_returns_none_for_missing_file(self):
        """Nonexistente Datei gibt None zurück."""
        from app.utils.image_utils import encode_image_base64
        result = encode_image_base64("/nonexistent/img.jpg")
        assert result is None
```

Run: `uv run pytest tests/test_utils/test_image_utils.py::TestCompressImageToJpeg::test_encode_image_base64_returns_base64_string -v`
Expected: FAIL (ImportError — function not defined)

- [ ] **Step 2: Implement encode_image_base64 in app/utils/image_utils.py**

Add this function to `app/utils/image_utils.py`:

```python
def encode_image_base64(image_path: str, max_size: int = 600) -> str | None:
    """Encodiert ein Bild als Base64-String für multimodale LLM-Requests.

    Thumbnail auf max_size, JPEG-Qualität 60, RGB-Konvertierung.
    """
    try:
        from PIL import Image

        if not os.path.exists(image_path):
            return None

        with Image.open(image_path) as img:
            if max(img.size) > max_size:
                img.thumbnail((max_size, max_size))
            import io as _io
            import base64 as _b64
            buf = _io.BytesIO()
            img.convert("RGB").save(buf, format="JPEG", quality=60)
            return _b64.b64encode(buf.getvalue()).decode("utf-8")
    except Exception as e:
        print(f"⚠️ Error encoding image {image_path}: {e}")
        return None
```

Run tests: both new tests must PASS.

- [ ] **Step 3: Commit**

```bash
git add app/utils/image_utils.py tests/test_utils/test_image_utils.py
git commit -m "feat: add encode_image_base64 to shared utility for multimodal LLM requests"
```

---

### Task 2: Pass 1 (plan.py) multimodal

**Files:**
- Modify: `app/photobook/plan.py`
- Modify: `tests/test_photobook/test_plan.py`

- [ ] **Step 1: Update plan.py to send images as base64**

Read `app/photobook/plan.py`. The function `plan_photobook_layout()` at lines 77-104 sends a text-only request. Change to:

Add import at top:
```python
from app.utils.image_utils import encode_image_base64
```

In `plan_photobook_layout()`, after the prompt is built (line 88), encode images and send in multimodal format. Replace the request block (lines 88-101) with:

```python
    prompt = _build_plan_prompt(len(images), gpx_stats, notes, weather, len(poi_list))
    
    # Bilder als Base64 encodieren
    encoded_images = []
    for img in images:
        b64 = encode_image_base64(img.path)
        if b64:
            encoded_images.append(b64)
    
    try:
        payload = {
            "model": model,
            "messages": [{
                "role": "user",
                "content": prompt,
                "images": encoded_images,
            }],
            "stream": False,
            "options": {"temperature": 0.3, "num_predict": 4096},
            "keep_alive": "10m",
        }
        resp = requests.post(
            f"{base_url.rstrip('/')}/api/chat",
            json=payload,
            timeout=300,
        )
        if resp.status_code == 200:
            content = resp.json().get("message", {}).get("content", "")
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                plan = json.loads(json_match.group())
                if "pages" in plan and len(plan["pages"]) > 0:
                    return plan
    except Exception as e:
        print(f"⚠️ Pass 1 (Planung) fehlgeschlagen: {e}")
    return _generate_fallback_plan(images, len(images))
```

- [ ] **Step 2: Update test_plan.py mocks**

Read `tests/test_photobook/test_plan.py`. The tests mock `requests.post`. Update them so the mock response includes the expected multimodal format. The mock should now return a JSON response with `"images"` key in the request body being checked (or simply ignore it — mocks verify status_code and `.json()` only).

Key changes:
- `test_plan_returns_valid_structure`: Mock's `resp.json()` should still return a valid plan JSON. The mock itself doesn't need to validate the request format.
- `test_fallback_on_llm_error`: Mock should still raise or return error — fallback behavior unchanged.

Run: `uv run pytest tests/test_photobook/test_plan.py -v`
Expected: ALL tests PASS

- [ ] **Step 3: Commit**

```bash
git add app/photobook/plan.py tests/test_photobook/test_plan.py
git commit -m "feat: make photobook Pass 1 (plan.py) multimodal with base64 images"
```

---

### Task 3: Pass 2 (generate.py) multimodal with captions + titles

**Files:**
- Modify: `app/photobook/generate.py`
- Modify: `tests/test_photobook/test_generate.py`

- [ ] **Step 1: Update the prompt to include caption + title instructions**

Read `app/photobook/generate.py`. In `_build_generate_prompt()` (around line 25-45), add to the prompt after the REGELN section:

```
5. Generiere einen kurzen, stimmungsvollen Seitentitel (2-5 Woerter, Deutsch) — Feld "title"
6. Generiere fuer jedes Bild eine aussagekraeftige Bildunterschrift (1 Satz, sachlich, Deutsch) — Feld "caption" im jeweiligen Slot
```

And update the example output format to include `"title"`:

```
ANTWORTE NUR mit JSON-Array:
[{"template_id": "hero_single", "page_type": "single", "title": "Gipfelstürmer", "slots": [{"slot_id": "main", "image_index": 3, "caption": "Der steile Aufstieg zum Gipfelgrat bei klarer Sicht"}]}]
```

- [ ] **Step 2: Add image encoding and multimodal request to generate_photobook_pages()**

Replace the request block (lines 59-65) with multimodal format:

```python
    prompt = _build_generate_prompt(pages_plan, gpx_stats, notes)
    
    # Bilder als Base64 encodieren
    encoded_images = []
    for img in images:
        b64 = encode_image_base64(img.path)
        if b64:
            encoded_images.append(b64)
    
    try:
        payload = {
            "model": model,
            "messages": [{
                "role": "user",
                "content": prompt,
                "images": encoded_images,
            }],
            "stream": False,
            "options": {"temperature": 0.3, "num_predict": 8192},
            "keep_alive": "10m",
        }
        resp = requests.post(
            f"{base_url.rstrip('/')}/api/chat",
            json=payload,
            timeout=300,
        )
```

Also add `from app.utils.image_utils import encode_image_base64` at the top.

- [ ] **Step 3: Parse title field in the response**

In the response parsing loop (lines 72-80), add `"title"` field extraction:

```python
                result = []
                for pd in pages_data:
                    valid_slots = []
                    for slot in pd.get("slots", []):
                        idx = slot.get("image_index", -1)
                        if 0 <= idx < len(images):
                            valid_slots.append(slot)
                        else:
                            valid_slots.append({k: v for k, v in slot.items() if k != "image_index"})
                    page = PageDescription(
                        template_id=pd.get("template_id", "grid_2x2"),
                        page_type=pd.get("page_type", "single"),
                        slots=valid_slots,
                    )
                    # Titel in den ersten Text/Caption-Slot packen oder als Metadatum
                    if pd.get("title"):
                        page.slots.append({"slot_id": "title", "text": pd["title"]})
                    result.append(page)
```

- [ ] **Step 4: Update test_generate.py mocks**

Update mock responses to include multimodal format. Add new test:

```python
    def test_generate_includes_titles_and_captions(self):
        """LLM-Response mit 'title' und 'caption' Feldern muss korrekt geparst werden."""
        plan = {"pages": [{"position": 0, "template_category": "hero", "image_indices": [0]}]}
        images = [ImageData(path=f"/tmp/img_{i}.jpg") for i in range(1)]
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "message": {"content": '[{"template_id": "hero_single", "page_type": "single", "title": "Aufbruch", "slots": [{"slot_id": "main", "image_index": 0, "caption": "Morgendlicher Start bei Sonnenaufgang"}]}]'}
        }
        with patch("app.photobook.generate.requests.post", return_value=mock_resp):
            pages = generate_photobook_pages(plan, images, None, None, model="test")
        assert len(pages) == 1
        # Titel sollte als Slot vorhanden sein
        title_slot = next((s for s in pages[0].slots if s.get("slot_id") == "title"), None)
        assert title_slot is not None
        assert title_slot["text"] == "Aufbruch"
        # Caption sollte im main-Slot vorhanden sein
        main_slot = next((s for s in pages[0].slots if s.get("slot_id") == "main"), None)
        assert main_slot is not None
        assert "Sonnenaufgang" in main_slot.get("caption", "")
```

Run: `uv run pytest tests/test_photobook/test_generate.py -v`
Expected: ALL tests PASS

- [ ] **Step 5: Commit**

```bash
git add app/photobook/generate.py tests/test_photobook/test_generate.py
git commit -m "feat: make photobook Pass 2 multimodal with captions and page titles"
```

---

### Task 4: Add title slot to templates + CSS + renderer

**Files:**
- Modify: All 8 template JSONs in `app/photobook/templates/`
- Modify: `app/photobook/styles.css`
- Modify: `app/photobook/renderer.py`
- Modify: `tests/test_photobook/test_renderer.py`
- Modify: `tests/test_photobook/test_template_loader.py`

- [ ] **Step 1: Add title slot to each template JSON**

For each of the 8 templates, add a `title` slot BEFORE the existing slots. Example for `hero_single.json`:

```json
{
  "id": "hero_single",
  "name": "Hero — Einzelbild",
  "category": "hero",
  "description": "Großes Einzelbild über eine Seite, optional mit Bildunterschrift. Für Cover, Kapitelanfänge und Schlüsselmomente.",
  "page_type": "single",
  "min_images": 1,
  "max_images": 1,
  "has_text": false,
  "supports_captions": true,
  "css_class": "layout-hero-single",
  "slots": [
    {"id": "title", "type": "text", "css_area": "title", "optional": true},
    {"id": "main", "type": "image", "priority": "primary", "css_area": "main", "optional": false},
    {"id": "caption", "type": "caption", "priority": null, "css_area": "caption", "optional": true}
  ]
}
```

The `title` slot goes first in each template's `slots` array. The `css_area` is `"title"`. Apply to ALL 8 templates.

- [ ] **Step 2: Update CSS grid for each layout to include title area**

In `app/photobook/styles.css`, add title area to each layout. The title goes above the content. Example for `hero_single`:

```css
.layout-hero-single {
  display: grid;
  grid-template-columns: 1fr;
  grid-template-rows: auto 1fr auto;
  grid-template-areas:
    "title"
    "main"
    "caption";
  gap: 0;
}
```

Apply similar changes to all 8 layouts (title row added on top). Also add `.slot-title` styling at the bottom:

```css
.slot-title {
  font-size: 14pt;
  font-weight: bold;
  color: #222;
  padding: 4mm;
  display: flex;
  align-items: center;
}
```

- [ ] **Step 3: Update renderer to handle title slots**

In `app/photobook/renderer.py`, the text-slot rendering block (around lines 88-92) already handles `slot_def.type == "text"`. The title slot is `type: "text"` with `css_area: "title"`, so it's automatically rendered. Just add a CSS class distinction: use `slot-title` for slots with `slot_id == "title"`, keep `slot-text` for others.

Change the text rendering (around line 90):
```python
            elif slot_def.type == "text":
                text = html.escape(slot_data.get("text", ""))
                css_class = "slot-title" if slot_id == "title" else "slot-text"
                html_parts.append(
                    f'<div class="{css_class}" {area_style}>{text}</div>'
                )
```

- [ ] **Step 4: Update renderer test**

In `tests/test_photobook/test_renderer.py`, add test:

```python
    def test_render_title_slot(self):
        """Title-Slot wird als slot-title gerendert."""
        pages = [
            PageDescription(
                template_id="hero_single",
                page_type="single",
                slots=[
                    {"slot_id": "title", "text": "Gipfelstürmer"},
                    {"slot_id": "main", "image_index": 0},
                ],
            )
        ]
        html = render_photobook(pages, TEST_IMAGES)
        assert "slot-title" in html
        assert "Gipfelstürmer" in html
```

- [ ] **Step 5: Update template loader test**

In `tests/test_photobook/test_template_loader.py`, update `test_all_templates_have_valid_slots` to accept the new `title` slot (it checks slot types are valid — `"text"` is already allowed).

Run: `uv run pytest tests/test_photobook/test_renderer.py tests/test_photobook/test_template_loader.py -v`
Expected: ALL tests PASS

- [ ] **Step 6: Commit**

```bash
git add app/photobook/templates/*.json app/photobook/styles.css app/photobook/renderer.py tests/test_photobook/test_renderer.py tests/test_photobook/test_template_loader.py
git commit -m "feat: add title slot to all photobook templates with CSS and renderer support"
```

---

### Task 5: Refactor image_selector.py to use shared utility

**Files:**
- Modify: `app/services/image_selector.py`

- [ ] **Step 1: Replace _encode_image with import**

In `app/services/image_selector.py`, replace `_encode_image()` function (lines 121-129) with:

```python
from app.utils.image_utils import encode_image_base64 as _encode_image
```

Remove the old function definition. All internal callers (`_encode_image(path)`) work unchanged.

- [ ] **Step 2: Run blog selection tests**

```bash
uv run pytest tests/test_services/ -v -k "select" --ignore=tests/test_services/test_map_helpers.py
```
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add app/services/image_selector.py
git commit -m "refactor: image_selector uses encode_image_base64 from shared utility"
```

---

### Task 6: Full suite verification

**Files:**
- None (verification only)

- [ ] **Step 1: Run full photobook suite**

```bash
uv run pytest tests/test_photobook/ -v
```
Expected: ALL PASS

- [ ] **Step 2: Run shared utility tests**

```bash
uv run pytest tests/test_utils/ -v
```
Expected: ALL PASS

- [ ] **Step 3: Run full test suite**

```bash
uv run pytest tests/ -v --ignore=tests/test_services/test_map_helpers.py::TestMatchPhotosToPauses::test_exif_timestamp_format
```
Expected: ALL PASS except ignored pre-existing failure
