# Calendar Rendering Fix — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Behebe schwarze Bildbereiche und Layout-Overflow im Fotokalender-Rendering durch 5-layer Fix (CSS-Stabilität, Slot-Dimensionen, Orientierungs-Matching, Smart Cropping, Validierung).

**Architecture:** Fünf unabhängige Layer, jede mit eigener Testabdeckung. Layer 1 ist ein reiner CSS-Hotfix. Layer 2 legt die Datenbasis (Slot-Aspect-Ratios). Layer 3 fügt Orientierungserkennung in month_assigner ein. Layer 4 nutzt Layer 2+3 für object-position im Renderer. Layer 5 validiert das HTML strukturell.

**Tech Stack:** Python 3.12, Pydantic, PIL (Pillow), CSS Grid, Pytest

**Spezifikation:** `docs/superpowers/specs/2026-05-19-calendar-rendering-fix-design.md`

---

### Task 1: Layer 1 — CSS-Stabilitätsfix

**Files:**
- Modify: `app/calendar/styles.css:23-77`

- [ ] **Step 1: Ändere `.calendar-page min-height` → `height`**

Zeile 25 in `app/calendar/styles.css`:
```css
/* Vorher (Zeile 25) */
  min-height: 210mm;
/* Nachher */
  height: 210mm;
```

- [ ] **Step 2: Füge `min-height: 0` und `min-width: 0` auf Grid-Items hinzu**

Zeilen 71-77 in `app/calendar/styles.css`:
```css
/* Vorher */
.image-area img,
.image-area .slot-placeholder {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
/* Nachher */
.image-area img,
.image-area .slot-placeholder {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
  min-height: 0;
  min-width: 0;
}
```

- [ ] **Step 3: Schreibe Tests für die CSS-Änderungen**

Ergänze `tests/test_calendar/test_renderer.py`:

```python
class TestCalendarPageCss:
    """Layer 1: CSS-Stabilitätsfix."""

    @pytest.mark.unit
    def test_calendar_page_has_fixed_height(self):
        """.calendar-page hat height: 210mm (nicht min-height)."""
        css_path = os.path.join(
            os.path.dirname(__file__), "..", "..",
            "app", "calendar", "styles.css",
        )
        css = Path(css_path).read_text()
        # Extrahiere den .calendar-page Block
        assert "height: 210mm" in css
        assert "min-height: 210mm" not in css

    @pytest.mark.unit
    def test_grid_items_have_min_height_zero(self):
        """.image-area img und .slot-placeholder haben min-height: 0."""
        css_path = os.path.join(
            os.path.dirname(__file__), "..", "..",
            "app", "calendar", "styles.css",
        )
        css = Path(css_path).read_text()
        # Der kombinierte Selektor muss min-height: 0 enthalten
        assert ".image-area img," in css
        # Prüfe dass min-height: 0 im Block nach dem Selektor steht
        img_block_start = css.index(".image-area img,")
        img_block_end = css.index("}", css.index("{", img_block_start) + 1)
        img_block = css[img_block_start:img_block_end]
        assert "min-height: 0" in img_block
        assert "min-width: 0" in img_block
```

Füge den Import oben in der Datei hinzu:
```python
import os
from pathlib import Path
```

- [ ] **Step 4: Führe die neuen Tests aus**

Run: `uv run pytest tests/test_calendar/test_renderer.py::TestCalendarPageCss -v`
Expected: 2 PASS

- [ ] **Step 5: Führe alle bestehenden Tests aus (Regression)**

Run: `uv run pytest tests/test_calendar/ -v`
Expected: Alle bestehenden 34 Tests + 2 neue = 36 PASS

- [ ] **Step 6: Commit**

```bash
git add app/calendar/styles.css tests/test_calendar/test_renderer.py
git commit -m "fix(layer1): change min-height to fixed height, add min-height:0 on grid items"
```

---

### Task 2: Layer 2 — Slot-Dimensionen

**Files:**
- Modify: `app/calendar/layouts.py`
- Modify: `tests/test_calendar/test_layouts.py`
- Create: `tests/test_calendar/test_slot_dimensions.py`

- [ ] **Step 1: Ergänze `SlotDimensions`-Dataclass und `SLOT_DIMENSIONS` in `layouts.py`**

Ergänze nach der `get_total_image_slots()`-Funktion (Ende der Datei):

```python
from dataclasses import dataclass


@dataclass
class SlotDimensions:
    """Berechnete Slot-Maße aus dem CSS-Grid-Layout.

    width_ratio:  Anteil an der image-area-Breite (0..1)
    height_ratio: Anteil an der image-area-Höhe (0..1)
    aspect_ratio: width_ratio / height_ratio * IMAGE_AREA_ASPECT
                  (>1.5 = breit, <0.67 = hoch, sonst quadratisch)
    """
    width_ratio: float
    height_ratio: float
    aspect_ratio: float


# Die image-area hat in der Landscape-Seite (297×210mm) etwa
# folgende Maße nach Abzug von Header (~16mm) und Tagesraster (~35mm):
#   Breite: ~295mm, Höhe: ~159mm → Aspect Ratio ≈ 1.86
IMAGE_AREA_ASPECT_RATIO = 1.86


def _compute_aspect(w: float, h: float) -> float:
    """Berechnet den Slot-Aspekt aus Grid-Fraktionen."""
    if h == 0:
        return float("inf")
    return (w / h) * IMAGE_AREA_ASPECT_RATIO


# Mapping: preset_id → {slot_id: SlotDimensions}
SLOT_DIMENSIONS: dict[str, dict[str, SlotDimensions]] = {
    "cal_single_full": {
        "img": SlotDimensions(1.0, 1.0, _compute_aspect(1.0, 1.0)),
    },
    "cal_double_side": {
        "left":  SlotDimensions(0.5, 1.0, _compute_aspect(0.5, 1.0)),
        "right": SlotDimensions(0.5, 1.0, _compute_aspect(0.5, 1.0)),
    },
    "cal_double_stacked": {
        "top":    SlotDimensions(1.0, 2/3, _compute_aspect(1.0, 2/3)),
        "bottom": SlotDimensions(1.0, 1/3, _compute_aspect(1.0, 1/3)),
    },
    "cal_triple_big_top": {
        "big": SlotDimensions(1.0, 2/3, _compute_aspect(1.0, 2/3)),
        "sl":  SlotDimensions(0.5, 1/3, _compute_aspect(0.5, 1/3)),
        "sr":  SlotDimensions(0.5, 1/3, _compute_aspect(0.5, 1/3)),
    },
    "cal_triple_row": {
        "l": SlotDimensions(1/3, 1.0, _compute_aspect(1/3, 1.0)),
        "m": SlotDimensions(1/3, 1.0, _compute_aspect(1/3, 1.0)),
        "r": SlotDimensions(1/3, 1.0, _compute_aspect(1/3, 1.0)),
    },
    "cal_triple_stacked": {
        "big":    SlotDimensions(2/3, 1.0, _compute_aspect(2/3, 1.0)),
        "top":    SlotDimensions(1/3, 0.5, _compute_aspect(1/3, 0.5)),
        "bottom": SlotDimensions(1/3, 0.5, _compute_aspect(1/3, 0.5)),
    },
    "cal_triple_lshape": {
        "main":   SlotDimensions(2/3, 1.0, _compute_aspect(2/3, 1.0)),
        "top":    SlotDimensions(1/3, 0.5, _compute_aspect(1/3, 0.5)),
        "bottom": SlotDimensions(1/3, 0.5, _compute_aspect(1/3, 0.5)),
    },
    "cal_quad_grid": {
        "tl": SlotDimensions(0.5, 0.5, _compute_aspect(0.5, 0.5)),
        "tr": SlotDimensions(0.5, 0.5, _compute_aspect(0.5, 0.5)),
        "bl": SlotDimensions(0.5, 0.5, _compute_aspect(0.5, 0.5)),
        "br": SlotDimensions(0.5, 0.5, _compute_aspect(0.5, 0.5)),
    },
    "cal_quad_big_left": {
        "big": SlotDimensions(2/3, 1.0, _compute_aspect(2/3, 1.0)),
        "rt":  SlotDimensions(1/3, 1/3, _compute_aspect(1/3, 1/3)),
        "rm":  SlotDimensions(1/3, 1/3, _compute_aspect(1/3, 1/3)),
        "rb":  SlotDimensions(1/3, 1/3, _compute_aspect(1/3, 1/3)),
    },
    "cal_quad_panorama": {
        "wide": SlotDimensions(1.0, 2/3, _compute_aspect(1.0, 2/3)),
        "bl":   SlotDimensions(1/3, 1/3, _compute_aspect(1/3, 1/3)),
        "bm":   SlotDimensions(1/3, 1/3, _compute_aspect(1/3, 1/3)),
        "br":   SlotDimensions(1/3, 1/3, _compute_aspect(1/3, 1/3)),
    },
    "cal_quad_two_big": {
        "tl": SlotDimensions(0.5, 2/3, _compute_aspect(0.5, 2/3)),
        "tr": SlotDimensions(0.5, 2/3, _compute_aspect(0.5, 2/3)),
        "bl": SlotDimensions(0.5, 1/3, _compute_aspect(0.5, 1/3)),
        "br": SlotDimensions(0.5, 1/3, _compute_aspect(0.5, 1/3)),
    },
    "cal_cover": {
        "cover_img": SlotDimensions(1.0, 1.0, _compute_aspect(1.0, 1.0)),
    },
}
```

