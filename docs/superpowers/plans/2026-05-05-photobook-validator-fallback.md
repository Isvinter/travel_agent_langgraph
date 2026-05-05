# Photopuch Validator + Fallback + Bildanzahl Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce default photo_count to realistic values, make validator repair pages minimally instead of degrading to grid_2x2, and make generate.py fallback use Pass-1 template categories.

**Architecture:** Three focused changes: (1) reduce PHOTOBOOK_SIZE_MAP values in state.py, (2) rewrite enforce_fallback() to preserve template/captions with minimal repairs, (3) rewrite generate.py fallback to select templates by category from Pass 1 plan.

**Tech Stack:** Python 3.12+, Pydantic, pytest

---

### Task 1: Reduce photo_count in PHOTOBOOK_SIZE_MAP

**Files:**
- Modify: `app/state.py:46-50`
- Modify: `tests/test_state.py` (adjust expected values)
- Modify: `tests/test_photobook/test_graph.py:28` (fix pre-existing test)

- [ ] **Step 1: Update PHOTOBOOK_SIZE_MAP in app/state.py**

Read `app/state.py`. The `PHOTOBOOK_SIZE_MAP` is at lines 46-50. Replace:

```python
PHOTOBOOK_SIZE_MAP = {
    "short":    {"photo_count": 14, "page_range": "8-12"},
    "normal":   {"photo_count": 20, "page_range": "14-18"},
    "detailed": {"photo_count": 26, "page_range": "20-24"},
}
```

With:

```python
PHOTOBOOK_SIZE_MAP = {
    "short":    {"photo_count": 12, "page_range": "8-12"},
    "normal":   {"photo_count": 16, "page_range": "14-18"},
    "detailed": {"photo_count": 20, "page_range": "20-24"},
}
```

- [ ] **Step 2: Update test_state.py expected values**

Read `tests/test_state.py`. Find the `TestApplyPhotobookSize` class. Update expected values:

In `test_short_maps_correctly` (around line 54-58): change `assert cfg.photo_count == 14` to `assert cfg.photo_count == 12`
In `test_normal_maps_correctly` (around line 60-64): change `assert cfg.photo_count == 20` to `assert cfg.photo_count == 16`
In `test_detailed_maps_correctly` (around line 66-70): change `assert cfg.photo_count == 26` to `assert cfg.photo_count == 20`

- [ ] **Step 3: Fix pre-existing test_select_images_node failure**

Read `tests/test_photobook/test_graph.py`. The `test_select_images_node` test (around line 28) has:
```python
assert len(result.photobook_images) == 12
```
This was previously failing because photo_count=20 but the test expected 12. With photo_count=16 (normal), change to:
```python
assert len(result.photobook_images) == 16
```

- [ ] **Step 4: Run state and graph tests**

```bash
uv run pytest tests/test_state.py::TestApplyPhotobookSize tests/test_photobook/test_graph.py::TestPhotobookNodes::test_select_images_node -v
```
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add app/state.py tests/test_state.py tests/test_photobook/test_graph.py
git commit -m "fix: reduce default photobook photo_count to 12/16/20 (short/normal/detailed)"
```

---

### Task 2: Write failing tests for enforce_fallback minimal repair

**Files:**
- Modify: `tests/test_photobook/test_validator.py`

- [ ] **Step 1: Add test_enforce_fallback_preserves_captions**

Read `tests/test_photobook/test_validator.py`. Add to `TestEnforceFallback` class:

```python
    def test_enforce_fallback_preserves_captions(self):
        """Captions aus der Original-Seite muessen im Fallback erhalten bleiben."""
        page = PageDescription(
            template_id="hero_single",
            page_type="single",
            slots=[
                {"slot_id": "main", "image_index": 0, "caption": "Schöne Aussicht"},
                {"slot_id": "wrong_slot", "image_index": 1},  # Fehler provozieren
            ],
        )
        result = enforce_fallback(page)
        # Caption muss im Fallback vorhanden sein
        captions = [s.get("caption", "") for s in result.slots]
        assert "Schöne Aussicht" in captions
```

- [ ] **Step 2: Add test_enforce_fallback_preserves_template_when_possible**

```python
    def test_enforce_fallback_preserves_template_when_possible(self):
        """Wenn nur ein Slot-Name falsch ist, soll das Template erhalten bleiben."""
        page = PageDescription(
            template_id="split_equal",
            page_type="spread",
            slots=[
                {"slot_id": "left_", "image_index": 0},   # Tippfehler: "left_" statt "left"
                {"slot_id": "right", "image_index": 1},
            ],
        )
        result = enforce_fallback(page)
        # Template sollte split_equal bleiben (nicht zu grid_2x2 degradiert)
        assert result.template_id == "split_equal"
        # Slots sollten korrigiert sein
        slot_ids = [s.get("slot_id", "") for s in result.slots]
        assert "left" in slot_ids
