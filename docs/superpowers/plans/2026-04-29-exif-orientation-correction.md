# EXIF Orientation Correction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Apply EXIF orientation correction in `compress_image_to_jpeg()` so output images are properly oriented.

**Architecture:** Add `ImageOps.exif_transpose()` call in `app/services/blog_generator.py`, function `compress_image_to_jpeg()`, immediately after `Image.open()` and before `img.convert("RGB")`. One import change, one line added.

**Tech Stack:** Pillow `ImageOps` (already available via existing `pillow>=12.2.0` dependency)

---

### Task 1: Add EXIF orientation correction to compress_image_to_jpeg

**Files:**
- Modify: `app/services/blog_generator.py:70-76`

- [ ] **Step 1: Add `ImageOps` to the PIL import**

Change line 70 from:
```python
        from PIL import Image
```
to:
```python
        from PIL import Image, ImageOps
```

- [ ] **Step 2: Add `exif_transpose()` call after `Image.open()`**

Insert `img = ImageOps.exif_transpose(img)` between the `with Image.open(...)` block and `img.convert("RGB")`.

Lines 75-76 currently:
```python
        with Image.open(image_path) as img:
            img = img.convert("RGB")  # JPEG unterstützt kein Alpha/Kanäle
```

Change to:
```python
        with Image.open(image_path) as img:
            img = ImageOps.exif_transpose(img)
            img = img.convert("RGB")  # JPEG unterstützt kein Alpha/Kanäle
```

- [ ] **Step 3: Run the pipeline to verify**

```bash
uv run python main.py
```

Verify that output images in `output/<timestamp>/images/` are correctly oriented (no visible rotation artifacts from EXIF orientation tags).

- [ ] **Step 4: Run image loading tests to verify no regressions**

```bash
uv run python -m pytest tests/test_services/test_image_loader.py tests/test_services/test_metadata_extractor.py -v
```

Expected: All existing tests pass (orientation change does not affect these).

- [ ] **Step 5: Commit**

```bash
git add app/services/blog_generator.py
git commit -m "feat: apply EXIF orientation correction when compressing images"
```