- [ ] **Step 2: Schreibe Tests für Slot-Dimensionen**

Erstelle `tests/test_calendar/test_slot_dimensions.py`:

```python
"""Layer 2: Slot-Dimensionen und Aspekt-Verhältnisse."""
import pytest
from app.calendar.layouts import (
    CALENDAR_LAYOUT_SEQUENCE,
    SLOT_DIMENSIONS,
    SlotDimensions,
    IMAGE_AREA_ASPECT_RATIO,
)


class TestSlotDimensionsExist:
    @pytest.mark.unit
    def test_all_presets_have_dimensions(self):
        """Alle 13 Presets aus CALENDAR_LAYOUT_SEQUENCE sind in SLOT_DIMENSIONS."""
        for _, preset_id in CALENDAR_LAYOUT_SEQUENCE:
            assert preset_id in SLOT_DIMENSIONS, (
                f"Preset {preset_id} fehlt in SLOT_DIMENSIONS"
            )

    @pytest.mark.unit
    def test_slot_ids_match_preset_slots(self):
        """Jeder Slot in SLOT_DIMENSIONS entspricht den Preset-JSON-Slots."""
        import os
        from app.shared.preset_loader import load_preset

        presets_dir = os.path.join(
            os.path.dirname(__file__), "..", "..",
            "app", "calendar", "preset_data",
        )
        for _, preset_id in CALENDAR_LAYOUT_SEQUENCE:
            preset = load_preset(preset_id, presets_dir)
            dims = SLOT_DIMENSIONS[preset_id]
            json_slot_ids = {s.id for s in preset.slots if s.type == "image"}
            dim_slot_ids = set(dims.keys())
            assert json_slot_ids == dim_slot_ids, (
                f"{preset_id}: JSON={json_slot_ids}, DIMS={dim_slot_ids}"
            )


class TestSlotAspectRatios:
    @pytest.mark.unit
    def test_double_stacked_top_is_wide(self):
        """cal_double_stacked top slot ist breit (>1.5)."""
        top = SLOT_DIMENSIONS["cal_double_stacked"]["top"]
        assert top.aspect_ratio > 1.5, f"Erwartet >1.5, ist {top.aspect_ratio}"

    @pytest.mark.unit
    def test_double_stacked_bottom_is_ultra_wide(self):
        """cal_double_stacked bottom slot ist sehr breit (>3.0)."""
        bottom = SLOT_DIMENSIONS["cal_double_stacked"]["bottom"]
        assert bottom.aspect_ratio > 3.0, f"Erwartet >3.0, ist {bottom.aspect_ratio}"

    @pytest.mark.unit
    def test_triple_row_slots_are_tall(self):
        """cal_triple_row slots sind hochformatig (<0.67)."""
        for slot_id in ["l", "m", "r"]:
            slot = SLOT_DIMENSIONS["cal_triple_row"][slot_id]
            assert slot.aspect_ratio < 0.67, (
                f"{slot_id}: Erwartet <0.67, ist {slot.aspect_ratio}"
            )

    @pytest.mark.unit
    def test_double_side_slots_are_squareish(self):
        """cal_double_side slots sind etwa quadratisch (0.67–1.5)."""
        for slot_id in ["left", "right"]:
            slot = SLOT_DIMENSIONS["cal_double_side"][slot_id]
            assert 0.67 <= slot.aspect_ratio <= 1.5, (
                f"{slot_id}: Erwartet 0.67–1.5, ist {slot.aspect_ratio}"
            )

    @pytest.mark.unit
    def test_quad_big_left_right_slots_are_wide(self):
        """cal_quad_big_left rechte Slots sind breit (>1.5)."""
        for slot_id in ["rt", "rm", "rb"]:
            slot = SLOT_DIMENSIONS["cal_quad_big_left"][slot_id]
            assert slot.aspect_ratio > 1.5, (
                f"{slot_id}: Erwartet >1.5, ist {slot.aspect_ratio}"
            )

    @pytest.mark.unit
    def test_all_aspect_ratios_positive(self):
        """Alle Aspekt-Verhältnisse sind >0 und endlich."""
        for preset_id, slots in SLOT_DIMENSIONS.items():
            for slot_id, dims in slots.items():
                assert dims.aspect_ratio > 0, (
                    f"{preset_id}/{slot_id}: aspekt={dims.aspect_ratio}"
                )
                assert dims.aspect_ratio != float("inf"), (
                    f"{preset_id}/{slot_id}: aspekt=inf"
                )

    @pytest.mark.unit
    def test_slot_classification(self):
        """Hilfsfunktion zum Klassifizieren von Slots."""
        def classify(ratio: float) -> str:
            if ratio > 1.5:
                return "wide"
            elif ratio < 0.67:
                return "tall"
            return "square"

        # cal_single_full: ganzes Bild → breit
        assert classify(SLOT_DIMENSIONS["cal_single_full"]["img"].aspect_ratio) == "wide"

        # cal_triple_row: 3 Spalten → hoch
        assert classify(SLOT_DIMENSIONS["cal_triple_row"]["l"].aspect_ratio) == "tall"

        # cal_double_side: 2 Spalten nebeneinander → quadratisch
        assert classify(SLOT_DIMENSIONS["cal_double_side"]["left"].aspect_ratio) == "square"

        # cal_quad_grid: 2×2 → breit (Landscape)
        assert classify(SLOT_DIMENSIONS["cal_quad_grid"]["tl"].aspect_ratio) == "wide"
```

