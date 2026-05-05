# Photopuch Image Compression Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add image compression to the photobook pipeline (identically to the blog pipeline: max 1200px, ≤1MB, JPEG/RGB) by extracting the existing `compress_image_to_jpeg()` into a shared utility and wiring it into `render_photobook_node`.

**Architecture:** Extract `compress_image_to_jpeg()` from `app/services/blog_generator.py` into new `app/utils/image_utils.py`. Blog imports it back. Photobook node calls it before passing images to the renderer, storing compressed copies in `output/photobook_<ts>/images/`.

**Tech Stack:** Python 3.12+, Pillow (PIL), Pydantic, pytest

---

### Task 1: Create shared utility module with compress_image_to_jpeg

**Files:**
- Create: `app/utils/image_utils.py`
- Create: `tests/test_utils/__init__.py`

- [ ] **Step 1: Create `tests/test_utils/__init__.py`**

```python
# Test package für app.utils Komponenten
```

- [ ] **Step 2: Create `app/utils/image_utils.py` with the extracted function**

```python
"""Gemeinsam genutzte Bildverarbeitungs-Funktionen.

Wird sowohl von der Blog- als auch der Photopuch-Pipeline verwendet.
"""

import io
import os
from typing import Optional


def compress_image_to_jpeg(
    image_path: str,
    output_path: str,
    max_size_bytes: int = 1024 * 1024,  # 1 MB
    max_dim: int = 1200,
) -> Optional[str]:
    """Komprimiert ein Bild auf ≤ max_size_bytes, konvertiert nach JPEG.

    Resizet zuerst auf max_dim, reduziert dann JPEG-Qualität.
    Bei Bedarf wird weiter verkleinert bis das Limit erreicht ist.
    Gibt den Pfad zur ausgegebenen Datei zurück oder None bei Fehler.
    """
    try:
        from PIL import Image, ImageOps

        if not os.path.exists(image_path):
            return None

        with Image.open(image_path) as img:
            img = ImageOps.exif_transpose(img)
            img = img.convert("RGB")  # JPEG unterstützt kein Alpha/Kanäle

            # Mandatory: auf max_dim runterskalieren
            if max(img.size) > max_dim:
                ratio = max_dim / max(img.size)
                img = img.resize(
                    (int(img.width * ratio), int(img.height * ratio)),
                    Image.LANCZOS,
                )

            w, h = img.size

            # Phase 1: JPEG-Qualität reduzieren
            quality = 85
            while quality >= 10:
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=quality, optimize=True)
                if len(buf.getvalue()) <= max_size_bytes:
                    with open(output_path, "wb") as f:
                        f.write(buf.getvalue())
                    return output_path
                quality -= 5

            # Phase 2: weitere Grössenreduktion
            while max(w, h) > 200:
                w = int(w * 0.75)
                h = int(h * 0.75)
                resized = img.resize((w, h), Image.LANCZOS)

                buf = io.BytesIO()
                resized.save(buf, format="JPEG", quality=75, optimize=True)
                if len(buf.getvalue()) <= max_size_bytes:
                    with open(output_path, "wb") as f:
                        f.write(buf.getvalue())
                    return output_path

            # Fallback: kleinste mögliche Größe
            buf = io.BytesIO()
            img.resize((200, int(h * 200 / w))).save(
                buf, format="JPEG", quality=10, optimize=True
            )
            with open(output_path, "wb") as f:
                f.write(buf.getvalue())
            return output_path

    except Exception as e:
        print(f"⚠️ Error compressing image {image_path}: {e}")
        return None
```

- [ ] **Step 3: Run tests to verify the module can be imported**

```bash
uv run python -c "from app.utils.image_utils import compress_image_to_jpeg; print('import OK')"
```
Expected: `import OK`

- [ ] **Step 4: Commit**

```bash
git add app/utils/image_utils.py tests/test_utils/__init__.py
git commit -m "feat: extract compress_image_to_jpeg into shared utility app/utils/image_utils.py"
```

---

### Task 2: Update blog_generator.py to import from shared utility

**Files:**
- Modify: `app/services/blog_generator.py`

- [ ] **Step 1: Remove the compress_image_to_jpeg function definition from blog_generator.py**