```

- [ ] **Step 3: Run the new tests — they MUST fail**

```bash
uv run pytest tests/test_photobook/test_validator.py::TestEnforceFallback::test_enforce_fallback_preserves_captions tests/test_photobook/test_validator.py::TestEnforceFallback::test_enforce_fallback_preserves_template_when_possible -v
```
Expected: BOTH FAIL (current enforce_fallback always returns grid_2x2 without captions)

- [ ] **Step 4: Commit**

```bash
git add tests/test_photobook/test_validator.py
git commit -m "test: add failing tests for enforce_fallback caption/template preservation"
```

---

### Task 3: Implement minimal-repair enforce_fallback in validator.py

**Files:**
- Modify: `app/photobook/validator.py:59-78`

- [ ] **Step 1: Replace enforce_fallback with minimal-repair logic**

Read `app/photobook/validator.py`. The `enforce_fallback` function is at lines 59-78. Replace the entire function with:

```python
def enforce_fallback(page: PageDescription) -> PageDescription:
    """Repariert eine fehlerhafte Seite mit minimalen Eingriffen.

    Priorität: Template erhalten > Slots korrigieren > Captions bewahren.
    Nur wenn das Template nicht existiert, wird auf ein passendes Ersatz-Template
    der gleichen Kategorie oder grid_2x2 als letzte Instanz zurückgegriffen.
    """
    templates = load_all_templates()
    image_indices = [
        s["image_index"] for s in page.slots
        if s.get("image_index") is not None and s["image_index"] >= 0
    ]
    captions = {
        s.get("slot_id", ""): s.get("caption", "")
        for s in page.slots
        if s.get("caption")
    }

    # Template existiert nicht → nächstes aus gleicher Kategorie wählen
    if page.template_id not in templates:
        tmpl = templates.get(page.template_id)
        category = tmpl.category if tmpl else "grid"
        # Template gleicher Kategorie mit passender Bildanzahl finden
        same_category = [t for t in templates.values() if t.category == category]
        for t in sorted(same_category, key=lambda t: abs(t.min_images - len(image_indices))):
            if t.min_images <= len(image_indices) <= t.max_images:
                page.template_id = t.id
                break
        else:
            page.template_id = "grid_2x2"

    template = templates[page.template_id]
    slot_defs = {s.id: s for s in template.slots}
    image_slot_ids = [s.id for s in template.slots if s.type == "image"]

    # Slots korrigieren: falsche IDs reparieren, überzählige droppen
    repaired_slots = []
    for i, img_idx in enumerate(image_indices):
        if i >= len(image_slot_ids):
            break
        slot_id = image_slot_ids[i]
        # Caption aus Original-Slot übernehmen (falls vorhanden)
        orig_caption = ""
        for orig_slot in page.slots:
            if orig_slot.get("image_index") == img_idx and orig_slot.get("caption"):
                orig_caption = orig_slot["caption"]
                break
        slot_data = {"slot_id": slot_id, "image_index": img_idx}
        if orig_caption:
            slot_data["caption"] = orig_caption
        repaired_slots.append(slot_data)

    # Captions aus dedizierten Caption-Slots übernehmen
    for slot_id, caption in captions.items():
        if slot_id in slot_defs and slot_defs[slot_id].type == "caption":
            repaired_slots.append({"slot_id": slot_id, "caption": caption})

    return PageDescription(
        template_id=page.template_id,
        page_type=page.page_type,
        slots=repaired_slots,
    )