- [ ] **Step 3: Führe die neuen Tests aus**

Run: `uv run pytest tests/test_calendar/test_slot_dimensions.py -v`
Expected: 6 PASS

- [ ] **Step 4: Führe alle bestehenden Tests aus (Regression)**

Run: `uv run pytest tests/test_calendar/ -v`
Expected: Alle bestehenden + neue = 42 PASS

- [ ] **Step 5: Commit**

```bash
git add app/calendar/layouts.py tests/test_calendar/test_slot_dimensions.py
git commit -m "feat(layer2): add SlotDimensions dataclass and SLOT_DIMENSIONS mapping"
```

---

### Task 3: Layer 3 — Orientierungserkennung und -Matching

**Files:**
- Create: `app/calendar/orientation.py` (neue Utility-Datei)
- Modify: `app/calendar/month_assigner.py:1-215`
- Modify: `app/calendar/pipeline.py:1-80`
- Modify: `tests/test_calendar/test_month_assigner.py`
- Create: `tests/test_calendar/test_orientation.py`

- [ ] **Step 1: Erstelle `app/calendar/orientation.py`**

```python
"""Orientierungserkennung für Bilder (Landscape/Portrait/Square)."""
from typing import Optional

from PIL import Image


def get_orientation(image_path: str) -> str:
    """Ermittelt die Bildorientierung.

    Verwendet PIL Image.open() und EXIF-Orientierungs-Tag.
    Gibt 'landscape', 'portrait' oder 'square' zurück.
    """
    try:
        img = Image.open(image_path)
        # EXIF Orientation Tag (0x0112) prüfen
        exif = img._getexif()
        if exif:
            orientation = exif.get(0x0112, 1)
            # Orientierungen 5-8 bedeuten 90°/270° gedreht → vertauscht Breite/Höhe
            if orientation in (5, 6, 7, 8):
                # Effektive Breite/Höhe sind vertauscht
                w, h = img.size[1], img.size[0]
            else:
                w, h = img.size
        else:
            w, h = img.size

        if w > h:
            return "landscape"
        elif h > w:
            return "portrait"
        return "square"
    except Exception:
        return "landscape"  # Fallback: meistens Querformat


def get_orientations(image_paths: list[str]) -> list[str]:
    """Ermittelt Orientierungen für eine Liste von Bildpfaden."""
    return [get_orientation(p) for p in image_paths]
```

- [ ] **Step 2: Schreibe Tests für `orientation.py`**

Erstelle `tests/test_calendar/test_orientation.py`:

```python
"""Layer 3: Orientierungserkennung."""
import pytest
from PIL import Image
from app.calendar.orientation import get_orientation, get_orientations


@pytest.fixture
def landscape_img(tmp_path):
    p = tmp_path / "landscape.jpg"
    img = Image.new("RGB", (800, 600), color=(100, 150, 200))
    img.save(p, "JPEG")
    return str(p)


@pytest.fixture
def portrait_img(tmp_path):
    p = tmp_path / "portrait.jpg"
    img = Image.new("RGB", (600, 800), color=(200, 100, 150))
    img.save(p, "JPEG")
    return str(p)


@pytest.fixture
def square_img(tmp_path):
    p = tmp_path / "square.jpg"
    img = Image.new("RGB", (500, 500), color=(150, 200, 100))
    img.save(p, "JPEG")
    return str(p)


class TestGetOrientation:
    @pytest.mark.unit
    def test_landscape_image(self, landscape_img):
        assert get_orientation(landscape_img) == "landscape"

    @pytest.mark.unit
    def test_portrait_image(self, portrait_img):
        assert get_orientation(portrait_img) == "portrait"

    @pytest.mark.unit
    def test_square_image(self, square_img):
        assert get_orientation(square_img) == "square"

    @pytest.mark.unit
    def test_nonexistent_path_returns_landscape(self):
        """Fehlertoleranz: nicht existierende Datei → 'landscape'."""
        assert get_orientation("/tmp/nicht_existent_12345.jpg") == "landscape"

    @pytest.mark.unit
    def test_corrupt_file_returns_landscape(self, tmp_path):
        """Fehlertoleranz: korrupte Datei → 'landscape'."""
        p = tmp_path / "corrupt.jpg"
        p.write_text("not an image")
        assert get_orientation(str(p)) == "landscape"


class TestGetOrientations:
    @pytest.mark.unit
    def test_multiple_orientations(self, landscape_img, portrait_img, square_img):
        paths = [landscape_img, portrait_img, square_img]
        result = get_orientations(paths)
        assert result == ["landscape", "portrait", "square"]

    @pytest.mark.unit
    def test_empty_list(self):
        assert get_orientations([]) == []
```

- [ ] **Step 3: Führe die Orientation-Tests aus**

Run: `uv run pytest tests/test_calendar/test_orientation.py -v`
Expected: 7 PASS

- [ ] **Step 4: Ergänze `_build_assignment_prompt()` um Orientierungs-Tags**

In `app/calendar/month_assigner.py`, füge einen neuen Parameter `orientations: Optional[list[str]] = None` hinzu:

Ändere die Zeilen 33-71 wie folgt:

```python
def _build_assignment_prompt(
    selected_photos: list[tuple[str, str]],  # (filename, exif_date_or_empty)
    year: int,
    preset_criteria: str,
    custom_instructions: Optional[str] = None,
    orientations: Optional[list[str]] = None,  # NEU
) -> str:
    if orientations and len(orientations) == len(selected_photos):
        photos_text = "\n".join(
            f"  {i}: {fname}"
            + (f" (EXIF: {date})" if date else "")
            + f" ({orientations[i].upper()})"  # NEU
            for i, (fname, date) in enumerate(selected_photos)
        )
    else:
        photos_text = "\n".join(
            f"  {i}: {fname}" + (f" (EXIF: {date})" if date else "")
            for i, (fname, date) in enumerate(selected_photos)
        )

    presets_dir = os.path.join(os.path.dirname(__file__), "preset_data")
    layout_lines = []
    for i, (month_name, preset_id) in enumerate(CALENDAR_LAYOUT_SEQUENCE):
        preset = load_preset(preset_id, presets_dir)
        # Füge Slot-Orientierungshinweise hinzu
        from app.calendar.layouts import SLOT_DIMENSIONS
        dims = SLOT_DIMENSIONS.get(preset_id, {})
        orientations_hint = ""
        if dims:
            wide_slots = [sid for sid, d in dims.items() if d.aspect_ratio > 1.5]
            tall_slots = [sid for sid, d in dims.items() if d.aspect_ratio < 0.67]
            hints = []
            if wide_slots:
                hints.append(f"Breitslots ({', '.join(wide_slots)}): Querformat bevorzugen")
            if tall_slots:
                hints.append(f"Hochslots ({', '.join(tall_slots)}): Hochformat bevorzugen")
            if hints:
                orientations_hint = " [" + "; ".join(hints) + "]"
        layout_lines.append(
            f"  {i}: {month_name} → {preset_id} ({preset.image_count} Bilder){orientations_hint}"
        )

    extra = f"\nZusätzliche Anweisungen: {custom_instructions}" if custom_instructions else ""

    return (
        f"Erstelle einen Fotokalender für das Jahr {year}.\n\n"
        f"Auswahlkriterien: {preset_criteria}{extra}\n\n"
        f"Slot-Orientierungen beachten:\n"  # NEU
        f"- 'wide' Slots (Verhältnis > 1.5): bevorzuge Querformat-Fotos\n"  # NEU
        f"- 'tall' Slots (Verhältnis < 0.67): bevorzuge Hochformat-Fotos\n"  # NEU
        f"- 'square' Slots (0.67 ≤ Verhältnis ≤ 1.5): beide Formate ok\n\n"  # NEU
        f"Verfügbare Fotos ({len(selected_photos)}):\n{photos_text}\n\n"
        "Seiten-Layouts (fix):\n" + "\n".join(layout_lines) +
        "\n\n"
        "Weise jedem Layout-Slot ein Foto zu (0-basierter Index). "
        "Saisonale Passung beachten: Schnee/Winter → Januar/Dezember, "
        "Blumen/Grün → April/Mai, Sonne/Strand → Juli/August, "
        "Herbstfarben → Oktober/November.\n\n"
        "Antworte im Format:\n"
        "# Deckblatt\n"
        "  cover_img: 5\n"
        "# Januar\n"
        "  img: 12\n"
        "# Februar\n"
        "  left: 3, right: 8\n"
        "... (pro Seite alle Slots auffüllen)\n\n"
        "Keine Erklärung, nur die Zuweisungen."
    )
```

- [ ] **Step 5: Ergänze `_fallback_assignment()` um Orientierungs-Matching**

Ersetze die `_fallback_assignment`-Funktion (Zeilen 96-134) in `month_assigner.py`:

```python
def _fallback_assignment(
    selected_photos: list[ImageData],
    year: int,
    orientations: Optional[list[str]] = None,  # NEU
) -> list[CalendarMonthPage]:
    """Fallback: Orientierungs-bewusste Zuordnung.

    Teilt Fotos in Landscape/Portrait-Buckets und weist sie
    passend zu den Slot-Formaten zu.
    """
    presets_dir = os.path.join(os.path.dirname(__file__), "preset_data")

    if orientations and len(orientations) == len(selected_photos):
        landscapes = [i for i, o in enumerate(orientations) if o == "landscape"]
        portraits = [i for i, o in enumerate(orientations) if o == "portrait"]
        squares = [i for i, o in enumerate(orientations) if o == "square"]
    else:
        landscapes = list(range(len(selected_photos)))
        portraits = []
        squares = []

    all_indices = landscapes + squares + portraits  # Landscapes zuerst
    if not all_indices:
        all_indices = [0]

    from app.calendar.layouts import SLOT_DIMENSIONS

    pages = []
    landscape_ptr = 0
    portrait_ptr = 0
    square_ptr = 0

    def next_landscape():
        nonlocal landscape_ptr
        if landscapes:
            idx = landscapes[landscape_ptr % len(landscapes)]
            landscape_ptr += 1
            return idx
        # Fallback: nimm aus squares, dann portraits
        if squares:
            nonlocal square_ptr
            idx = squares[square_ptr % len(squares)]
            square_ptr += 1
            return idx
        return landscapes[0] if landscapes else all_indices[landscape_ptr % len(all_indices)]

    def next_portrait():
        nonlocal portrait_ptr
        if portraits:
            idx = portraits[portrait_ptr % len(portraits)]
            portrait_ptr += 1
            return idx
        if squares:
            nonlocal square_ptr
            idx = squares[square_ptr % len(squares)]
            square_ptr += 1
            return idx
        return all_indices[portrait_ptr % len(all_indices)]

    def next_square():
        nonlocal square_ptr
        if squares:
            idx = squares[square_ptr % len(squares)]
            square_ptr += 1
            return idx
        return all_indices[square_ptr % len(all_indices)]

    for month, preset_id in CALENDAR_LAYOUT_SEQUENCE:
        preset = load_preset(preset_id, presets_dir)
        dims = SLOT_DIMENSIONS.get(preset_id, {})
        slots = []
        for slot_def in preset.slots:
            if slot_def.type != "image":
                continue
            slot_dims = dims.get(slot_def.id)
            if slot_dims:
                if slot_dims.aspect_ratio > 1.5:
                    img_index = next_landscape()
                elif slot_dims.aspect_ratio < 0.67:
                    img_index = next_portrait()
                else:
                    img_index = next_square()
            else:
                img_index = all_indices[len(slots) % len(all_indices)]

            slots.append(MonthSlot(slot_id=slot_def.id, image_index=img_index))

        month_num = 0 if month == "Deckblatt" else MONTH_NAMES.index(month) + 1
        pages.append(CalendarMonthPage(
            month=month_num,
            month_name=month,
            preset_id=preset_id,
            slots=slots,
        ))

    return pages
```

- [ ] **Step 6: Passe `assign_photos_to_months()` an, um Orientierungen durchzureichen**

In `month_assigner.py`, ändere die Funktion `assign_photos_to_months` (ab Zeile 137):

```python
def assign_photos_to_months(
    selected_photos: list[ImageData],
    year: int,
    preset: str = "mixed",
    model: str = "gemma4:26b-ctx128k",
    base_url: str = OLLAMA_BASE_URL,
    custom_instructions: Optional[str] = None,
    orientations: Optional[list[str]] = None,  # NEU
) -> list[CalendarMonthPage]:
    """LLM-basierte Zuordnung von Fotos zu Kalender-Monaten und Slots."""
    if not selected_photos:
        logger.warning("Keine Fotos zur Auswahl, verwende Fallback ohne Bilder")
        return _fallback_assignment([], year)

    criteria = CALENDAR_PRESET_CRITERIA.get(preset, CALENDAR_PRESET_CRITERIA["mixed"])

    photo_list: list[tuple[str, str]] = []
    for img in selected_photos:
        fname = os.path.basename(img.path)
        date_str = ""
        dt = _parse_exif_date(img.timestamp)
        if dt:
            date_str = dt.strftime("%Y-%m-%d")
        photo_list.append((fname, date_str))

    prompt = _build_assignment_prompt(
        photo_list, year, criteria, custom_instructions,
        orientations=orientations,  # NEU
    )

    response = call_ollama(
        prompt,
        model=model,
        base_url=base_url,
        temperature=0.0,
        top_p=0.1,
        num_predict=4096,
        timeout=120,
        disable_thinking=True,
    )

    if response:
        content = strip_thinking_tokens(response)
        parsed = _parse_assignment_response(content)

        if parsed and len(parsed) >= 10:
            pages = _build_pages_from_parsed(parsed, selected_photos)
            if len(pages) == 13 and all(len(p.slots) > 0 for p in pages):
                return pages
            logger.info("LLM-Zuweisung unvollständig (%d Seiten), verwende Fallback", len(pages))

    logger.info("LLM-Zuweisung fehlgeschlagen, verwende Fallback")
    return _fallback_assignment(selected_photos, year, orientations=orientations)  # NEU
```