The function spans lines 70–134. Replace with an import. Change line 70 from:

```python
def compress_image_to_jpeg(
    image_path: str,
    ...
    except Exception as e:
        print(f"⚠️ Error compressing image {image_path}: {e}")
        return None
```

To:

```python
from app.utils.image_utils import compress_image_to_jpeg  # noqa: F401 — re-exported for callers
```

Note: Use the Edit tool to make this precise replacement — find the exact oldString from the file.

- [ ] **Step 2: Verify blog module still exports compress_image_to_jpeg**

```bash
uv run python -c "import app.services.blog_generator as bg; print(bg.compress_image_to_jpeg)"
```
Expected: `<function compress_image_to_jpeg at 0x...>`

- [ ] **Step 3: Run existing blog tests to confirm nothing broke**

```bash
uv run pytest tests/test_services/test_blog_generator.py -v
```
Expected: ALL tests PASS

- [ ] **Step 4: Commit**

```bash
git add app/services/blog_generator.py
git commit -m "refactor: blog_generator imports compress_image_to_jpeg from shared utility"
```

---

### Task 3: Write unit tests for compress_image_to_jpeg from shared utility

**Files:**
- Create: `tests/test_utils/test_image_utils.py`

- [ ] **Step 1: Write the test file**

```python
"""Tests für die gemeinsame Bildkompressions-Utility."""
import os
import pytest
from PIL import Image
from app.utils.image_utils import compress_image_to_jpeg


class TestCompressImageToJpeg:
    """Unit tests für compress_image_to_jpeg aus dem shared utility."""

    @pytest.mark.unit
    def test_compresses_image_to_small_size(self, tmp_path):
        """Ein 2000x2000 Bild muss auf ≤50KB komprimiert werden."""
        src = str(tmp_path / "src.jpg")
        dst = str(tmp_path / "dst.jpg")
        img = Image.new("RGB", (2000, 2000), color="red")
        img.save(src)

        result = compress_image_to_jpeg(src, dst, max_size_bytes=50 * 1024, max_dim=200)
        assert result == dst
        assert os.path.exists(dst)
        assert os.path.getsize(dst) <= 50 * 1024

    @pytest.mark.unit
    def test_returns_none_for_missing_source(self):
        """Nonexistente Quelle gibt None zurück."""
        result = compress_image_to_jpeg("/nonexistent/src.jpg", "/tmp/dst.jpg")
        assert result is None

    @pytest.mark.unit
    def test_output_is_jpeg_rgb(self, tmp_path):
        """Output muss JPEG und RGB sein."""
        src = str(tmp_path / "src.png")
        dst = str(tmp_path / "dst.jpg")
        img = Image.new("RGBA", (400, 300), color=(255, 0, 0, 128))
        img.save(src)

        result = compress_image_to_jpeg(src, dst, max_size_bytes=500 * 1024, max_dim=400)
        assert result == dst
        with Image.open(dst) as out:
            assert out.mode == "RGB"
            assert out.format == "JPEG"

    @pytest.mark.unit
    def test_max_dimension_enforced(self, tmp_path):
        """Output-Dimension darf max_dim nicht überschreiten."""
        src = str(tmp_path / "src.jpg")
        dst = str(tmp_path / "dst.jpg")
        img = Image.new("RGB", (3000, 1000), color="blue")
        img.save(src)

        result = compress_image_to_jpeg(src, dst, max_size_bytes=5 * 1024 * 1024, max_dim=600)
        assert result == dst
        with Image.open(dst) as out:
            assert max(out.size) <= 600

    @pytest.mark.unit
    def test_creates_output_directory_if_missing(self, tmp_path):
        """Sollte das Output-Verzeichnis nicht automatisch erstellen — Aufrufer ist verantwortlich."""
        src = str(tmp_path / "src.jpg")
        dst_dir = str(tmp_path / "nested" / "subdir")
        dst = os.path.join(dst_dir, "dst.jpg")
        img = Image.new("RGB", (100, 100), color="green")
        img.save(src)

        result = compress_image_to_jpeg(src, dst, max_size_bytes=500 * 1024, max_dim=100)
        assert result is None  # Verzeichnis existiert nicht → Fehler
```

- [ ] **Step 2: Run the tests — they should pass (function is already correct)**