```

- [ ] **Step 2: Run the previously failing tests — they should now PASS**

```bash
uv run pytest tests/test_photobook/test_validator.py::TestEnforceFallback::test_enforce_fallback_preserves_captions tests/test_photobook/test_validator.py::TestEnforceFallback::test_enforce_fallback_preserves_template_when_possible -v
```
Expected: BOTH PASS

- [ ] **Step 3: Run all validator tests**

```bash
uv run pytest tests/test_photobook/test_validator.py -v
```
Expected: ALL PASS (existing tests may need adjustment if they depended on grid_2x2 fallback behavior)

- [ ] **Step 4: Run full photobook test suite**

```bash
uv run pytest tests/test_photobook/ -v
```
Expected: All tests PASS (fix any tests that depended on old enforce_fallback behavior)

- [ ] **Step 5: Commit**

```bash
git add app/photobook/validator.py
git commit -m "fix: enforce_fallback preserves template and captions with minimal repair"
```

---

### Task 4: Write failing test for category-based generate.py fallback

**Files:**
- Modify: `tests/test_photobook/test_generate.py`

- [ ] **Step 1: Add test_fallback_uses_plan_categories**

Read `tests/test_photobook/test_generate.py`. Add to `TestGenerate` class:

```python
    def test_fallback_uses_plan_categories(self):
        """Fallback soll Template-Kategorien aus dem Plan respektieren, nicht alles grid_2x2."""
        from app.photobook.generate import generate_photobook_pages
        plan = {
            "pages": [
                {"position": 0, "template_category": "hero", "image_indices": [0]},
                {"position": 1, "template_category": "split", "image_indices": [1, 2]},
            ]
        }
        images = [
            ImageData(path=f"/tmp/img_{i}.jpg") for i in range(3)
        ]
        # LLM simulieren der fehlschlägt → Fallback wird aktiviert
        with patch("app.photobook.generate.requests.post", side_effect=Exception("LLM down")):
            pages = generate_photobook_pages(plan, images, None, None, model="test")
        assert len(pages) == 2
        # Position 0: hero → hero_single
        assert pages[0].template_id == "hero_single"
        # Position 1: split → split_equal
        assert pages[1].template_id == "split_equal"
```

- [ ] **Step 2: Run the test — it MUST fail**

```bash
uv run pytest tests/test_photobook/test_generate.py::TestGenerate::test_fallback_uses_plan_categories -v
```
Expected: FAIL — current fallback uses grid_2x2 for all pages

- [ ] **Step 3: Commit**

```bash
git add tests/test_photobook/test_generate.py
git commit -m "test: add failing test for category-based generate.py fallback"
```

---

### Task 5: Implement category-based fallback in generate.py

**Files:**
- Modify: `app/photobook/generate.py:87-91`

- [ ] **Step 1: Replace fallback logic with category-based template selection**

Read `app/photobook/generate.py`. The fallback is at lines 87-91. Replace from line 87 to the end of the function (line 92) with:

```python
    # Fallback: nutze Template-Kategorien aus dem Plan (Pass 1)
    CATEGORY_DEFAULTS = {
        "hero": "hero_single",
        "split": "split_equal",
        "grid": "grid_2x2",
        "strip": "strip_3",
        "mixed": "image_text_left",
        "collection": "collection_3",
    }
    all_templates = load_all_templates()
    fallback = []
    for plan_page in pages_plan:
        category = plan_page.get("template_category", "grid")
        template_id = CATEGORY_DEFAULTS.get(category, "grid_2x2")
        tmpl = all_templates.get(template_id)
        if tmpl is None:
            tmpl = all_templates.get("grid_2x2")
            template_id = "grid_2x2"
        indices = plan_page.get("image_indices", [])
        image_slots = [s.id for s in tmpl.slots if s.type == "image"]
        slots = []
        for i, (sid, idx) in enumerate(zip(image_slots, indices)):
            slot = {"slot_id": sid, "image_index": idx}
            slots.append(slot)
        fallback.append(PageDescription(
            template_id=template_id,
            page_type=tmpl.page_type,
            slots=slots,
        ))
    return fallback
```

Note: You'll also need to add `from app.photobook.template_loader import load_all_templates` at the top of the file if not already present.

- [ ] **Step 2: Run the previously failing test**

```bash
uv run pytest tests/test_photobook/test_generate.py::TestGenerate::test_fallback_uses_plan_categories -v
```
Expected: PASS

- [ ] **Step 3: Run all generate tests**

```bash
uv run pytest tests/test_photobook/test_generate.py -v
```
Expected: ALL PASS

- [ ] **Step 4: Run full photobook test suite**

```bash
uv run pytest tests/test_photobook/ -v
```
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add app/photobook/generate.py
git commit -m "fix: generate.py fallback uses Pass-1 template categories instead of grid_2x2"
```

---

### Task 6: Full suite verification

**Files:**
- None (verification only)

- [ ] **Step 1: Run full photobook suite**

```bash
uv run pytest tests/test_photobook/ -v
```
Expected: ALL PASS, zero failures

- [ ] **Step 2: Run full test suite**

```bash
uv run pytest tests/ -v
```
Expected: All PASS except any pre-existing unrelated failures
