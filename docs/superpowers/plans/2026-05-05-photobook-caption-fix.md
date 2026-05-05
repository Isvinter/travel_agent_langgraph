# Photopuch Caption-Rendering-Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix captions being invisible by rendering them in the template's dedicated caption CSS grid area instead of the image slot's area.

**Architecture:** Single-file change in `app/photobook/renderer.py`. When an image slot has a caption, look up the template's caption-type slot and use its `css_area` for the caption div. Templates without caption slots (grid_2x2, strip_3, collection_3) correctly render no captions.

**Tech Stack:** Python 3.12+, Pydantic, pytest

---

### Task 1: Write failing test for caption grid-area

**Files:**
- Modify: `tests/test_photobook/test_renderer.py`

- [ ] **Step 1: Add test_caption_uses_correct_grid_area to TestRenderer class**

Open `tests/test_photobook/test_renderer.py`. Add this test method to the `TestRenderer` class (after the existing `test_render_single_page_hero` method):

```python
    def test_caption_uses_correct_grid_area(self):
        """Caption soll im dedizierten caption-grid-area landen, nicht im image-grid-area."""
        pages = [
            PageDescription(
                template_id="hero_single",
                page_type="single",
                slots=[{"slot_id": "main", "image_index": 0, "caption": "Cover"}],
            )
        ]
        html = render_photobook(pages, TEST_IMAGES)
        # Caption muss im grid-area: caption erscheinen, nicht grid-area: main
        # Suche nach dem caption-div mit korrektem grid-area
        assert 'slot-caption' in html
        # Der caption-Slot des hero_single templates hat css_area="caption"
        assert 'grid-area: caption' in html
```

- [ ] **Step 2: Run the test — it MUST fail (caption currently uses grid-area: main)**

```bash
uv run pytest tests/test_photobook/test_renderer.py::TestRenderer::test_caption_uses_correct_grid_area -v
```
Expected: FAIL — `AssertionError: assert 'grid-area: caption' in html`

- [ ] **Step 3: Commit the failing test**

```bash
git add tests/test_photobook/test_renderer.py
git commit -m "test: add failing test for caption grid-area in photobook renderer"
```

---

### Task 2: Fix renderer to use template's caption slot area

**Files:**
- Modify: `app/photobook/renderer.py` (lines 81-86)

- [ ] **Step 1: Replace the caption rendering logic**

In `app/photobook/renderer.py`, the section at lines 81-86 currently reads:

```python
                # Caption kann auch am Image-Slot haengen
                caption = html.escape(slot_data.get("caption", ""))
                if caption:
                    html_parts.append(
                        f'<div class="slot-caption" {area_style}>{caption}</div>'
                    )
```

Replace with:

```python
                # Caption im dedizierten Caption-Slot des Templates rendern
                caption = html.escape(slot_data.get("caption", ""))
                if caption:
                    caption_slot_def = next((s for s in template.slots if s.type == "caption"), None)
                    if caption_slot_def:
                        caption_area = f'style="grid-area: {caption_slot_def.css_area}"'
                    else:
                        caption_area = area_style  # Fallback: Template hat keinen Caption-Slot
                    html_parts.append(
                        f'<div class="slot-caption" {caption_area}>{caption}</div>'
                    )
```

Use the Edit tool — find the exact `oldString` to replace.

- [ ] **Step 2: Run the previously failing test — it should now PASS**

```bash
uv run pytest tests/test_photobook/test_renderer.py::TestRenderer::test_caption_uses_correct_grid_area -v
```
Expected: PASS

- [ ] **Step 3: Run all renderer tests to check for regressions**

```bash
uv run pytest tests/test_photobook/test_renderer.py -v
```
Expected: ALL 6 tests PASS (5 existing + 1 new)

- [ ] **Step 4: Run full photobook test suite**

```bash
uv run pytest tests/test_photobook/ -v
```
Expected: All tests PASS except the pre-existing `test_select_images_node` failure

- [ ] **Step 5: Commit**

```bash
git add app/photobook/renderer.py
git commit -m "fix: render photobook captions in template's dedicated caption grid area"
```