```bash
uv run pytest tests/test_utils/test_image_utils.py -v
```
Expected: ALL 5 tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_utils/test_image_utils.py
git commit -m "test: add unit tests for compress_image_to_jpeg shared utility"
```

---

### Task 4: Write integration test for render_photobook_node compression

**Files:**
- Create: `tests/test_photobook/test_image_compression.py`

- [ ] **Step 1: Write the test file**

```python
"""Integrationstests für Bildkompression im render_photobook_node."""
import os
import pytest
from PIL import Image
from app.state import AppState, PageDescription, ImageData, OutputConfig
from app.nodes.render_photobook_node import render_photobook_node


def _make_test_image(path: str, size=(2000, 1500), color="red"):
    """Erzeugt ein Testbild und speichert es."""
    img = Image.new("RGB", size, color=color)
    img.save(path)
    return path


class TestRenderPhotobookNodeCompression:
    """Testet dass render_photobook_node Bilder vor dem Rendern komprimiert."""

    @pytest.mark.integration
    def test_compresses_images_before_rendering(self, tmp_path, monkeypatch):
        """Node soll komprimierte Bildkopien im output-Verzeichnis erzeugen."""
        from app.config import OUTPUT_DIR as orig_output_dir

        # Output-Dir in tmp_path umleiten
        output_dir = str(tmp_path / "output")
        monkeypatch.setattr("app.nodes.render_photobook_node.OUTPUT_DIR", output_dir)

        # Testbilder erstellen (gross, damit Kompression greift)
        img_dir = tmp_path / "images"
        img_dir.mkdir()
        img_paths = []
        for i in range(3):
            p = str(img_dir / f"photo_{i}.jpg")
            _make_test_image(p, size=(2000, 1500))
            img_paths.append(p)

        # State vorbereiten
        state = AppState(
            photobook_images=[
                ImageData(path=img_paths[0]),
                ImageData(path=img_paths[1]),
                ImageData(path=img_paths[2]),
            ],
            photobook_pages=[
                PageDescription(
                    template_id="hero_single",
                    page_type="single",
                    slots=[{"slot_id": "main", "image_index": 0}],
                ),
            ],
        )

        result = render_photobook_node(state)

        # HTML muss erzeugt worden sein
        assert result.photobook_html is not None
        assert "slot-image" in result.photobook_html

        # Bild-Pfade im HTML müssen auf komprimierte Kopien zeigen
        # (file:// URI mit output/... im Pfad)
        assert output_dir in result.photobook_html

        # Originale müssen unverändert existieren
        for p in img_paths:
            assert os.path.exists(p)

    @pytest.mark.integration
    def test_handles_empty_image_list(self, tmp_path, monkeypatch):
        """Leere photobook_images-Liste sollte keinen Fehler werfen."""
        output_dir = str(tmp_path / "output")
        monkeypatch.setattr("app.nodes.render_photobook_node.OUTPUT_DIR", output_dir)

        state = AppState(
            photobook_images=[],
            photobook_pages=[
                PageDescription(
                    template_id="hero_single",
                    page_type="single",
                    slots=[{"slot_id": "main", "image_index": 0}],
                ),
            ],
        )

        result = render_photobook_node(state)
        assert result.photobook_html is not None

    @pytest.mark.integration
    def test_handles_missing_image_file(self, tmp_path, monkeypatch):
        """Nicht existierende Bilddateien sollten nicht crashen."""
        output_dir = str(tmp_path / "output")
        monkeypatch.setattr("app.nodes.render_photobook_node.OUTPUT_DIR", output_dir)

        state = AppState(
            photobook_images=[
                ImageData(path="/nonexistent/path/photo.jpg"),
            ],
            photobook_pages=[
                PageDescription(
                    template_id="hero_single",
                    page_type="single",
                    slots=[{"slot_id": "main", "image_index": 0}],
                ),
            ],
        )

        result = render_photobook_node(state)
        assert result.photobook_html is not None