- [ ] **Step 7: Passe `pipeline.py` an, um Orientierungen zu berechnen und durchzureichen**

In `app/calendar/pipeline.py`, füge nach der Bildauswahl die Orientierungserkennung ein (nach Zeile 52):

```python
    logger.info("Stufe 1 abgeschlossen: %d Fotos ausgewählt", len(selected))

    # Orientierungen der ausgewählten Bilder ermitteln
    from app.calendar.orientation import get_orientations
    image_paths = [img.path for img in selected]
    orientations = get_orientations(image_paths)
    logger.info(
        "Orientierungen: %d landscape, %d portrait, %d square",
        orientations.count("landscape"),
        orientations.count("portrait"),
        orientations.count("square"),
    )

    logger.info("Stufe 2: Monats-Zuweisung")
    pages = assign_photos_to_months(
        selected_photos=selected,
        year=config.year,
        preset=config.preset,
        model=config.model,
        base_url=base_url,
        custom_instructions=config.custom_instructions,
        orientations=orientations,  # NEU
    )
```

- [ ] **Step 8: Ergänze Tests für Orientierungs-Matching**

Ergänze in `tests/test_calendar/test_month_assigner.py`:

```python
class TestBuildAssignmentPromptWithOrientations:
    @pytest.mark.unit
    def test_prompt_includes_orientation_tags(self):
        prompt = _build_assignment_prompt(
            selected_photos=[("test_1.jpg", "2024-06-15"), ("test_2.jpg", "2024-01-10")],
            year=2026,
            preset_criteria="landschaftliche Vielfalt",
            orientations=["landscape", "portrait"],
        )
        assert "(LANDSCAPE)" in prompt
        assert "(PORTRAIT)" in prompt

    @pytest.mark.unit
    def test_prompt_includes_orientation_instructions(self):
        prompt = _build_assignment_prompt(
            selected_photos=[("test_1.jpg", "2024-06-15")],
            year=2026,
            preset_criteria="test",
            orientations=["landscape"],
        )
        assert "Slot-Orientierungen beachten" in prompt
        assert "Querformat bevorzugen" in prompt or "wide" in prompt.lower()

    @pytest.mark.unit
    def test_prompt_without_orientations_no_tags(self):
        prompt = _build_assignment_prompt(
            selected_photos=[("test_1.jpg", "2024-06-15")],
            year=2026,
            preset_criteria="test",
            orientations=None,
        )
        assert "(LANDSCAPE)" not in prompt
        assert "(PORTRAIT)" not in prompt


class TestFallbackAssignmentWithOrientations:
    @pytest.mark.unit
    def test_landscapes_assigned_to_wide_slots(self):
        """Querformat-Fotos landen in Breitslots."""
        # Erstelle 30 Querformat- und 5 Hochformat-Bilder
        from PIL import Image
        import tempfile
        photos = []
        tmpdir = tempfile.mkdtemp()
        for i in range(30):
            p = f"{tmpdir}/landscape_{i}.jpg"
            img = Image.new("RGB", (800, 600))
            img.save(p, "JPEG")
            photos.append(ImageData(path=p, timestamp=f"2024:0{(i % 12) + 1}:15 10:00:00"))
        for i in range(5):
            p = f"{tmpdir}/portrait_{i}.jpg"
            img = Image.new("RGB", (600, 800))
            img.save(p, "JPEG")
            photos.append(ImageData(path=p, timestamp="2024:06:15 10:00:00"))

        orientations = []
        for img in photos:
            from PIL import Image as PILImg
            i = PILImg.open(img.path)
            orientations.append("landscape" if i.size[0] > i.size[1] else "portrait")

        pages = _fallback_assignment(photos, 2026, orientations=orientations)
        assert len(pages) == 13

        # Juni (cal_double_stacked) hat einen Breitslot (top) und einen Ultra-Breitslot (bottom)
        # Beide sollten mit Landscapes gefüllt sein
        june_page = [p for p in pages if p.month_name == "Juni"][0]
        june_orientations = []
        for slot in june_page.slots:
            june_orientations.append(orientations[slot.image_index])
        # Mindestens einer ist landscape (wenn genug Landscapes da sind)
        assert "landscape" in june_orientations

    @pytest.mark.unit
    def test_fallback_without_orientations_still_works(self):
        """Ohne Orientierungen: bestehendes Verhalten bleibt erhalten."""
        photos = [
            ImageData(path=f"/tmp/test_{i}.jpg", timestamp=f"2024:0{(i % 12) + 1}:15 10:00:00")
            for i in range(40)
        ]
        pages = _fallback_assignment(photos, 2026)
        assert len(pages) == 13
        # Alle Slots gefüllt
        for page in pages:
            assert len(page.slots) > 0
```

- [ ] **Step 9: Führe alle Tests aus**

Run: `uv run pytest tests/test_calendar/test_orientation.py tests/test_calendar/test_month_assigner.py -v`
Expected: Alle neuen + bestehenden = ~15 PASS (7 orientation + 9 bestehende month_assigner + 3 neue)

- [ ] **Step 10: Führe alle Calendar-Tests aus (Regression)**

Run: `uv run pytest tests/test_calendar/ -v`
Expected: Alle Tests grün

- [ ] **Step 11: Commit**

```bash
git add app/calendar/orientation.py app/calendar/month_assigner.py app/calendar/pipeline.py tests/test_calendar/test_orientation.py tests/test_calendar/test_month_assigner.py
git commit -m "feat(layer3): add orientation detection and orientation-aware month assignment"
```

---

### Task 4: Layer 4 — Smart Cropping (object-position)

**Files:**
- Modify: `app/calendar/renderer.py:1-134`
- Modify: `tests/test_calendar/test_renderer.py`
- Create: `tests/test_calendar/test_object_position.py`

- [ ] **Step 1: Schreibe Tests für `_get_object_position`**

Erstelle `tests/test_calendar/test_object_position.py`:

```python
"""Layer 4: object-position Berechnung."""
import pytest
from app.calendar.layouts import SlotDimensions, SLOT_DIMENSIONS


def _get_object_position(slot_dims: SlotDimensions, image_orientation: str) -> str:
    """Bestimmt den object-position Wert basierend auf Slot-Format und Bild-Orientierung."""
    if slot_dims.aspect_ratio > 1.5 and image_orientation == "portrait":
        return "center 30%"
    elif slot_dims.aspect_ratio > 1.5:
        return "center center"
    elif slot_dims.aspect_ratio < 0.67 and image_orientation == "landscape":
        return "30% center"
    else:
        return "center center"


class TestObjectPosition:
    @pytest.mark.unit
    def test_portrait_in_wide_slot(self):
        """Portrait-Bild in breitem Slot: obere Hälfte zeigen."""
        wide_slot = SLOT_DIMENSIONS["cal_double_stacked"]["top"]
        assert wide_slot.aspect_ratio > 1.5
        assert _get_object_position(wide_slot, "portrait") == "center 30%"

    @pytest.mark.unit
    def test_landscape_in_wide_slot(self):
        """Landscape in Breitslot: normal zentriert."""
        wide_slot = SLOT_DIMENSIONS["cal_double_stacked"]["top"]
        assert _get_object_position(wide_slot, "landscape") == "center center"

    @pytest.mark.unit
    def test_landscape_in_tall_slot(self):
        """Landscape in Hochslot: linke Hälfte zeigen."""
        tall_slot = SLOT_DIMENSIONS["cal_triple_row"]["l"]
        assert tall_slot.aspect_ratio < 0.67
        assert _get_object_position(tall_slot, "landscape") == "30% center"

    @pytest.mark.unit
    def test_portrait_in_tall_slot(self):
        """Portrait in Hochslot: normal zentriert."""
        tall_slot = SLOT_DIMENSIONS["cal_triple_row"]["l"]
        assert _get_object_position(tall_slot, "portrait") == "center center"

    @pytest.mark.unit
    def test_square_slot_always_center(self):
        """Quadratischer Slot: immer center center."""
        square_slot = SLOT_DIMENSIONS["cal_double_side"]["left"]
        assert 0.67 <= square_slot.aspect_ratio <= 1.5
        assert _get_object_position(square_slot, "landscape") == "center center"
        assert _get_object_position(square_slot, "portrait") == "center center"
        assert _get_object_position(square_slot, "square") == "center center"

    @pytest.mark.unit
    def test_square_image_always_center(self):
        """Square-Bild: immer center center, unabhängig vom Slot."""
        wide_slot = SLOT_DIMENSIONS["cal_double_stacked"]["top"]
        tall_slot = SLOT_DIMENSIONS["cal_triple_row"]["l"]
        assert _get_object_position(wide_slot, "square") == "center center"
        assert _get_object_position(tall_slot, "square") == "center center"
```

- [ ] **Step 2: Führe die object-position Tests aus**

Run: `uv run pytest tests/test_calendar/test_object_position.py -v`
Expected: 6 PASS

- [ ] **Step 3: Implementiere `_get_object_position` in `renderer.py` und integriere es**

Füge am Anfang von `app/calendar/renderer.py` (nach den Imports) hinzu:

```python
from typing import Optional
from app.calendar.layouts import SLOT_DIMENSIONS, SlotDimensions


def _get_object_position(slot_dims: Optional[SlotDimensions], image_orientation: str) -> str:
    """Bestimmt den object-position Wert basierend auf Slot-Format und Bild-Orientierung.

    Bei extremer Fehlpassung (Portrait in ultrawide, Landscape in tall)
    wird der sichtbare Ausschnitt verschoben, um einen interessanteren
    Bildbereich zu zeigen.
    """
    if slot_dims is None:
        return "center center"
    if slot_dims.aspect_ratio > 1.5 and image_orientation == "portrait":
        return "center 30%"   # Portrait in Breitslot: zeige oberen Teil
    elif slot_dims.aspect_ratio > 1.5:
        return "center center"
    elif slot_dims.aspect_ratio < 0.67 and image_orientation == "landscape":
        return "30% center"   # Landscape in Hochslot: zeige linken Teil
    else:
        return "center center"
```

Ändere die Signatur von `render_calendar` (Zeile 40):

```python
def render_calendar(
    pages: List[CalendarMonthPage],
    year: int,
    image_paths: List[str],
    image_orientations: Optional[List[str]] = None,  # NEU
) -> str:
```

Und reiche `image_orientations` an die Subfunktionen durch.

Ändere `_render_month_page`-Signatur (Zeile 87):

```python
def _render_month_page(
    page: CalendarMonthPage,
    year: int,
    image_paths: List[str],
    presets_dir: str,
    image_orientations: Optional[List[str]] = None,  # NEU
) -> str:
```

Ändere die Bild-Rendering-Logik in `_render_month_page` (Zeilen 107-125):

```python
    slot_defs = {s.id: s for s in preset.slots}
    slot_dims = SLOT_DIMENSIONS.get(page.preset_id, {})
    for slot_data in page.slots:
        slot_def = slot_defs.get(slot_data.slot_id)
        if not slot_def or slot_def.type != "image":
            continue

        idx = slot_data.image_index
        orientation = (
            image_orientations[idx]
            if image_orientations and 0 <= idx < len(image_orientations)
            else "landscape"
        )
        dims = slot_dims.get(slot_data.slot_id)
        obj_pos = _get_object_position(dims, orientation)

        if obj_pos != "center center":
            area_style = (
                f'style="grid-area: {slot_def.css_area}; '
                f'object-position: {obj_pos}"'
            )
        else:
            area_style = f'style="grid-area: {slot_def.css_area}"'

        if 0 <= idx < len(image_paths):
            img_path = _normalize_path(image_paths[idx])
            parts.append(
                f'<img class="slot-image" {area_style} '
                f'src="{html_mod.escape(img_path)}" alt="Foto">'
            )
        else:
            parts.append(
                f'<div class="slot-placeholder" style="grid-area: {slot_def.css_area}">'
                f'Bild nicht verfügbar</div>'
            )
```

Rufe `_render_month_page` mit Orientierungen auf (in `render_calendar`, Zeile 53):

```python
            parts.append(_render_month_page(page, year, image_paths, presets_dir, image_orientations))
```

- [ ] **Step 4: Ergänze Renderer-Tests für object-position**

Ergänze in `tests/test_calendar/test_renderer.py`:

```python
class TestObjectPositionInHtml:
    @pytest.mark.unit
    def test_renderer_accepts_orientations(self, sample_data):
        """Renderer akzeptiert und verarbeitet image_orientations."""
        pages, img_paths = sample_data
        html = render_calendar(
            pages, year=2026, image_paths=img_paths,
            image_orientations=["landscape", "portrait", "square"],
        )
        assert "<!DOCTYPE html>" in html

    @pytest.mark.unit
    def test_object_position_in_output_for_mismatch(self, tmp_path):
        """Bei Orientation-Fehlpassung erscheint object-position im HTML."""
        from PIL import Image
        from app.calendar.models import CalendarMonthPage, MonthSlot

        # Erstelle ein Portrait-Bild
        p = tmp_path / "portrait.jpg"
        img = Image.new("RGB", (600, 800))
        img.save(p, "JPEG")
        img_paths = [str(p)]

        # Juni hat cal_double_stacked mit Breitslots
        page = CalendarMonthPage(
            month=6, month_name="Juni", preset_id="cal_double_stacked",
            slots=[
                MonthSlot(slot_id="top", image_index=0),
                MonthSlot(slot_id="bottom", image_index=0),
            ],
        )

        html = render_calendar(
            [page], year=2026, image_paths=img_paths,
            image_orientations=["portrait"],
        )
        # Portrait in Breitslot → object-position: center 30%
        assert "object-position: center 30%" in html

    @pytest.mark.unit
    def test_no_object_position_for_good_match(self, tmp_path):
        """Bei guter Passung (Landscape in Breitslot) kein object-position."""
        from PIL import Image
        from app.calendar.models import CalendarMonthPage, MonthSlot

        p = tmp_path / "landscape.jpg"
        img = Image.new("RGB", (800, 600))
        img.save(p, "JPEG")
        img_paths = [str(p)]

        page = CalendarMonthPage(
            month=6, month_name="Juni", preset_id="cal_double_stacked",
            slots=[MonthSlot(slot_id="top", image_index=0)],
        )

        html = render_calendar(
            [page], year=2026, image_paths=img_paths,
            image_orientations=["landscape"],
        )
        # Landscape in Breitslot → center center (= Default, nicht explizit gesetzt)
        assert "object-position" not in html
```

- [ ] **Step 5: Führe alle Renderer-Tests aus**

Run: `uv run pytest tests/test_calendar/test_renderer.py tests/test_calendar/test_object_position.py -v`
Expected: Alle neuen + bestehenden = 11 PASS (5 bestehende + 3 neue Renderer + 3 Position)

- [ ] **Step 6: Passe `pipeline.py` an, um Orientierungen an den Renderer zu übergeben**

In `app/calendar/pipeline.py`, ändere den Renderer-Aufruf (Zeile 71):

```python
    logger.info("Rendering: HTML-Erzeugung")
    html = render_calendar(
        pages, config.year, image_paths,
        image_orientations=orientations,  # NEU
    )
```

- [ ] **Step 7: Führe alle Calendar-Tests aus (Regression)**

Run: `uv run pytest tests/test_calendar/ -v`
Expected: Alle Tests grün

- [ ] **Step 8: Commit**

```bash
git add app/calendar/renderer.py app/calendar/pipeline.py tests/test_calendar/test_renderer.py tests/test_calendar/test_object_position.py
git commit -m "feat(layer4): add orientation-aware object-position for smart image cropping"
```

---

### Task 5: Layer 5 — HTML-Validator

**Files:**
- Create: `app/calendar/validator.py`
- Create: `tests/test_calendar/test_validator.py`
- Modify: `app/calendar/pipeline.py:1-80`

- [ ] **Step 1: Schreibe Tests für den Validator**

Erstelle `tests/test_calendar/test_validator.py`:

```python
"""Layer 5: HTML-Strukturvalidierung."""
import pytest
from app.calendar.validator import validate_calendar_html
from app.calendar.renderer import render_calendar
from app.calendar.models import CalendarMonthPage, MonthSlot


class TestValidateCalendarHtml:
    @pytest.mark.unit
    def test_valid_html_passes(self, tmp_path):
        """Korrektes HTML: keine Fehler."""
        from PIL import Image

        img_paths = []
        for i in range(35):
            p = tmp_path / f"img_{i}.jpg"
            img = Image.new("RGB", (200, 150))
            img.save(p, "JPEG")
            img_paths.append(str(p))

        pages = []
        for i in range(13):
            month = i
            month_name = "Deckblatt" if i == 0 else f"Monat {i}"
            preset_id = "cal_cover" if i == 0 else "cal_single_full"
            pages.append(CalendarMonthPage(
                month=month, month_name=month_name, preset_id=preset_id,
                slots=[MonthSlot(slot_id="cover_img" if i == 0 else "img", image_index=i)],
            ))

        html = render_calendar(pages, year=2026, image_paths=img_paths)
        issues = validate_calendar_html(html)
        assert len(issues) == 0, f"Unerwartete Issues: {issues}"

    @pytest.mark.unit
    def test_missing_pages_detected(self):
        """Weniger als 13 Seiten → Fehler."""
        html = """<!DOCTYPE html><html><body>
        <div class="calendar-page"></div>
        </body></html>"""
        issues = validate_calendar_html(html)
        assert any("Seiten" in i or "pages" in i.lower() or "page" in i.lower()
                   for i in issues)

    @pytest.mark.unit
    def test_slot_placeholder_detected(self):
        """slot-placeholder divs → Warnung."""
        html = """<!DOCTYPE html><html><body>
        <div class="calendar-page"><div class="slot-placeholder"></div></div>
        </body></html>"""
        issues = validate_calendar_html(html)
        assert any("placeholder" in i.lower() for i in issues), f"Issues: {issues}"

    @pytest.mark.unit
    def test_empty_html_returns_error(self):
        """Leeres HTML → Fehler."""
        issues = validate_calendar_html("")
        assert len(issues) > 0

    @pytest.mark.unit
    def test_duplicate_images_detected(self):
        """Doppelte image_index-Werte auf einer Seite → Warnung."""
        html = """<!DOCTYPE html><html><body>
        <div class="calendar-page">
          <div class="image-area cal-double-side">
            <img class="slot-image" style="grid-area: left" src="file:///tmp/1.jpg">
            <img class="slot-image" style="grid-area: right" src="file:///tmp/1.jpg">
          </div>
        </div>
        </body></html>"""
        issues = validate_calendar_html(html)
        # Duplikate werden durch gleiche src erkannt
        assert any("doppelt" in i.lower() or "duplicate" in i.lower()
                   for i in issues), f"Issues: {issues}"
```

- [ ] **Step 2: Führe die Validator-Tests aus (sollten fehlschlagen)**

Run: `uv run pytest tests/test_calendar/test_validator.py -v`
Expected: FAIL (ImportError — validator.py existiert noch nicht)

- [ ] **Step 3: Implementiere `app/calendar/validator.py`**