```

- [ ] **Step 2: Run the integration tests (they will FAIL — the node doesn't compress yet)**

```bash
uv run pytest tests/test_photobook/test_image_compression.py -v
```
Expected: `test_compresses_images_before_rendering` FAILS — HTML enthält noch Original-Pfade statt output-Pfade

- [ ] **Step 3: Commit the failing test**

```bash
git add tests/test_photobook/test_image_compression.py
git commit -m "test: add failing integration test for photobook image compression"
```

---

### Task 5: Implement image compression in render_photobook_node

**Files:**
- Modify: `app/nodes/render_photobook_node.py`

- [ ] **Step 1: Update render_photobook_node to compress images before rendering**

Replace the entire file with:

```python
import os
from datetime import datetime
from pathlib import Path
from app.state import AppState, ImageData
from app.photobook.renderer import render_photobook
from app.photobook.validator import validate_all_pages
from app.utils.image_utils import compress_image_to_jpeg
from app.config import OUTPUT_DIR


def render_photobook_node(state: AppState) -> AppState:
    print("🖨️ Rendere Fotobuch als HTML...")
    if not state.photobook_pages:
        print("⚠️ Keine Seiten zum Rendern vorhanden.")
        return state
    validated_pages, warnings = validate_all_pages(state.photobook_pages)
    if warnings:
        for w in warnings:
            print(f"⚠️ Validator: {w}")
    state.photobook_pages = validated_pages

    # --- Bilder komprimieren ---
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    images_dir = Path(OUTPUT_DIR) / f"photobook_{timestamp}" / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    compressed_images = []
    for idx, img in enumerate(state.photobook_images):
        orig = img.path
        if not orig or not os.path.isfile(orig):
            print(f"⚠️ Bild nicht gefunden, überspringe: {orig}")
            compressed_images.append(img)
            continue

        basename = os.path.splitext(os.path.basename(orig))[0]
        out_name = f"{idx:02d}_{basename}.jpg"
        out_path = str(images_dir / out_name)

        result = compress_image_to_jpeg(orig, out_path)
        if result:
            compressed_images.append(ImageData(
                path=result,
                timestamp=img.timestamp,
                latitude=img.latitude,
                longitude=img.longitude,
            ))
            print(f"  ✅ Bild {idx + 1}/{len(state.photobook_images)} komprimiert: {out_name}")
        else:
            print(f"  ⚠️ Kompression fehlgeschlagen für {orig}, verwende Original")
            compressed_images.append(img)

    # --- Rendern mit komprimierten Bildern ---
    try:
        html = render_photobook(validated_pages, compressed_images)
        state.photobook_html = html
        print(f"✅ Fotobuch-HTML gerendert ({len(html)} Zeichen).")
    except Exception as e:
        print(f"❌ Fehler beim Rendern: {e}")
    return state
```

- [ ] **Step 2: Run the integration test to verify compression works**

```bash
uv run pytest tests/test_photobook/test_image_compression.py::TestRenderPhotobookNodeCompression::test_compresses_images_before_rendering -v
```
Expected: PASS

- [ ] **Step 3: Run all integration tests**

```bash
uv run pytest tests/test_photobook/test_image_compression.py -v
```
Expected: ALL 3 tests PASS

- [ ] **Step 4: Run existing photobook tests to check for regressions**

```bash
uv run pytest tests/test_photobook/ -v
```
Expected: ALL existing tests PASS

- [ ] **Step 5: Run the full test suite**

```bash
uv run pytest tests/ -v
```
Expected: ALL tests PASS (no regressions)

- [ ] **Step 6: Commit**

```bash
git add app/nodes/render_photobook_node.py
git commit -m "feat: add image compression to photobook render node using shared utility"
```

---

### Task 6: Verify end-to-end with existing photobook and blog tests

**Files:**
- None (verification only)

- [ ] **Step 1: Run photobook renderer tests**

```bash
uv run pytest tests/test_photobook/test_renderer.py -v
```
Expected: ALL PASS

- [ ] **Step 2: Run photobook PDF tests**

```bash
uv run pytest tests/test_photobook/test_pdf.py -v
```
Expected: ALL PASS

- [ ] **Step 3: Run blog generator tests (must still pass after refactoring)**

```bash
uv run pytest tests/test_services/test_blog_generator.py -v
```
Expected: ALL PASS

- [ ] **Step 4: Run full suite one final time**

```bash
uv run pytest tests/ -v
```
Expected: ALL PASS, zero regressions