```python
"""Strukturelle HTML-Validierung für den Kalender (Layer 5)."""
import logging
import re

logger = logging.getLogger(__name__)


def validate_calendar_html(html_content: str) -> list[str]:
    """Prüft das gerenderte HTML auf strukturelle Probleme.

    Checked:
    - HTML nicht leer
    - 13 Seiten vorhanden (Cover + 12 Monate)
    - Jede Seite hat genau einen image-area (außer Cover?)
    - Keine slot-placeholder divs (indiziert fehlende Bilder)
    - Keine doppelten Bild-src innerhalb einer Seite

    Returns:
        Liste von Warnungen/Fehlern (leer = alles ok).
    """
    issues = []

    if not html_content or not html_content.strip():
        return ["HTML-Inhalt ist leer"]

    # 13 Seiten prüfen
    page_count = html_content.count('class="calendar-page')
    if page_count != 13:
        issues.append(f"Erwartet 13 Seiten, gefunden: {page_count}")

    # slot-placeholder prüfen
    placeholder_count = html_content.count("slot-placeholder")
    if placeholder_count > 0:
        issues.append(
            f"{placeholder_count} slot-placeholder(s) gefunden — "
            f"fehlende Bilder"
        )

    # Doppelte Bilder pro Seite prüfen
    pages = html_content.split('class="calendar-page')
    for i, page in enumerate(pages[1:], start=1):  # erstes Element ist vor der ersten Seite
        # Extrahiere alle src-Attribute aus img-Tags
        img_srcs = re.findall(r'<img[^>]+src="([^"]+)"', page)
        seen = set()
        duplicates = set()
        for src in img_srcs:
            if src in seen:
                duplicates.add(src)
            seen.add(src)
        if duplicates:
            issues.append(
                f"Seite {i}: {len(duplicates)} doppelte(s) Bild(er) — "
                f"{', '.join(list(duplicates)[:3])}"
            )

    if issues:
        logger.warning("Kalender-HTML-Validierung: %d Problem(e)", len(issues))
        for issue in issues:
            logger.warning("  - %s", issue)
    else:
        logger.info("Kalender-HTML-Validierung: OK (13 Seiten, keine Platzhalter)")

    return issues
```

- [ ] **Step 4: Führe die Validator-Tests aus**

Run: `uv run pytest tests/test_calendar/test_validator.py -v`
Expected: 5 PASS

- [ ] **Step 5: Integriere den Validator in die Pipeline**

In `app/calendar/pipeline.py`, füge nach dem Rendering (nach Zeile 71) ein:

```python
    # Validierung (Layer 5)
    from app.calendar.validator import validate_calendar_html
    validation_issues = validate_calendar_html(html)
    if validation_issues:
        logger.warning(
            "Kalender-Validierung: %d Problem(e) gefunden",
            len(validation_issues),
        )
```

- [ ] **Step 6: Führe alle Calendar-Tests aus (Final Regression)**

Run: `uv run pytest tests/test_calendar/ -v`
Expected: Alle ~50+ Tests grün

- [ ] **Step 7: Commit**

```bash
git add app/calendar/validator.py app/calendar/pipeline.py tests/test_calendar/test_validator.py
git commit -m "feat(layer5): add HTML structure validator for calendar"
```

---

### Task 6: Integrationstest und finale Regression

**Files:**
- Modify: `tests/test_calendar/test_integration.py`

- [ ] **Step 1: Ergänze Integrationstests**

Ergänze in `tests/test_calendar/test_integration.py`:

```python
    @pytest.mark.integration
    def test_pipeline_passes_validation(self, many_images):
        """Pipeline-Output besteht die Validierung."""
        config = CalendarConfig(preset="mixed", year=2026)
        result = run_calendar_pipeline(
            images=many_images,
            config=config,
            base_url="http://localhost:99999",
        )
        from app.calendar.validator import validate_calendar_html
        issues = validate_calendar_html(result.html_content)
        # slot-placeholder sind ok im Fallback (keine echten Bilder im Test)
        critical = [i for i in issues if "placeholder" not in i.lower()]
        assert len(critical) == 0, f"Kritische Issues: {critical}"

    @pytest.mark.integration
    def test_no_slot_placeholders_with_enough_images(self, many_images):
        """Mit genug Bildern: keine slot-placeholder."""
        # Verwende die ersten 35 Bilder (genau genug für 35 Slots)
        images = many_images[:35]
        config = CalendarConfig(preset="mixed", year=2026)
        result = run_calendar_pipeline(
            images=images,
            config=config,
            base_url="http://localhost:99999",
        )
        assert "slot-placeholder" not in result.html_content

    @pytest.mark.integration
    def test_orientation_data_flows_through_pipeline(self, tmp_path):
        """Orientierungen werden korrekt durch die Pipeline gereicht."""
        from PIL import Image
        from app.calendar.orientation import get_orientation

        paths = []
        # Erstelle gemischte Orientierungen
        for i in range(40):
            p = tmp_path / f"photo_{i:03d}.jpg"
            # Abwechselnd landscape (800x600) und portrait (600x800)
            if i % 3 == 0:
                img = Image.new("RGB", (600, 800))
            else:
                img = Image.new("RGB", (800, 600))
            img.save(p, "JPEG")
            paths.append(str(p))

        images = [ImageData(path=p) for p in paths]
        config = CalendarConfig(preset="mixed", year=2026)

        result = run_calendar_pipeline(
            images=images,
            config=config,
            base_url="http://localhost:99999",
        )

        assert len(result.pages) == 13
        assert result.html_content != ""
        # Prüfe dass das HTML keine strukturellen Fehler hat
        from app.calendar.validator import validate_calendar_html
        issues = validate_calendar_html(result.html_content)
        critical = [i for i in issues if "placeholder" not in i.lower()]
        assert len(critical) == 0, f"Kritische Issues: {critical}"
```

- [ ] **Step 2: Führe Integrationstests aus**

Run: `uv run pytest tests/test_calendar/test_integration.py -v -m integration`
Expected: Alle Tests PASS (4 bestehende + 3 neue = 7)

- [ ] **Step 3: Führe den kompletten Test-Suite aus**

Run: `uv run pytest tests/test_calendar/ -v`
Expected: Alle Tests grün

- [ ] **Step 4: Führe alle Unit-Tests des Projekts aus (Regression)**

Run: `uv run pytest tests/ -v -m "not e2e"`
Expected: Keine Regressionen

- [ ] **Step 5: Commit**

```bash
git add tests/test_calendar/test_integration.py
git commit -m "test: add integration tests for orientation flow and validation"
```

---

## Zusammenfassung der Änderungen

| Datei | Änderung | Layer |
|-------|----------|-------|
| `app/calendar/styles.css` | `height: 210mm`, `min-height: 0` auf Grid-Items | 1 |
| `app/calendar/layouts.py` | `SlotDimensions` + `SLOT_DIMENSIONS` | 2 |
| `app/calendar/orientation.py` | **NEU** `get_orientation()`, `get_orientations()` | 3 |
| `app/calendar/month_assigner.py` | Orientierungs-Tags im Prompt, orientation-aware Fallback | 3 |
| `app/calendar/renderer.py` | `_get_object_position()`, object-position in img-Tags | 4 |
| `app/calendar/validator.py` | **NEU** `validate_calendar_html()` | 5 |
| `app/calendar/pipeline.py` | Orientierungserkennung, Validator-Aufruf | 3,4,5 |
| `tests/test_calendar/test_renderer.py` | Neue CSS-Tests, object-position-Tests | 1,4 |
| `tests/test_calendar/test_slot_dimensions.py` | **NEU** | 2 |
| `tests/test_calendar/test_orientation.py` | **NEU** | 3 |
| `tests/test_calendar/test_month_assigner.py` | Orientierungs-Tests | 3 |
| `tests/test_calendar/test_object_position.py` | **NEU** | 4 |
| `tests/test_calendar/test_validator.py` | **NEU** | 5 |
| `tests/test_calendar/test_integration.py` | Neue Integrationstests | Alle |
