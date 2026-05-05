# Photobook Preset Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace 8 free-form templates with 21 fixed preset layouts featuring hard-coded text constraints (font size + character limits), LLM preset selection, and validator-enforced variety.

**Architecture:** Two LLM passes remain (Pass 1: preset selection, Pass 2: slot filling), but the LLM's freedom is drastically reduced. Preset JSONs define image slots, text slots with `char_limit`/`font_size`/`text_role`, and CSS grid areas. The validator enforces variety (no back-to-back repeats, min 5 unique presets) and truncates overflow text.

**Tech Stack:** Python 3.12, Pydantic, Ollama (multimodal), CSS Grid, pytest

---

## File Map

| File | Action | Purpose |
|---|---|---|
| `app/photobook/presets/*.json` | **Create 21 files** | Preset layout definitions with text constraints |
| `app/photobook/preset_loader.py` | **Create** | Load presets into Pydantic models with extended SlotDefinition |
| `app/photobook/presets.py` | **Create** | Preset data (name, image_count, has_text for each preset ID) for LLM prompts |
| `app/photobook/styles.css` | **Modify** | 21 new `preset-*` CSS grid classes, remove old 8 `layout-*` classes |
| `app/photobook/plan.py` | **Modify** | Prompt: preset catalog + variety rules; output: `preset_id`; fallback adapted |
| `app/photobook/generate.py` | **Modify** | Prompt: constraint table; output: text within limits; fallback adapted |
| `app/photobook/validator.py` | **Modify** | New: char-limit overflow truncation, variety checks (cover, back-to-back, text-gap, image-count monotony, total variety) |
| `app/photobook/renderer.py` | **Modify** | Font-size from slot definition; no template lookup needed |
| `app/state.py` | **Modify** | Updated `SlotDefinition` with `char_limit`, `font_size`, `text_role` |
| `tests/test_photobook/test_presets.py` | **Create** | Preset loading + slot validation tests |
| `tests/test_photobook/test_variety.py` | **Create** | Variety enforcement tests |
| `tests/test_photobook/test_text_overflow.py` | **Create** | Text truncation tests |
| `app/photobook/templates/*.json` | **Delete 8 files** | Old template system removed |
| `app/photobook/template_loader.py` | **Delete** | Replaced by preset_loader.py |

---

### Task 1: Create preset directory and updated SlotDefinition model

**Files:**
- Create: `app/photobook/presets/__init__.py` (empty)
- Create: `app/photobook/preset_loader.py`
- Modify: `app/state.py` — add `char_limit`, `font_size`, `text_role` to `SlotDefinition` (if it lives there; check)

**Note:** The `SlotDefinition` class lives in `app/photobook/template_loader.py`. Since we are replacing that module, we define the updated model in the new `preset_loader.py`.

- [ ] **Step 1: Create presets directory**

```bash
mkdir -p app/photobook/presets
touch app/photobook/presets/__init__.py
```

- [ ] **Step 2: Write preset_loader.py with updated SlotDefinition**

Write `app/photobook/preset_loader.py`:

```python
"""Preset-Loader — lädt JSON-Presets und parst sie in Pydantic-Modelle."""
import json
from pathlib import Path
from typing import Dict, List, Optional
from pydantic import BaseModel

_PRESETS_DIR = Path(__file__).parent / "presets"


class SlotDefinition(BaseModel):
    """Ein einzelner Slot in einem Preset."""
    id: str
    type: str                          # "image" | "text"
    priority: Optional[str] = None     # "primary" | "secondary" | None
    css_area: str
    optional: bool = False
    char_limit: Optional[int] = None   # Zeichenlimit (nur für type="text")
    font_size: Optional[str] = None    # CSS font-size (nur für type="text")
    text_role: Optional[str] = None    # "title" | "caption" | "intro" (nur für type="text")


class Preset(BaseModel):
    """Ein Layout-Preset aus dem Katalog."""
    id: str
    name: str
    image_count: int
    has_text: bool
    description: str
    css_class: str
    slots: List[SlotDefinition]


def load_preset(preset_id: str) -> Preset:
    """Lädt ein einzelnes Preset aus dem Katalog."""
    path = _PRESETS_DIR / f"{preset_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"Preset '{preset_id}' nicht gefunden unter {path}")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return Preset(**data)


def load_all_presets() -> Dict[str, Preset]:
    """Lädt alle Presets aus dem Katalog."""
    presets = {}
    for path in sorted(_PRESETS_DIR.glob("*.json")):
        preset_id = path.stem
        presets[preset_id] = load_preset(preset_id)
    return presets


def get_preset_catalog_for_llm() -> str:
    """Erzeugt Kurzübersicht aller Presets für Pass-1-Prompt (nur ID, Bildanzahl, Text)."""
    lines = []
    for pid, p in load_all_presets().items():
        lines.append(f"  {pid}: {p.image_count} Bilder, Text={'ja' if p.has_text else 'nein'}")
    return "\n".join(lines)


def get_constraint_table_for_llm() -> str:
    """Erzeugt Text-Constraint-Tabelle für Pass-2-Prompt."""
    constraints = {}
    for preset in load_all_presets().values():
        for slot in preset.slots:
            if slot.type == "text" and slot.text_role:
                key = slot.text_role
                if key not in constraints:
                    constraints[key] = (slot.char_limit, slot.font_size)
    lines = ["TEXT-CONSTRAINTS:"]
    for role, (limit, size) in sorted(constraints.items()):
        lines.append(f"  {role}: max. {limit} Zeichen, Schriftgröße {size}")
    return "\n".join(lines)
```

- [ ] **Step 3: Write test for preset_loader (failing — no presets yet)**

Write `tests/test_photobook/test_presets.py`:

```python
"""Tests für den Preset-Loader."""
import pytest
from app.photobook.preset_loader import load_preset, load_all_presets


class TestPresetLoader:
    def test_load_all_presets_returns_non_empty_dict(self):
        """Nachdem alle Presets erstellt sind, muss load_all_presets() sie alle liefern."""
        presets = load_all_presets()
        assert isinstance(presets, dict)
        # 21 Presets erwartet
        assert len(presets) == 21, f"Erwartet 21 Presets, gefunden: {len(presets)}"

    def test_unknown_preset_raises(self):
        with pytest.raises(FileNotFoundError):
            load_preset("nonexistent_preset")

    def test_all_presets_have_valid_slots(self):
        presets = load_all_presets()
        for pid, preset in presets.items():
            for slot in preset.slots:
                assert slot.type in ("image", "text"), (
                    f"{pid}: slot {slot.id} hat ungültigen type {slot.type}"
                )
                assert slot.css_area, f"{pid}: slot {slot.id} hat kein css_area"
                if slot.type == "text":
                    assert slot.char_limit is not None, f"{pid}: text-slot {slot.id} hat kein char_limit"
                    assert slot.font_size is not None, f"{pid}: text-slot {slot.id} hat kein font_size"
                    assert slot.text_role is not None, f"{pid}: text-slot {slot.id} hat kein text_role"

    def test_cover_hero_exists(self):
        """Cover-Preset muss existieren (worst-case Fallback im Validator)."""
        preset = load_preset("cover_hero")
        assert preset.image_count == 1
        assert preset.has_text is True

    def test_preset_loader_returns_expected_structure(self):
        """Ein konkretes Preset hat die richtigen Werte."""
        preset = load_preset("single_text_below")
        assert preset.id == "single_text_below"
        assert preset.image_count == 1
        assert preset.has_text is True
        image_slots = [s for s in preset.slots if s.type == "image"]
        text_slots = [s for s in preset.slots if s.type == "text"]
        assert len(image_slots) == 1
        assert len(text_slots) >= 1
        caption = text_slots[0]
        assert caption.char_limit == 170
        assert caption.font_size == "9pt"
        assert caption.text_role == "caption"
```

- [ ] **Step 4: Run test to verify it fails**

```bash
uv run pytest tests/test_photobook/test_presets.py -v
```

Expected: Most tests FAIL because no preset JSONs exist yet.

- [ ] **Step 5: Commit**

```bash
git add app/photobook/presets/__init__.py app/photobook/preset_loader.py tests/test_photobook/test_presets.py
git commit -m "feat: add preset_loader with extended SlotDefinition and failing tests"
```

---

### Task 2: Create all 21 preset JSON files

**Files:**
- Create: 21 files in `app/photobook/presets/`

Each preset JSON follows this template:

```json
{
  "id": "<preset_id>",
  "name": "<Human-readable name>",
  "description": "<One-line description>",
  "image_count": N,
  "has_text": true/false,
  "css_class": "preset-<preset_id>",
  "slots": [
    {"id": "<slot_id>", "type": "image", "priority": "<primary|secondary>", "css_area": "<area>", "optional": false},
    {"id": "<text_slot>", "type": "text", "css_area": "<area>", "char_limit": N, "font_size": "<Npt>", "text_role": "<role>", "optional": true}
  ]
}
```

Slot naming conventions:
- Image slots: `main`, `left`/`right`, `img1`/`img2`/`img3`/`img4`, `top`/`bottom`, `tl`/`tr`/`bl`/`br`
- Text slots: `title`, `caption`, `text`

- [ ] **Step 1: Create cover_hero.json**

Write `app/photobook/presets/cover_hero.json`:

```json
{
  "id": "cover_hero",
  "name": "Cover — Hero",
  "description": "Großes Titelbild mit Buchtitel-Overlay am unteren Rand. Für die Titelseite des Fotobuchs.",
  "image_count": 1,
  "has_text": true,
  "css_class": "preset-cover-hero",
  "slots": [
    {"id": "main", "type": "image", "priority": "primary", "css_area": "main", "optional": false},
    {"id": "title", "type": "text", "css_area": "title", "char_limit": 60, "font_size": "14pt", "text_role": "title", "optional": true}
  ]
}
```

- [ ] **Step 2: Create 1-Bild presets (P01-P03)**

Write `app/photobook/presets/single_full.json`:

```json
{
  "id": "single_full",
  "name": "Einzelbild — Vollformat",
  "description": "Ein Bild auf der ganzen Seite ohne Text. Für starke Einzelmotive.",
  "image_count": 1,
  "has_text": false,
  "css_class": "preset-single-full",
  "slots": [
    {"id": "main", "type": "image", "priority": "primary", "css_area": "main", "optional": false}
  ]
}
```

Write `app/photobook/presets/single_text_below.json`:

```json
{
  "id": "single_text_below",
  "name": "Einzelbild mit Unterschrift",
  "description": "Ein Bild (70% der Seite) mit Bildunterschrift darunter (30%).",
  "image_count": 1,
  "has_text": true,
  "css_class": "preset-single-text-below",
  "slots": [
    {"id": "main", "type": "image", "priority": "primary", "css_area": "main", "optional": false},
    {"id": "caption", "type": "text", "css_area": "caption", "char_limit": 170, "font_size": "9pt", "text_role": "caption", "optional": true}
  ]
}
```

Write `app/photobook/presets/single_text_right.json`:

```json
{
  "id": "single_text_right",
  "name": "Einzelbild + Text rechts",
  "description": "Bild links (70%), Textblock rechts (30%).",
  "image_count": 1,
  "has_text": true,
  "css_class": "preset-single-text-right",
  "slots": [
    {"id": "main", "type": "image", "priority": "primary", "css_area": "main", "optional": false},
    {"id": "text", "type": "text", "css_area": "text", "char_limit": 170, "font_size": "9pt", "text_role": "caption", "optional": true}
  ]
}
```

- [ ] **Step 3: Create 2-Bild presets (P04-P07)**

Write `app/photobook/presets/double_equal.json`:

```json
{
  "id": "double_equal",
  "name": "Zwei Bilder — 50/50",
  "description": "Zwei gleich große Bilder nebeneinander. Für Vergleiche oder ähnlich gewichtete Motive.",
  "image_count": 2,
  "has_text": false,
  "css_class": "preset-double-equal",
  "slots": [
    {"id": "left", "type": "image", "priority": "primary", "css_area": "left", "optional": false},
    {"id": "right", "type": "image", "priority": "secondary", "css_area": "right", "optional": false}
  ]
}
```

Write `app/photobook/presets/double_dominant.json`:

```json
{
  "id": "double_dominant",
  "name": "Zwei Bilder — Groß+Klein",
  "description": "Ein großes Bild (2/3) und ein kleineres (1/3) nebeneinander.",
  "image_count": 2,
  "has_text": false,
  "css_class": "preset-double-dominant",
  "slots": [
    {"id": "main", "type": "image", "priority": "primary", "css_area": "main", "optional": false},
    {"id": "secondary", "type": "image", "priority": "secondary", "css_area": "secondary", "optional": false}
  ]
}
```

Write `app/photobook/presets/double_text_below.json`:

```json
{
  "id": "double_text_below",
  "name": "Zwei Bilder + Unterschrift",
  "description": "Zwei Bilder nebeneinander (70%) mit Bildunterschrift darunter (30%).",
  "image_count": 2,
  "has_text": true,
  "css_class": "preset-double-text-below",
  "slots": [
    {"id": "left", "type": "image", "priority": "primary", "css_area": "left", "optional": false},
    {"id": "right", "type": "image", "priority": "secondary", "css_area": "right", "optional": false},
    {"id": "caption", "type": "text", "css_area": "caption", "char_limit": 170, "font_size": "9pt", "text_role": "caption", "optional": true}
  ]
}
```

Write `app/photobook/presets/double_text_right.json`:

```json
{
  "id": "double_text_right",
  "name": "Zwei Bilder + Text rechts",
  "description": "Zwei Bilder untereinander links (70%), Textblock rechts (30%).",
  "image_count": 2,
  "has_text": true,
  "css_class": "preset-double-text-right",
  "slots": [
    {"id": "img1", "type": "image", "priority": "primary", "css_area": "img1", "optional": false},
    {"id": "img2", "type": "image", "priority": "secondary", "css_area": "img2", "optional": false},
    {"id": "text", "type": "text", "css_area": "text", "char_limit": 170, "font_size": "9pt", "text_role": "caption", "optional": true}
  ]
}
```

- [ ] **Step 4: Create 3-Bild presets (P08-P12)**

Write `app/photobook/presets/triple_strip.json`:

```json
{
  "id": "triple_strip",
  "name": "Drei Bilder — Querstreifen",
  "description": "Drei Bilder in einem horizontalen Streifen. Für Sequenzen und Zeitabläufe.",
  "image_count": 3,
  "has_text": false,
  "css_class": "preset-triple-strip",
  "slots": [
    {"id": "left", "type": "image", "priority": "secondary", "css_area": "left", "optional": false},
    {"id": "center", "type": "image", "priority": "primary", "css_area": "center", "optional": false},
    {"id": "right", "type": "image", "priority": "secondary", "css_area": "right", "optional": false}
  ]
}
```

Write `app/photobook/presets/triple_big_top.json`:

```json
{
  "id": "triple_big_top",
  "name": "Drei Bilder — Eins groß oben",
  "description": "Ein großes Bild oben (70%), zwei kleinere darunter (30%).",
  "image_count": 3,
  "has_text": false,
  "css_class": "preset-triple-big-top",
  "slots": [
    {"id": "top", "type": "image", "priority": "primary", "css_area": "top", "optional": false},
    {"id": "bl", "type": "image", "priority": "secondary", "css_area": "bl", "optional": false},
    {"id": "br", "type": "image", "priority": "secondary", "css_area": "br", "optional": false}
  ]
}
```

Write `app/photobook/presets/triple_text_below.json`:

```json
{
  "id": "triple_text_below",
  "name": "Drei quer + Unterschrift",
  "description": "Drei Bilder im Querstreifen (70%) mit Bildunterschrift darunter (30%).",
  "image_count": 3,
  "has_text": true,
  "css_class": "preset-triple-text-below",
  "slots": [
    {"id": "left", "type": "image", "priority": "secondary", "css_area": "left", "optional": false},
    {"id": "center", "type": "image", "priority": "primary", "css_area": "center", "optional": false},
    {"id": "right", "type": "image", "priority": "secondary", "css_area": "right", "optional": false},
    {"id": "caption", "type": "text", "css_area": "caption", "char_limit": 170, "font_size": "9pt", "text_role": "caption", "optional": true}
  ]
}
```

Write `app/photobook/presets/triple_big_text_below.json`:

```json
{
  "id": "triple_big_text_below",
  "name": "Groß+Zwei+Unterschrift",
  "description": "Ein großes Bild oben (50%), zwei kleinere darunter (20%), Bildunterschrift unten (30%).",
  "image_count": 3,
  "has_text": true,
  "css_class": "preset-triple-big-text-below",
  "slots": [
    {"id": "top", "type": "image", "priority": "primary", "css_area": "top", "optional": false},
    {"id": "bl", "type": "image", "priority": "secondary", "css_area": "bl", "optional": false},
    {"id": "br", "type": "image", "priority": "secondary", "css_area": "br", "optional": false},
    {"id": "caption", "type": "text", "css_area": "caption", "char_limit": 170, "font_size": "9pt", "text_role": "caption", "optional": true}
  ]
}
```

Write `app/photobook/presets/triple_text_right.json`:

```json
{
  "id": "triple_text_right",
  "name": "Drei Bilder + Text rechts",
  "description": "Drei Bilder untereinander links (70%), Textblock rechts (30%).",
  "image_count": 3,
  "has_text": true,
  "css_class": "preset-triple-text-right",
  "slots": [
    {"id": "img1", "type": "image", "priority": "primary", "css_area": "img1", "optional": false},
    {"id": "img2", "type": "image", "priority": "secondary", "css_area": "img2", "optional": false},
    {"id": "img3", "type": "image", "priority": "secondary", "css_area": "img3", "optional": false},
    {"id": "text", "type": "text", "css_area": "text", "char_limit": 170, "font_size": "9pt", "text_role": "caption", "optional": true}
  ]
}
```

- [ ] **Step 5: Create 4-Bild presets (P13-P16)**

Write `app/photobook/presets/quad_grid.json`:

```json
{
  "id": "quad_grid",
  "name": "Vier Bilder — 2×2 Raster",
  "description": "Vier Bilder in einem gleichmäßigen 2×2-Raster. Für Sammlungen und Themengruppen.",
  "image_count": 4,
  "has_text": false,
  "css_class": "preset-quad-grid",
  "slots": [
    {"id": "tl", "type": "image", "priority": "primary", "css_area": "tl", "optional": false},
    {"id": "tr", "type": "image", "priority": "secondary", "css_area": "tr", "optional": false},
    {"id": "bl", "type": "image", "priority": "secondary", "css_area": "bl", "optional": false},
    {"id": "br", "type": "image", "priority": "secondary", "css_area": "br", "optional": false}
  ]
}
```

Write `app/photobook/presets/quad_grid_text_below.json`:

```json
{
  "id": "quad_grid_text_below",
  "name": "2×2 Raster + Unterschrift",
  "description": "Vier Bilder im 2×2-Raster (70%) mit Bildunterschrift darunter (30%).",
  "image_count": 4,
  "has_text": true,
  "css_class": "preset-quad-grid-text-below",
  "slots": [
    {"id": "tl", "type": "image", "priority": "primary", "css_area": "tl", "optional": false},
    {"id": "tr", "type": "image", "priority": "secondary", "css_area": "tr", "optional": false},
    {"id": "bl", "type": "image", "priority": "secondary", "css_area": "bl", "optional": false},
    {"id": "br", "type": "image", "priority": "secondary", "css_area": "br", "optional": false},
    {"id": "caption", "type": "text", "css_area": "caption", "char_limit": 170, "font_size": "9pt", "text_role": "caption", "optional": true}
  ]
}
```

Write `app/photobook/presets/quad_strip_text_below.json`:

```json
{
  "id": "quad_strip_text_below",
  "name": "Vier quer + Unterschrift",
  "description": "Vier Bilder in horizontalem Streifen (70%) mit Unterschrift darunter (30%).",
  "image_count": 4,
  "has_text": true,
  "css_class": "preset-quad-strip-text-below",
  "slots": [
    {"id": "img1", "type": "image", "priority": "secondary", "css_area": "img1", "optional": false},
    {"id": "img2", "type": "image", "priority": "primary", "css_area": "img2", "optional": false},
    {"id": "img3", "type": "image", "priority": "primary", "css_area": "img3", "optional": false},
    {"id": "img4", "type": "image", "priority": "secondary", "css_area": "img4", "optional": false},
    {"id": "caption", "type": "text", "css_area": "caption", "char_limit": 170, "font_size": "9pt", "text_role": "caption", "optional": true}
  ]
}
```

Write `app/photobook/presets/quad_large_plus_3.json`:

```json
{
  "id": "quad_large_plus_3",
  "name": "Groß + drei + Text",
  "description": "Ein großes Bild links (70%), drei kleinere rechts gestapelt (30%), Bildunterschrift unten.",
  "image_count": 4,
  "has_text": true,
  "css_class": "preset-quad-large-plus-3",
  "slots": [
    {"id": "main", "type": "image", "priority": "primary", "css_area": "main", "optional": false},
    {"id": "small1", "type": "image", "priority": "secondary", "css_area": "small1", "optional": false},
    {"id": "small2", "type": "image", "priority": "secondary", "css_area": "small2", "optional": false},
    {"id": "small3", "type": "image", "priority": "secondary", "css_area": "small3", "optional": false},
    {"id": "caption", "type": "text", "css_area": "caption", "char_limit": 170, "font_size": "9pt", "text_role": "caption", "optional": true}
  ]
}
```

- [ ] **Step 6: Create Extra presets (E01-E04)**

Write `app/photobook/presets/panorama.json`:

```json
{
  "id": "panorama",
  "name": "Panorama",
  "description": "Ein extragroßes Querformat-Bild mit Bildunterschrift. Für Panorama-Aufnahmen.",
  "image_count": 1,
  "has_text": true,
  "css_class": "preset-panorama",
  "slots": [
    {"id": "main", "type": "image", "priority": "primary", "css_area": "main", "optional": false},
    {"id": "caption", "type": "text", "css_area": "caption", "char_limit": 100, "font_size": "9pt", "text_role": "caption", "optional": true}
  ]
}
```

Write `app/photobook/presets/collage_5.json`:

```json
{
  "id": "collage_5",
  "name": "Collage — 5 Bilder",
  "description": "Fünf Bilder in asymmetrischer Collage: ein großes, drei kleine, ein breites. Ohne Text.",
  "image_count": 5,
  "has_text": false,
  "css_class": "preset-collage-5",
  "slots": [
    {"id": "big", "type": "image", "priority": "primary", "css_area": "big", "optional": false},
    {"id": "s1", "type": "image", "priority": "secondary", "css_area": "s1", "optional": false},
    {"id": "s2", "type": "image", "priority": "secondary", "css_area": "s2", "optional": false},
    {"id": "s3", "type": "image", "priority": "secondary", "css_area": "s3", "optional": false},
    {"id": "wide", "type": "image", "priority": "secondary", "css_area": "wide", "optional": false}
  ]
}
```

Write `app/photobook/presets/image_text_split.json`:

```json
{
  "id": "image_text_split",
  "name": "Bild + Text — 50:50",
  "description": "Bild links (50%), Einleitungstext rechts (50%). Für Kapitelanfänge und Kontextseiten.",
  "image_count": 1,
  "has_text": true,
  "css_class": "preset-image-text-split",
  "slots": [
    {"id": "image", "type": "image", "priority": "primary", "css_area": "image", "optional": false},
    {"id": "text", "type": "text", "css_area": "text", "char_limit": 400, "font_size": "11pt", "text_role": "intro", "optional": false}
  ]
}
```

Write `app/photobook/presets/map_focus.json`:

```json
{
  "id": "map_focus",
  "name": "Karte + Bild",
  "description": "Karte und ein Bild nebeneinander (70%) mit Routenbeschreibung darunter (30%).",
  "image_count": 2,
  "has_text": true,
  "css_class": "preset-map-focus",
  "slots": [
    {"id": "map", "type": "image", "priority": "primary", "css_area": "map", "optional": false},
    {"id": "photo", "type": "image", "priority": "secondary", "css_area": "photo", "optional": false},
    {"id": "caption", "type": "text", "css_area": "caption", "char_limit": 170, "font_size": "9pt", "text_role": "caption", "optional": true}
  ]
}
```

- [ ] **Step 7: Run test_presets to verify all 21 load correctly**

```bash
uv run pytest tests/test_photobook/test_presets.py -v
```

Expected: All tests PASS (21 presets found, valid slots, char_limits present).

- [ ] **Step 8: Commit**

```bash
git add app/photobook/presets/*.json tests/test_photobook/test_presets.py
git commit -m "feat: add 21 preset JSON files with text constraints"
```

---

### Task 3: Update styles.css with 21 preset grid layouts

**Files:**
- Modify: `app/photobook/styles.css`

Replace the old 8 `layout-*` CSS classes with 21 new `preset-*` classes. Keep the base styles (body, .photobook-page, .page-single, .page-spread, .slot-image, .slot-text, .slot-caption, .slot-title, @media print). Remove old layout classes: `.layout-hero-single`, `.layout-split-equal`, `.layout-split-dominant`, `.layout-grid-2x2`, `.layout-strip-3`, `.layout-image-text-left`, `.layout-collection-3`, `.layout-panorama`.

- [ ] **Step 1: Write failing test for new CSS classes**

Write `tests/test_photobook/test_renderer.py` (append to existing file a new test class):

```python
class TestPresetRenderer:
    def test_cover_hero_uses_preset_css_class(self):
        """Renderer muss preset-cover-hero CSS-Klasse verwenden."""
        from app.photobook.renderer import render_photobook
        from app.state import PageDescription, ImageData
        from app.photobook.preset_loader import load_preset

        preset = load_preset("cover_hero")
        page = PageDescription(
            template_id="cover_hero",
            page_type="single",
            slots=[
                {"slot_id": "main", "image_index": 0},
                {"slot_id": "title", "text": "Mein Fotobuch"},
            ],
        )
        images = [ImageData(path="/tmp/test.jpg")]
        html = render_photobook([page], images)
        assert "preset-cover-hero" in html
```

Run: `uv run pytest tests/test_photobook/test_renderer.py::TestPresetRenderer::test_cover_hero_uses_preset_css_class -v`
Expected: FAIL (old styles.css still has `layout-*` classes, renderer hasn't been updated yet).

- [ ] **Step 2: Rewrite styles.css with 21 preset layouts**

Write `app/photobook/styles.css` (complete replacement):

```css
/* CSS Grid Layouts fuer alle Fotobuch-Presets */

* { box-sizing: border-box; margin: 0; padding: 0; }

body {
  font-family: Georgia, 'Times New Roman', serif;
  color: #333;
  background: #666;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0;
}

.photobook-page {
  background: #fff;
  overflow: hidden;
  box-shadow: 0 2px 12px rgba(0,0,0,0.2);
}

.page-single {
  width: 210mm;
  height: 297mm;
  padding: 10mm;
}

.page-spread {
  width: 420mm;
  height: 297mm;
  padding: 10mm;
}

/* --- Base Slot Styles --- */

.slot-image {
  object-fit: cover;
  width: 100%;
  height: 100%;
  display: block;
}

.slot-placeholder {
  background: #e0e0e0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 10pt;
  color: #999;
}

.slot-text {
  font-size: 11pt;
  line-height: 1.6;
  color: #444;
  padding: 4mm;
  display: flex;
  align-items: flex-start;
}

.slot-caption {
  font-size: 9pt;
  color: #777;
  font-style: italic;
  line-height: 1.4;
  padding: 3mm 0 0 0;
}

.slot-title {
  font-size: 14pt;
  font-weight: bold;
  color: #222;
  padding: 4mm;
  display: flex;
  align-items: center;
}

/* --- Cover (1) --- */

.preset-cover-hero {
  display: grid;
  grid-template-columns: 1fr;
  grid-template-rows: 1fr auto;
  grid-template-areas: "main" "title";
  gap: 0;
}

/* --- 1-Bild (3) --- */

.preset-single-full {
  display: grid;
  grid-template-columns: 1fr;
  grid-template-rows: 1fr;
  grid-template-areas: "main";
  gap: 0;
}

.preset-single-text-below {
  display: grid;
  grid-template-columns: 1fr;
  grid-template-rows: 7fr 3fr;
  grid-template-areas: "main" "caption";
  gap: 4mm;
}

.preset-single-text-right {
  display: grid;
  grid-template-columns: 7fr 3fr;
  grid-template-rows: 1fr;
  grid-template-areas: "main text";
  gap: 4mm;
}

/* --- 2-Bild (4) --- */

.preset-double-equal {
  display: grid;
  grid-template-columns: 1fr 1fr;
  grid-template-rows: 1fr;
  grid-template-areas: "left right";
  gap: 4mm;
}

.preset-double-dominant {
  display: grid;
  grid-template-columns: 2fr 1fr;
  grid-template-rows: 1fr;
  grid-template-areas: "main secondary";
  gap: 4mm;
}

.preset-double-text-below {
  display: grid;
  grid-template-columns: 1fr 1fr;
  grid-template-rows: 7fr 3fr;
  grid-template-areas:
    "left right"
    "caption caption";
  gap: 4mm;
}

.preset-double-text-right {
  display: grid;
  grid-template-columns: 7fr 3fr;
  grid-template-rows: 1fr 1fr;
  grid-template-areas:
    "img1 text"
    "img2 text";
  gap: 4mm;
}

/* --- 3-Bild (5) --- */

.preset-triple-strip {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  grid-template-rows: 1fr;
  grid-template-areas: "left center right";
  gap: 3mm;
}

.preset-triple-big-top {
  display: grid;
  grid-template-columns: 1fr 1fr;
  grid-template-rows: 7fr 3fr;
  grid-template-areas:
    "top top"
    "bl br";
  gap: 3mm;
}

.preset-triple-text-below {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  grid-template-rows: 7fr 3fr;
  grid-template-areas:
    "left center right"
    "caption caption caption";
  gap: 3mm;
}

.preset-triple-big-text-below {
  display: grid;
  grid-template-columns: 1fr 1fr;
  grid-template-rows: 5fr 2fr 3fr;
  grid-template-areas:
    "top top"
    "bl br"
    "caption caption";
  gap: 3mm;
}

.preset-triple-text-right {
  display: grid;
  grid-template-columns: 7fr 3fr;
  grid-template-rows: 1fr 1fr 1fr;
  grid-template-areas:
    "img1 text"
    "img2 text"
    "img3 text";
  gap: 3mm;
}

/* --- 4-Bild (4) --- */

.preset-quad-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  grid-template-rows: 1fr 1fr;
  grid-template-areas:
    "tl tr"
    "bl br";
  gap: 3mm;
}

.preset-quad-grid-text-below {
  display: grid;
  grid-template-columns: 1fr 1fr;
  grid-template-rows: 3.5fr 3.5fr 3fr;
  grid-template-areas:
    "tl tr"
    "bl br"
    "caption caption";
  gap: 3mm;
}

.preset-quad-strip-text-below {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr 1fr;
  grid-template-rows: 7fr 3fr;
  grid-template-areas:
    "img1 img2 img3 img4"
    "caption caption caption caption";
  gap: 3mm;
}

.preset-quad-large-plus-3 {
  display: grid;
  grid-template-columns: 7fr 3fr;
  grid-template-rows: 1fr 1fr 1fr 3fr;
  grid-template-areas:
    "main small1"
    "main small2"
    "main small3"
    "caption caption";
  gap: 3mm;
}

/* --- Extra (4) --- */

.preset-panorama {
  display: grid;
  grid-template-columns: 1fr;
  grid-template-rows: 1fr auto;
  grid-template-areas: "main" "caption";
  gap: 0;
  align-items: center;
}

.preset-collage-5 {
  display: grid;
  grid-template-columns: 2fr 1fr;
  grid-template-rows: 1fr 1fr 1fr;
  grid-template-areas:
    "big s1"
    "big s2"
    "wide wide";
  gap: 3mm;
}

.preset-image-text-split {
  display: grid;
  grid-template-columns: 5fr 5fr;
  grid-template-rows: 1fr;
  grid-template-areas: "image text";
  gap: 4mm;
}

.preset-map-focus {
  display: grid;
  grid-template-columns: 1fr 1fr;
  grid-template-rows: 7fr 3fr;
  grid-template-areas:
    "map photo"
    "caption caption";
  gap: 4mm;
}

/* --- Print --- */

@media print {
  body { background: #fff; }
  .photobook-page {
    box-shadow: none;
    page-break-after: always;
  }
  .photobook-page:last-child { page-break-after: avoid; }
}
```

- [ ] **Step 3: Commit**

```bash
git add app/photobook/styles.css
git commit -m "feat: add 21 preset CSS grid layouts, remove old layout classes"
```

---

### Task 4: Update renderer.py to use presets and slot font-size

**Files:**
- Modify: `app/photobook/renderer.py`

The renderer currently uses `load_template()` from `template_loader.py`. We change it to use `load_preset()` from `preset_loader.py` and apply `font_size` from slot definitions directly in inline CSS.

- [ ] **Step 1: Rewrite renderer.py**

Write `app/photobook/renderer.py`:

```python
"""HTML-Assembler fuer Fotobuch-Seiten.

Nimmt PageDescription-Objekte und erzeugt ein vollstaendiges HTML-Dokument
mit CSS Grid Layouts aus den Preset-Definitionen.
"""

import html
import os
from typing import List
from app.state import PageDescription, ImageData
from app.photobook.preset_loader import load_preset

_STYLES_PATH = os.path.join(os.path.dirname(__file__), "styles.css")


def _read_styles() -> str:
    with open(_STYLES_PATH, "r", encoding="utf-8") as f:
        return f.read()


PHOTOBOOK_HEADER = f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Fotobuch</title>
<style>
{_read_styles()}
</style>
</head>
<body>
"""

PHOTOBOOK_FOOTER = """
</body>
</html>
"""


def render_photobook(pages: List[PageDescription], images: List[ImageData]) -> str:
    """Erzeugt ein vollstaendiges HTML-Dokument aus Seitenbeschreibungen.

    Args:
        pages: Liste von PageDescription (vom LLM)
        images: Liste aller ImageData-Objekte

    Returns:
        Vollstaendiges HTML-Dokument als String
    """
    html_parts = [PHOTOBOOK_HEADER]

    for page in pages:
        preset = load_preset(page.template_id)
        css_class = preset.css_class
        html_parts.append(f'<div class="photobook-page {css_class} page-single">')

        slot_defs = {s.id: s for s in preset.slots}

        for slot_data in page.slots:
            slot_id = slot_data.get("slot_id", "")
            slot_def = slot_defs.get(slot_id)
            if not slot_def:
                continue

            area_style = f'style="grid-area: {slot_def.css_area}"'

            if slot_def.type == "image" and slot_data.get("image_index") is not None:
                idx = slot_data["image_index"]
                if 0 <= idx < len(images):
                    img_path = _normalize_path(images[idx].path)
                    html_parts.append(
                        f'<img class="slot-image" {area_style} '
                        f'src="{img_path}" alt="Foto {idx + 1}">'
                    )
                else:
                    html_parts.append(
                        f'<div class="slot-image slot-placeholder" {area_style}>'
                        f'Bild {slot_data["image_index"]} nicht gefunden</div>'
                    )

            elif slot_def.type == "text":
                text = html.escape(slot_data.get("text", ""))
                # Font-Size aus der Slot-Definition direkt ins Inline-CSS
                font_size = slot_def.font_size or "11pt"
                style = f'style="grid-area: {slot_def.css_area}; font-size: {font_size}"'

                if slot_def.text_role == "title":
                    css_class = "slot-title"
                elif slot_def.text_role == "caption":
                    css_class = "slot-caption"
                else:
                    css_class = "slot-text"

                html_parts.append(
                    f'<div class="{css_class}" {style}>{text}</div>'
                )

        html_parts.append("</div>")

    html_parts.append(PHOTOBOOK_FOOTER)
    return "\n".join(html_parts)


def _normalize_path(path: str) -> str:
    """Konvertiert Pfade zu file:/// URIs fuer Headless Chrome."""
    abs_path = os.path.abspath(path)
    return f"file://{abs_path}"
```

- [ ] **Step 2: Run test to verify renderer uses preset CSS**

```bash
uv run pytest tests/test_photobook/test_renderer.py::TestPresetRenderer::test_cover_hero_uses_preset_css_class -v
```

Expected: PASS (renderer now loads preset and uses `preset-cover-hero` CSS class).

- [ ] **Step 3: Commit**

```bash
git add app/photobook/renderer.py tests/test_photobook/test_renderer.py
git commit -m "feat: renderer uses presets with font-size from slot definition"
```

---

### Task 5: Create presets.py data module for LLM prompts

**Files:**
- Create: `app/photobook/presets.py`

Provides lightweight preset data (ID, image_count, has_text) that can be embedded in LLM prompts without loading full JSON.

- [ ] **Step 1: Write presets.py**

Write `app/photobook/presets.py`:

```python
"""Preset-Metadaten fuer LLM-Prompts (leichtgewichtig, ohne JSON-Loading)."""

# Jeder Eintrag: (preset_id, image_count, has_text)
PRESET_CATALOG = [
    # Cover
    ("cover_hero", 1, True),
    # 1-Bild
    ("single_full", 1, False),
    ("single_text_below", 1, True),
    ("single_text_right", 1, True),
    # 2-Bild
    ("double_equal", 2, False),
    ("double_dominant", 2, False),
    ("double_text_below", 2, True),
    ("double_text_right", 2, True),
    # 3-Bild
    ("triple_strip", 3, False),
    ("triple_big_top", 3, False),
    ("triple_text_below", 3, True),
    ("triple_big_text_below", 3, True),
    ("triple_text_right", 3, True),
    # 4-Bild
    ("quad_grid", 4, False),
    ("quad_grid_text_below", 4, True),
    ("quad_strip_text_below", 4, True),
    ("quad_large_plus_3", 4, True),
    # Extra
    ("panorama", 1, True),
    ("collage_5", 5, False),
    ("image_text_split", 1, True),
    ("map_focus", 2, True),
]


def get_preset_summary() -> str:
    """Erzeugt kompakte Preset-Übersicht für den LLM-Prompt."""
    lines = []
    for pid, count, text in PRESET_CATALOG:
        lines.append(f"  {pid}: {count} Bilder, Text={'ja' if text else 'nein'}")
    return "\n".join(lines)


def get_presets_by_image_count(count: int, has_text: bool | None = None) -> list[str]:
    """Filtert Presets nach Bildanzahl und optional Text."""
    result = []
    for pid, c, t in PRESET_CATALOG:
        if c == count:
            if has_text is None or t == has_text:
                result.append(pid)
    return result


def get_any_preset(count: int) -> str:
    """Gibt das erste Preset mit der angegebenen Bildanzahl zurück (Fallback)."""
    for pid, c, _ in PRESET_CATALOG:
        if c == count:
            return pid
    return "quad_grid"  # ultimativer Fallback


# Constraint-Tabelle für Pass-2-Prompt
TEXT_CONSTRAINTS = {
    "title":   {"char_limit": 60,  "font_size": "14pt", "description": "Seitentitel (bold)"},
    "caption": {"char_limit": 170, "font_size": "9pt",  "description": "Bildunterschrift (italic)"},
    "intro":   {"char_limit": 400, "font_size": "11pt", "description": "Einleitungstext"},
}


def get_constraint_summary() -> str:
    """Erzeugt Constraint-Text für den LLM-Prompt."""
    lines = ["TEXT-CONSTRAINTS (UNBEDINGT EINHALTEN):"]
    for role, c in TEXT_CONSTRAINTS.items():
        lines.append(f"  {role}: max. {c['char_limit']} Zeichen, Schriftgröße {c['font_size']} ({c['description']})")
    return "\n".join(lines)
```

- [ ] **Step 2: Write test for presets module**

Append to `tests/test_photobook/test_presets.py`:

```python
class TestPresetCatalog:
    def test_catalog_has_21_entries(self):
        from app.photobook.presets import PRESET_CATALOG
        assert len(PRESET_CATALOG) == 21

    def test_get_presets_by_image_count(self):
        from app.photobook.presets import get_presets_by_image_count
        p1 = get_presets_by_image_count(1)
        assert len(p1) >= 5  # cover + single_full + single_text_below + single_text_right + panorama + image_text_split
        p3 = get_presets_by_image_count(3)
        assert len(p3) == 5

    def test_get_presets_by_count_and_text(self):
        from app.photobook.presets import get_presets_by_image_count
        p3_no_text = get_presets_by_image_count(3, has_text=False)
        assert len(p3_no_text) == 2  # triple_strip, triple_big_top
        p3_text = get_presets_by_image_count(3, has_text=True)
        assert len(p3_text) == 3

    def test_get_any_preset_returns_valid(self):
        from app.photobook.presets import get_any_preset
        assert get_any_preset(1) == "cover_hero"
        assert get_any_preset(3) == "triple_strip"
        assert get_any_preset(99) == "quad_grid"

    def test_constraint_summary_contains_limits(self):
        from app.photobook.presets import get_constraint_summary
        summary = get_constraint_summary()
        assert "60" in summary
        assert "170" in summary
        assert "400" in summary
        assert "14pt" in summary
        assert "9pt" in summary
        assert "11pt" in summary
```

- [ ] **Step 3: Run tests**

```bash
uv run pytest tests/test_photobook/test_presets.py::TestPresetCatalog -v
```

Expected: All PASS.

- [ ] **Step 4: Commit**

```bash
git add app/photobook/presets.py tests/test_photobook/test_presets.py
git commit -m "feat: add lightweight preset catalog module for LLM prompts"
```

---

### Task 6: Update plan.py — preset selection prompt

**Files:**
- Modify: `app/photobook/plan.py`

Changes:
- Prompt: Replace template categories with preset catalog (from `presets.py`)
- Prompt: Add variety rules
- Output: `preset_id` instead of `template_category`
- Fallback: Use `get_any_preset()` from `presets.py`

- [ ] **Step 1: Rewrite plan.py prompt functions**

Write `app/photobook/plan.py`:

```python
"""LLM Pass 1: Preset-Auswahl (pro Seite ein Preset aus 21 Optionen).

Das LLM wählt für jede Seite ein Preset basierend auf Bildanzahl und Text-Bedarf.
Variety-Regeln im Prompt sorgen für Abwechslung.
"""

import json
import re
from typing import Any, Dict, List, Optional
import requests
from app.config import OLLAMA_BASE_URL
from app.state import ImageData, WeatherInfo
from app.utils.image_utils import encode_image_base64
from app.photobook.presets import get_preset_summary, get_any_preset


def _build_plan_prompt(
    image_count: int,
    gpx_stats_d: Optional[Dict[str, Any]],
    notes: Optional[str],
    weather: Optional[WeatherInfo],
    poi_count: int,
) -> str:
    context_parts = [f"BILDER: {image_count} Fotos (chronologisch sortiert, Index 0-{image_count - 1})"]
    if gpx_stats_d:
        dist = gpx_stats_d.get("total_distance_m", 0) / 1000
        elev = gpx_stats_d.get("elevation_gain_m", 0)
        context_parts.append(f"TOUR: {dist:.1f} km, {elev:.0f}m Hoehenmeter")
    if weather and weather.daily:
        context_parts.append(f"WETTER: {weather.summary}")
    if poi_count > 0:
        context_parts.append(f"POIs: {poi_count} Sehenswuerdigkeiten")
    if notes:
        context_parts.append(f"NOTIZEN: {notes}")
    context = "\n".join(context_parts)

    preset_catalog = get_preset_summary()

    return f"""Du bist Fotobuch-Art-Director fuer eine Wandertour.

{context}

PRESETS (waehle eins pro Seite):
{preset_catalog}

VARIETY-REGELN (UNBEDINGT EINHALTEN):
1. Maximal 2x das gleiche Preset im gesamten Buch
2. Nicht 2x hintereinander das gleiche Preset
3. Maximal 3 Seiten ohne Text hintereinander
4. Nicht 3x hintereinander die gleiche Bildanzahl
5. Dramatischer Bogen: Cover (cover_hero) -> ruhiger Start (1-Bild) -> Aufbau (2-3 Bilder) -> Hoehepunkt (4-Bild) -> Ausklang (1-Bild)
6. Seite 0 MUSS cover_hero sein

PLANE die Seitenabfolge. Gib jedem Bild einen Platz.

ANTWORTE AUSSCHLIESSLICH mit diesem JSON:
{{"pages": [{{"position": 0, "preset_id": "cover_hero", "image_indices": [3], "purpose": "Cover"}}], "dramatic_arc": "kurze Beschreibung"}}"""


def _generate_fallback_plan(images: List[ImageData], image_count: int) -> Dict[str, Any]:
    """Deterministische Fallback-Planung: einfache lineare Sequenz mit Presets."""
    indices = list(range(min(image_count, len(images))))
    pages = []
    if indices:
        pages.append({
            "position": 0,
            "preset_id": "cover_hero",
            "image_indices": [indices.pop(0)],
            "purpose": "Cover",
        })
    pos = 1
    while indices:
        remaining = len(indices)
        if remaining >= 4:
            pid = get_any_preset(4)
            pages.append({
                "position": pos,
                "preset_id": pid,
                "image_indices": [indices.pop(0) for _ in range(min(4, remaining))],
                "purpose": "Sammlung",
            })
        elif remaining >= 3:
            pid = get_any_preset(3)
            pages.append({
                "position": pos,
                "preset_id": pid,
                "image_indices": [indices.pop(0) for _ in range(min(3, remaining))],
                "purpose": "Sequenz",
            })
        elif remaining >= 2:
            pid = get_any_preset(2)
            pages.append({
                "position": pos,
                "preset_id": pid,
                "image_indices": [indices.pop(0), indices.pop(0)],
                "purpose": "Vergleich",
            })
        else:
            pages.append({
                "position": pos,
                "preset_id": "single_full",
                "image_indices": [indices.pop(0)],
                "purpose": "Einzelbild",
            })
        pos += 1
    return {"pages": pages, "dramatic_arc": "Fallback: lineare Sequenz"}


def plan_photobook_layout(
    images: List[ImageData],
    gpx_stats: Optional[Dict[str, Any]],
    notes: Optional[str],
    weather: Optional[WeatherInfo],
    poi_list: List[Dict[str, Any]],
    model: str = "gemma4:26b-ctx128k",
    base_url: str = OLLAMA_BASE_URL,
) -> Dict[str, Any]:
    if not images:
        return {"pages": [], "dramatic_arc": ""}
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

- [ ] **Step 2: Run existing plan tests (expected: some failures)**

```bash
uv run pytest tests/test_photobook/test_plan.py -v
```

Expected: Several tests FAIL because they check for `template_category` which no longer exists.

- [ ] **Step 3: Update plan tests**

Rewrite `tests/test_photobook/test_plan.py`:

```python
"""Tests fuer LLM Pass 1: Preset-Auswahl."""
import json
from unittest.mock import patch, MagicMock
from app.state import ImageData
from app.photobook.plan import plan_photobook_layout

SAMPLE_IMAGES = [ImageData(path=f"/tmp/img_{i}.jpg") for i in range(16)]

MOCK_PLAN_RESPONSE = {
    "message": {
        "content": json.dumps({
            "pages": [
                {"position": 0, "preset_id": "cover_hero", "image_indices": [3], "purpose": "Cover"},
                {"position": 1, "preset_id": "double_equal", "image_indices": [7, 12], "purpose": "Aufstieg"},
                {"position": 2, "preset_id": "quad_grid", "image_indices": [0, 2, 5, 8], "purpose": "Sammlung"},
            ],
            "dramatic_arc": "intro -> buildup -> variation"
        })
    }
}


class TestPlan:
    @patch("app.photobook.plan.requests.post")
    def test_plan_returns_valid_structure(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = MOCK_PLAN_RESPONSE
        mock_post.return_value = mock_resp
        result = plan_photobook_layout(
            images=SAMPLE_IMAGES,
            gpx_stats={"total_distance_m": 8000},
            notes="Test",
            weather=None,
            poi_list=[],
            model="test-model",
        )
        assert "pages" in result
        assert len(result["pages"]) == 3
        assert "dramatic_arc" in result
        page0 = result["pages"][0]
        assert page0["position"] == 0
        assert page0["preset_id"] == "cover_hero"
        assert isinstance(page0["image_indices"], list)

    @patch("app.photobook.plan.requests.post")
    def test_fallback_on_llm_error(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_post.return_value = mock_resp
        result = plan_photobook_layout(
            images=SAMPLE_IMAGES[:4],
            gpx_stats={},
            notes=None,
            weather=None,
            poi_list=[],
            model="test-model",
        )
        assert "pages" in result
        assert len(result["pages"]) > 0
        assert result["pages"][0]["preset_id"] == "cover_hero"

    def test_fallback_plan_uses_presets(self):
        """Fallback-Planung muss preset_id (nicht template_category) produzieren."""
        result = plan_photobook_layout(
            images=SAMPLE_IMAGES[:6],
            gpx_stats={},
            notes=None,
            weather=None,
            poi_list=[],
            model="test-model",
            base_url="http://invalid:99999",
        )
        for page in result["pages"]:
            assert "preset_id" in page, f"Seite {page.get('position')} hat kein preset_id"
            assert page["preset_id"] != "", f"Seite {page.get('position')} hat leeres preset_id"
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_photobook/test_plan.py -v
```

Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add app/photobook/plan.py tests/test_photobook/test_plan.py
git commit -m "feat: plan.py uses preset catalog with variety rules in prompt"
```

---

### Task 7: Update generate.py — constraint-based slot filling

**Files:**
- Modify: `app/photobook/generate.py`

Changes:
- Prompt: Replace template catalog with constraint table
- Output: Slots with `text` within `char_limit`
- Fallback: Uses `get_any_preset()` from `presets.py` instead of category-based defaults

- [ ] **Step 1: Rewrite generate.py**

Write `app/photobook/generate.py`:

```python
"""LLM Pass 2: Slot-Zuweisung + Text innerhalb von Preset-Constraints."""

import json
import re
from typing import Any, Dict, List, Optional
import requests
from app.config import OLLAMA_BASE_URL
from app.state import ImageData, PageDescription
from app.photobook.preset_loader import load_all_presets
from app.photobook.presets import get_constraint_summary, get_any_preset, TEXT_CONSTRAINTS
from app.utils.image_utils import encode_image_base64


def _build_generate_prompt(pages_plan, gpx_stats_d, notes):
    presets = load_all_presets()
    preset_summary = []
    for pid, p in presets.items():
        slot_info = ", ".join(
            f"{s.id}({s.type},{s.text_role or s.priority or '-'})" for s in p.slots
        )
        preset_summary.append(f"  {pid} [{p.image_count} Bilder, Text={'ja' if p.has_text else 'nein'}]: {slot_info}")
    catalog = "\n".join(preset_summary)

    constraints = get_constraint_summary()

    plan_text = json.dumps(pages_plan, indent=2, ensure_ascii=False)
    gpx_text = ""
    if gpx_stats_d:
        dist = gpx_stats_d.get("total_distance_m", 0) / 1000
        elev = gpx_stats_d.get("elevation_gain_m", 0)
        gpx_text = f"\nTOUR: {dist:.1f} km, {elev:.0f}m Hoehenmeter."
    notes_text = f"\nTOUR-NOTIZEN: {notes}" if notes else ""

    return f"""Du befuellst die Slots der gewaehlten Presets mit Bildern und Text.

SEITENPLAN (preset_id pro Seite):
{plan_text}

PRESET-SLOTS:
{catalog}
{gpx_text}{notes_text}

{constraints}

AUFGABE PRO SEITE:
1. Weise jedem Image-Slot ein Bild zu (image_index aus dem Plan)
2. Generiere Text NUR wenn das Preset Text-Slots hat
3. Text MUSS innerhalb des Zeichenlimits bleiben (Validator kuerzt sonst)
4. Textrollen: title (stimmungsvoller Seitentitel), caption (Bildunterschrift), intro (Einleitung)

ANTWORTE NUR mit JSON-Array:
[{{"preset_id": "cover_hero", "slots": [{{"slot_id": "main", "image_index": 3}}, {{"slot_id": "title", "text": "Gipfelstuermer"}}]}}]"""


def generate_photobook_pages(
    plan: Dict[str, Any],
    images: List[ImageData],
    gpx_stats: Optional[Dict[str, Any]],
    notes: Optional[str],
    model: str = "gemma4:26b-ctx128k",
    base_url: str = OLLAMA_BASE_URL,
) -> List[PageDescription]:
    pages_plan = plan.get("pages", [])
    if not pages_plan:
        return []
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
        if resp.status_code == 200:
            content = resp.json().get("message", {}).get("content", "")
            array_match = re.search(r'\[.*\]', content, re.DOTALL)
            if array_match:
                pages_data = json.loads(array_match.group())
                result = []
                for pd in pages_data:
                    valid_slots = []
                    for slot in pd.get("slots", []):
                        idx = slot.get("image_index", -1)
                        if 0 <= idx < len(images):
                            valid_slots.append(slot)
                        else:
                            # Entferne image_index wenn ungültig, behalte text
                            cleansed = {k: v for k, v in slot.items() if k != "image_index"}
                            if cleansed.get("text") or cleansed.get("slot_id"):
                                valid_slots.append(cleansed)
                    page = PageDescription(
                        template_id=pd.get("preset_id", "quad_grid"),
                        page_type="single",
                        slots=valid_slots,
                    )
                    result.append(page)
                if result:
                    return result
    except Exception as e:
        print(f"⚠️ Pass 2 (Generierung) fehlgeschlagen: {e}")

    # Fallback: verwende das im Plan gewählte Preset mit einfacher Slot-Zuweisung
    all_presets = load_all_presets()
    fallback = []
    for plan_page in pages_plan:
        preset_id = plan_page.get("preset_id", "quad_grid")
        preset = all_presets.get(preset_id)
        if preset is None:
            # Fallback: nächstes Preset mit passender Bildanzahl
            count = len(plan_page.get("image_indices", []))
            preset_id = get_any_preset(count)
            preset = all_presets.get(preset_id, all_presets["quad_grid"])

        indices = plan_page.get("image_indices", [])
        image_slots = [s.id for s in preset.slots if s.type == "image"]
        slots = []
        for sid, idx in zip(image_slots, indices):
            slots.append({"slot_id": sid, "image_index": idx})
        fallback.append(PageDescription(
            template_id=preset_id,
            page_type="single",
            slots=slots,
        ))
    return fallback
```

- [ ] **Step 2: Update generate tests**

Rewrite `tests/test_photobook/test_generate.py`:

```python
"""Tests fuer LLM Pass 2: Slot-Zuweisung mit Preset-Constraints."""
import json
from unittest.mock import patch, MagicMock
from app.state import ImageData, PageDescription
from app.photobook.generate import generate_photobook_pages

MOCK_PLAN = {
    "pages": [
        {"position": 0, "preset_id": "cover_hero", "image_indices": [0], "purpose": "Cover"},
        {"position": 1, "preset_id": "double_equal", "image_indices": [1, 2], "purpose": "Aufstieg"},
    ]
}

MOCK_GENERATE_RESPONSE = {
    "message": {
        "content": json.dumps([
            {"preset_id": "cover_hero", "slots": [
                {"slot_id": "main", "image_index": 0},
                {"slot_id": "title", "text": "Gipfelblick"},
            ]},
            {"preset_id": "double_equal", "slots": [
                {"slot_id": "left", "image_index": 1},
                {"slot_id": "right", "image_index": 2},
            ]},
        ])
    }
}

SAMPLE_IMAGES = [ImageData(path=f"/tmp/img_{i}.jpg") for i in range(16)]


class TestGenerate:
    @patch("app.photobook.generate.requests.post")
    def test_generate_returns_page_descriptions(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = MOCK_GENERATE_RESPONSE
        mock_post.return_value = mock_resp
        result = generate_photobook_pages(
            plan=MOCK_PLAN, images=SAMPLE_IMAGES, gpx_stats={}, notes="Test", model="test-model",
        )
        assert len(result) == 2
        assert isinstance(result[0], PageDescription)
        assert result[0].template_id == "cover_hero"
        assert result[1].template_id == "double_equal"

    def test_fallback_on_empty_plan(self):
        result = generate_photobook_pages(
            plan={"pages": []}, images=SAMPLE_IMAGES[:4], gpx_stats={}, notes=None, model="test-model",
        )
        assert len(result) == 0

    @patch("app.photobook.generate.requests.post")
    def test_generate_handles_missing_images(self, mock_post):
        bad_response = {
            "message": {"content": json.dumps([
                {"preset_id": "cover_hero", "slots": [{"slot_id": "main", "image_index": 999}]},
            ])}
        }
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = bad_response
        mock_post.return_value = mock_resp
        result = generate_photobook_pages(
            plan=MOCK_PLAN, images=SAMPLE_IMAGES[:3], gpx_stats={}, notes="Test", model="test-model",
        )
        assert len(result) >= 0

    def test_fallback_uses_preset_from_plan(self):
        """Fallback soll das im Plan gewählte Preset respektieren."""
        plan = {
            "pages": [
                {"position": 0, "preset_id": "cover_hero", "image_indices": [0]},
                {"position": 1, "preset_id": "double_equal", "image_indices": [1, 2]},
            ]
        }
        images = [ImageData(path=f"/tmp/img_{i}.jpg") for i in range(3)]
        with patch("app.photobook.generate.requests.post", side_effect=Exception("LLM down")):
            pages = generate_photobook_pages(plan, images, None, None, model="test")
        assert len(pages) == 2
        assert pages[0].template_id == "cover_hero"
        assert pages[1].template_id == "double_equal"

    def test_generate_includes_titles_and_captions(self):
        """LLM-Response mit 'title' und 'text' Feldern muss korrekt geparst werden."""
        plan = {"pages": [{"position": 0, "preset_id": "cover_hero", "image_indices": [0]}]}
        images = [ImageData(path=f"/tmp/img_{i}.jpg") for i in range(1)]
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "message": {"content": json.dumps([
                {"preset_id": "cover_hero", "slots": [
                    {"slot_id": "main", "image_index": 0},
                    {"slot_id": "title", "text": "Aufbruch"},
                ]}
            ])}
        }
        with patch("app.photobook.generate.requests.post", return_value=mock_resp):
            pages = generate_photobook_pages(plan, images, None, None, model="test")
        assert len(pages) == 1
        title_slot = next((s for s in pages[0].slots if s.get("slot_id") == "title"), None)
        assert title_slot is not None
        assert title_slot["text"] == "Aufbruch"

    def test_fallback_unknown_preset_uses_fallback_count(self):
        """Fallback mit unbekanntem Preset wählt passendes nach Bildanzahl."""
        plan = {"pages": [{"position": 0, "preset_id": "nonexistent", "image_indices": [0, 1]}]}
        images = [ImageData(path=f"/tmp/img_{i}.jpg") for i in range(2)]
        with patch("app.photobook.generate.requests.post", side_effect=Exception("LLM down")):
            pages = generate_photobook_pages(plan, images, None, None, model="test")
        assert len(pages) == 1
        assert pages[0].template_id != "nonexistent"
        # Sollte ein 2-Bild-Preset sein
        from app.photobook.preset_loader import load_preset
        preset = load_preset(pages[0].template_id)
        assert preset.image_count == 2
```

- [ ] **Step 3: Run tests**

```bash
uv run pytest tests/test_photobook/test_generate.py -v
```

Expected: All PASS (or most — there may be test adjustments needed).

- [ ] **Step 4: Commit**

```bash
git add app/photobook/generate.py tests/test_photobook/test_generate.py
git commit -m "feat: generate.py uses constraint-based slot filling with presets"
```

---

### Task 8: Update validator.py — char-limit checks + variety enforcement

**Files:**
- Modify: `app/photobook/validator.py`

Changes:
- `validate_page()`: Check against preset (not template), validate char limits
- `enforce_fallback()`: Repair using presets, truncate overflow text
- New: `check_variety()` — enforce variety rules across all pages
- `validate_all_pages()`: Call `check_variety()` after per-page validation

- [ ] **Step 1: Rewrite validator.py**

Write `app/photobook/validator.py`:

```python
"""Deterministischer Validator fuer LLM-Seitenbeschreibungen.

Prueft die LLM-Ausgabe auf Konsistenz VOR dem Rendering:
  - Slot-Konsistenz gegen Preset-Definition
  - Char-Limit-Overflow → Text kürzen
  - Variety-Checks (Cover, Back-to-Back, Text-Lücke, Bildanzahl-Monotonie, Gesamt-Variety)
"""

from typing import List
from app.state import PageDescription
from app.photobook.preset_loader import load_all_presets, load_preset
from app.photobook.presets import get_any_preset, get_presets_by_image_count


def validate_page(page: PageDescription, presets: dict = None) -> List[str]:
    """Prueft eine einzelne Seite auf Fehler. Gibt Liste von Fehlermeldungen zurueck."""
    errors = []
    if presets is None:
        presets = load_all_presets()

    if page.template_id not in presets:
        errors.append(f"Preset '{page.template_id}' existiert nicht im Katalog.")
        return errors

    preset = presets[page.template_id]
    slot_defs = {s.id: s for s in preset.slots}
    image_count = 0

    for slot in page.slots:
        slot_id = slot.get("slot_id", "")
        if slot_id not in slot_defs:
            errors.append(f"Slot '{slot_id}' existiert nicht im Preset '{page.template_id}'.")
            continue

        slot_def = slot_defs[slot_id]

        if slot.get("image_index") is not None:
            if slot["image_index"] < 0:
                errors.append(f"Slot '{slot_id}': image_index {slot['image_index']} ist ungueltig.")
            else:
                image_count += 1

        # Char-Limit-Prüfung für Text-Slots
        if slot_def.type == "text" and slot_def.char_limit is not None:
            text = slot.get("text", "")
            if len(text) > slot_def.char_limit:
                errors.append(
                    f"Slot '{slot_id}': Text hat {len(text)} Zeichen (Limit: {slot_def.char_limit})."
                )

    if image_count > preset.image_count:
        errors.append(
            f"Zu viele Bilder: {image_count} (Preset '{page.template_id}' erlaubt {preset.image_count})."
        )
    if image_count < preset.image_count and image_count > 0:
        errors.append(
            f"Zu wenige Bilder: {image_count} (Preset '{page.template_id}' erwartet {preset.image_count})."
        )

    return errors


def enforce_fallback(page: PageDescription) -> PageDescription:
    """Repariert eine fehlerhafte Seite mit minimalen Eingriffen.

    Priorität: Preset erhalten → Text kürzen → Preset wechseln.
    """
    presets = load_all_presets()
    image_indices = [
        s["image_index"] for s in page.slots
        if s.get("image_index") is not None and s["image_index"] >= 0
    ]

    # Preset existiert nicht → passendes nach Bildanzahl wählen
    if page.template_id not in presets:
        page.template_id = get_any_preset(len(image_indices))

    preset = presets[page.template_id]
    slot_defs = {s.id: s for s in preset.slots}
    image_slot_ids = [s.id for s in preset.slots if s.type == "image"]

    repaired_slots = []

    # Bilder korrekten Image-Slots zuweisen
    for i, img_idx in enumerate(image_indices):
        if i >= len(image_slot_ids):
            break
        slot_data = {"slot_id": image_slot_ids[i], "image_index": img_idx}
        repaired_slots.append(slot_data)

    # Text-Slots aus Original übernehmen, dabei Char-Limit kürzen
    for slot in page.slots:
        sid = slot.get("slot_id", "")
        if sid in slot_defs:
            sd = slot_defs[sid]
            if sd.type == "text" and slot.get("text"):
                text = slot["text"]
                if sd.char_limit and len(text) > sd.char_limit:
                    text = text[:sd.char_limit]
                repaired_slots.append({"slot_id": sid, "text": text})

    return PageDescription(
        template_id=page.template_id,
        page_type="single",
        slots=repaired_slots,
    )


def check_variety(pages: List[PageDescription]) -> List[PageDescription]:
    """Stellt Abwechslung in der Preset-Sequenz sicher.

    Regeln:
    1. Seite 0 muss cover_hero sein
    2. Kein Preset mehr als 2× insgesamt
    3. Nicht 2× hintereinander gleiches Preset
    4. Max. 3 Seiten ohne Text hintereinander
    5. Nicht 3× hintereinander gleiche Bildanzahl
    6. Mindestens 5 verschiedene Presets im Buch
    """
    presets = load_all_presets()
    if not pages:
        return pages

    # Die ersten Seiten nicht verändern (Referenz für Vergleiche)
    result = list(pages)

    # Regel 1: Cover erzwingen
    if result[0].template_id != "cover_hero":
        result[0] = _replace_preset(result[0], "cover_hero")

    # Regel 2 + 3: Kein Preset >2× insgesamt, kein Back-to-Back
    preset_counts = {}
    for i, page in enumerate(result):
        pid = page.template_id
        count = preset_counts.get(pid, 0) + 1
        if count > 2:
            # Tausche gegen nächstes Preset gleicher Bildanzahl
            replacement = _find_alternative_preset(pid, preset_counts)
            result[i] = _replace_preset(page, replacement)
            pid = replacement
            count = 1
        preset_counts[pid] = count

        # Back-to-Back-Check
        if i > 0 and pid == result[i - 1].template_id:
            replacement = _find_alternative_preset(pid, preset_counts)
            result[i] = _replace_preset(page, replacement)
            preset_counts[replacement] = preset_counts.get(replacement, 0) + 1

    # Regel 4: Max. 3 No-Text-Seiten hintereinander
    no_text_streak = 0
    for i, page in enumerate(result):
        preset = presets.get(page.template_id)
        if preset and not preset.has_text:
            no_text_streak += 1
            if no_text_streak > 3:
                # Ersetze durch Text-Preset gleicher Bildanzahl
                text_presets = get_presets_by_image_count(preset.image_count, has_text=True)
                if text_presets:
                    result[i] = _replace_preset(page, text_presets[0])
                no_text_streak = 0
        else:
            no_text_streak = 0

    # Regel 5: Max. 2 Seiten gleiche Bildanzahl hintereinander
    same_count_streak = 0
    last_count = None
    for i, page in enumerate(result):
        preset = presets.get(page.template_id)
        if preset:
            if preset.image_count == last_count:
                same_count_streak += 1
                if same_count_streak > 2:
                    # Wähle Preset mit anderer Bildanzahl
                    new_count = preset.image_count + 1 if preset.image_count < 4 else 1
                    replacement = get_any_preset(new_count)
                    result[i] = _replace_preset(page, replacement)
                    same_count_streak = 0
            else:
                same_count_streak = 1
                last_count = preset.image_count

    # Regel 6: Mindestens 5 verschiedene Presets
    unique = len({p.template_id for p in result})
    if unique < 5 and len(result) >= 5:
        # Ersetze Duplikate durch ungenutzte Presets gleicher Bildanzahl
        used = {p.template_id for p in result}
        for i, page in enumerate(result):
            if unique >= 5:
                break
            preset = presets.get(page.template_id)
            if preset:
                alternatives = [
                    pid for pid in get_presets_by_image_count(preset.image_count)
                    if pid not in used
                ]
                if alternatives:
                    result[i] = _replace_preset(page, alternatives[0])
                    used.add(alternatives[0])
                    unique += 1

    return result


def _replace_preset(page: PageDescription, new_preset_id: str) -> PageDescription:
    """Ersetzt das Preset einer Seite, behält aber image_indices bei."""
    presets = load_all_presets()
    preset = presets.get(new_preset_id)
    if not preset:
        return page

    old_slots = page.slots
    new_slots = []

    # Extrahiere image_indices aus den alten Slots
    image_indices = [
        s["image_index"] for s in old_slots
        if s.get("image_index") is not None and s["image_index"] >= 0
    ]

    # Weise sie den Image-Slots des neuen Presets zu
    image_slot_ids = [s.id for s in preset.slots if s.type == "image"]
    for i, img_idx in enumerate(image_indices):
        if i >= len(image_slot_ids):
            break
        new_slots.append({"slot_id": image_slot_ids[i], "image_index": img_idx})

    # Text-Slots aus dem Original übernehmen (falls passend)
    for slot in old_slots:
        sid = slot.get("slot_id", "")
        if sid in {s.id for s in preset.slots if s.type == "text"} and slot.get("text"):
            new_slots.append({"slot_id": sid, "text": slot["text"]})

    return PageDescription(
        template_id=new_preset_id,
        page_type="single",
        slots=new_slots,
    )


def _find_alternative_preset(current_id: str, used_counts: dict) -> str:
    """Findet alternatives Preset gleicher Bildanzahl, das noch nicht >2× verwendet wurde."""
    presets = load_all_presets()
    current = presets.get(current_id)
    if not current:
        return get_any_preset(1)

    candidates = get_presets_by_image_count(current.image_count)
    for pid in candidates:
        if pid != current_id and used_counts.get(pid, 0) < 2:
            return pid

    # Alle sind >2× → nimm das erste andere
    for pid in candidates:
        if pid != current_id:
            return pid

    return current_id


def validate_all_pages(pages: List[PageDescription]) -> tuple[List[PageDescription], List[str]]:
    """Validiert alle Seiten: Einzelseiten-Prüfung + Variety-Checks."""
    _presets = load_all_presets()
    validated = []
    warnings = []
    for i, page in enumerate(pages):
        errors = validate_page(page, _presets)
        if errors:
            warnings.append(f"Seite {i}: {', '.join(errors)}")
            validated.append(enforce_fallback(page))
        else:
            validated.append(page)

    # Variety-Checks (nur warnen, nicht blocken)
    validated = check_variety(validated)

    return validated, warnings
```

- [ ] **Step 2: Write variety and text overflow tests**

Write `tests/test_photobook/test_variety.py`:

```python
"""Tests fuer Variety-Enforcement im Validator."""
from app.photobook.validator import check_variety
from app.state import PageDescription


def make_page(preset_id: str) -> PageDescription:
    return PageDescription(template_id=preset_id, page_type="single", slots=[])


class TestVariety:
    def test_cover_hero_forced_on_first_page(self):
        """Seite 0 muss cover_hero sein."""
        pages = [
            make_page("single_full"),
            make_page("double_equal"),
        ]
        result = check_variety(pages)
        assert result[0].template_id == "cover_hero"

    def test_no_back_to_back_same_preset(self):
        """Nicht 2x das gleiche Preset hintereinander."""
        pages = [
            make_page("cover_hero"),
            make_page("double_equal"),
            make_page("double_equal"),  # Back-to-Back
        ]
        result = check_variety(pages)
        assert result[2].template_id != "double_equal"

    def test_max_3_no_text_pages_in_a_row(self):
        """Maximal 3 Seiten ohne Text hintereinander."""
        pages = [
            make_page("cover_hero"),      # has_text=True
            make_page("single_full"),      # no text
            make_page("double_equal"),     # no text
            make_page("triple_strip"),     # no text
            make_page("quad_grid"),        # no text → 4 in Folge → Verstoß
        ]
        result = check_variety(pages)
        # Die 4. No-Text-Seite sollte durch ein Text-Preset ersetzt sein
        no_text_count = 0
        for i in range(1, len(result)):
            from app.photobook.preset_loader import load_preset
            preset = load_preset(result[i].template_id)
            if not preset.has_text:
                no_text_count += 1
            else:
                break
        assert no_text_count <= 3, f"{no_text_count} No-Text-Seiten in Folge"

    def test_empty_pages_list(self):
        """Leere Liste bleibt leer."""
        result = check_variety([])
        assert result == []
```

Write `tests/test_photobook/test_text_overflow.py`:

```python
"""Tests fuer Char-Limit-Truncation im Validator."""
from app.photobook.validator import validate_page, enforce_fallback
from app.state import PageDescription


class TestTextOverflow:
    def test_text_within_limit_passes(self):
        """Text innerhalb des Char-Limits wird akzeptiert."""
        page = PageDescription(
            template_id="cover_hero",
            page_type="single",
            slots=[
                {"slot_id": "main", "image_index": 0},
                {"slot_id": "title", "text": "Kurzer Titel"},
            ],
        )
        errors = validate_page(page)
        assert errors == []

    def test_text_exceeding_limit_reported(self):
        """Text über dem Char-Limit erzeugt Fehler."""
        long_text = "X" * 100  # 100 Zeichen, Limit für title ist 60
        page = PageDescription(
            template_id="cover_hero",
            page_type="single",
            slots=[
                {"slot_id": "main", "image_index": 0},
                {"slot_id": "title", "text": long_text},
            ],
        )
        errors = validate_page(page)
        assert len(errors) >= 1
        assert any("Zeichen" in e for e in errors)

    def test_enforce_fallback_truncates_text(self):
        """enforce_fallback kürzt Text über dem Char-Limit."""
        long_text = "A" * 200  # caption limit ist 170
        page = PageDescription(
            template_id="single_text_below",
            page_type="single",
            slots=[
                {"slot_id": "main", "image_index": 0},
                {"slot_id": "caption", "text": long_text},
            ],
        )
        result = enforce_fallback(page)
        caption_slot = next((s for s in result.slots if s.get("slot_id") == "caption"), None)
        assert caption_slot is not None
        assert len(caption_slot["text"]) <= 170
```

- [ ] **Step 3: Run tests**

```bash
uv run pytest tests/test_photobook/test_variety.py tests/test_photobook/test_text_overflow.py -v
```

Expected: All PASS.

- [ ] **Step 4: Update existing validator tests**

The existing validator tests in `test_validator.py` use old template names like `hero_single`, `split_equal`, `grid_2x2`, `split_dominant`. These need to be updated to use preset names.

Update `tests/test_photobook/test_validator.py`:

Replace all template names:
- `hero_single` → `cover_hero`
- `split_equal` → `double_equal`
- `grid_2x2` → `quad_grid`
- `split_dominant` → `double_dominant`
- `"primary"` slot → `"main"` (for hero presets) or `"left"` (for split presets)
- `"secondary"` slot → `"right"` (for split presets)

```python
"""Tests fuer den deterministischen Validator (angepasst an Presets)."""
from app.photobook.validator import validate_page
from app.state import PageDescription


def make_page(template_id, slots=None):
    return PageDescription(template_id=template_id, page_type="single", slots=slots or [])


class TestValidator:
    def test_valid_cover_hero_passes(self):
        page = make_page("cover_hero", slots=[
            {"slot_id": "main", "image_index": 0},
            {"slot_id": "title", "text": "Cover"},
        ])
        errors = validate_page(page)
        assert errors == []

    def test_overfill_rejected(self):
        page = make_page("cover_hero", slots=[
            {"slot_id": "main", "image_index": 0},
            {"slot_id": "main", "image_index": 1},  # Nur 1 Bild-Slot in cover_hero
        ])
        errors = validate_page(page)
        assert len(errors) >= 1

    def test_unknown_preset_rejected(self):
        page = make_page("nonexistent", slots=[])
        errors = validate_page(page)
        assert len(errors) >= 1
        assert any("existiert" in e.lower() for e in errors)

    def test_missing_mandatory_slot_rejected(self):
        page = make_page("double_dominant", slots=[
            {"slot_id": "main", "image_index": 0}
        ])
        errors = validate_page(page)
        assert len(errors) >= 1

    def test_negative_image_index_rejected(self):
        page = make_page("cover_hero", slots=[
            {"slot_id": "main", "image_index": -1},
        ])
        errors = validate_page(page)
        assert len(errors) >= 1

    def test_valid_quad_grid_partial_passes(self):
        page = make_page("quad_grid", slots=[
            {"slot_id": "tl", "image_index": 0},
            {"slot_id": "tr", "image_index": 1},
            {"slot_id": "bl", "image_index": 2},
            {"slot_id": "br", "image_index": 3},
        ])
        errors = validate_page(page)
        # 4 von 4 slots befüllt → okay
        assert not any("Bilder" in e for e in errors)


class TestEnforceFallback:
    def test_unknown_preset_fallback_to_quad_grid(self):
        """Unbekanntes Preset → Fallback passend zur Bildanzahl."""
        from app.photobook.validator import enforce_fallback
        from app.state import PageDescription

        page = PageDescription(
            template_id="nonexistent",
            page_type="single",
            slots=[
                {"slot_id": "bad", "image_index": 5},
                {"slot_id": "bad2", "image_index": 10},
            ],
        )
        result = enforce_fallback(page)
        assert result.template_id != "nonexistent"
        # 2 Bilder → sollte ein 2-Bild-Preset sein
        from app.photobook.preset_loader import load_preset
        preset = load_preset(result.template_id)
        assert preset.image_count == 2

    def test_truncates_at_preset_image_count(self):
        """enforce_fallback kappt bei maximaler Bildanzahl des Presets."""
        from app.photobook.validator import enforce_fallback
        from app.state import PageDescription

        page = PageDescription(
            template_id="quad_grid",
            page_type="single",
            slots=[
                {"slot_id": "x", "image_index": i} for i in range(10)
            ],
        )
        result = enforce_fallback(page)
        assert len(result.slots) <= 4

    def test_handles_empty_slots(self):
        """enforce_fallback vertraegt leere Slot-Liste."""
        from app.photobook.validator import enforce_fallback
        from app.state import PageDescription

        page = PageDescription(template_id="quad_grid", page_type="single", slots=[])
        result = enforce_fallback(page)
        assert result.template_id == "quad_grid"
        assert result.slots == []

    def test_handles_negative_indices(self):
        """enforce_fallback filtert negative Indizes heraus."""
        from app.photobook.validator import enforce_fallback
        from app.state import PageDescription

        page = PageDescription(
            template_id="quad_grid",
            page_type="single",
            slots=[
                {"slot_id": "x", "image_index": -1},
                {"slot_id": "y", "image_index": 3},
            ],
        )
        result = enforce_fallback(page)
        assert len(result.slots) == 1
        assert result.slots[0]["image_index"] == 3

    def test_enforce_fallback_truncates_long_text(self):
        """Text über Char-Limit wird im Fallback gekürzt."""
        from app.photobook.validator import enforce_fallback
        from app.state import PageDescription

        long_text = "X" * 200
        page = PageDescription(
            template_id="cover_hero",
            page_type="single",
            slots=[
                {"slot_id": "main", "image_index": 0},
                {"slot_id": "title", "text": long_text},
            ],
        )
        result = enforce_fallback(page)
        title_slot = next((s for s in result.slots if s.get("slot_id") == "title"), None)
        if title_slot:
            assert len(title_slot.get("text", "")) <= 60


class TestValidateAllPages:
    def test_returns_valid_pages_and_warnings(self):
        """validate_all_pages trennt gueltige und fehlerhafte Seiten."""
        from app.photobook.validator import validate_all_pages
        from app.state import PageDescription

        pages = [
            PageDescription(template_id="cover_hero", page_type="single",
                          slots=[{"slot_id": "main", "image_index": 0}]),
            PageDescription(template_id="nonexistent", page_type="single", slots=[]),
            PageDescription(template_id="double_dominant", page_type="single",
                          slots=[
                              {"slot_id": "main", "image_index": 1},
                              {"slot_id": "secondary", "image_index": 2},
                          ]),
        ]
        validated, warnings = validate_all_pages(pages)
        assert len(validated) == 3
        assert len(warnings) >= 1

    def test_no_warnings_when_all_valid(self):
        """validate_all_pages produziert keine Warnungen bei gueltigen Seiten."""
        from app.photobook.validator import validate_all_pages
        from app.state import PageDescription

        pages = [
            PageDescription(template_id="cover_hero", page_type="single",
                          slots=[{"slot_id": "main", "image_index": 0}]),
        ]
        validated, warnings = validate_all_pages(pages)
        assert len(warnings) == 0
```

- [ ] **Step 5: Run all validator tests**

```bash
uv run pytest tests/test_photobook/test_validator.py tests/test_photobook/test_variety.py tests/test_photobook/test_text_overflow.py -v
```

Expected: All PASS.

- [ ] **Step 6: Commit**

```bash
git add app/photobook/validator.py tests/test_photobook/test_validator.py tests/test_photobook/test_variety.py tests/test_photobook/test_text_overflow.py
git commit -m "feat: validator enforces char limits and variety rules for presets"
```

---

### Task 9: Cleanup — delete old templates, update imports

**Files:**
- Delete: `app/photobook/templates/*.json` (8 files)
- Delete: `app/photobook/template_loader.py`
- Modify: `tests/test_photobook/test_renderer.py` — fix remaining old tests
- Modify: `tests/test_photobook/test_graph.py` — if it references old templates
- Modify: `app/nodes/` — if any nodes import from template_loader

- [ ] **Step 1: Find all imports of template_loader**

```bash
rg "template_loader" app/ tests/ --files-with-matches
```

- [ ] **Step 2: Fix all imports — replace with preset_loader**

For each file found, update:
```python
from app.photobook.template_loader import ... 
→ from app.photobook.preset_loader import ...
```

And update function calls:
```python
load_template("hero_single") → load_preset("cover_hero")
load_all_templates() → load_all_presets()
```

- [ ] **Step 3: Delete old template files and template_loader.py**

```bash
rm app/photobook/template_loader.py
rm app/photobook/templates/*.json
# Remove templates directory if empty
rmdir app/photobook/templates 2>/dev/null || true
```

- [ ] **Step 4: Fix test_template_loader.py → test_presets.py**

The existing `test_template_loader.py` should be replaced by `test_presets.py` which already exists from Task 1. Delete the old test:

```bash
rm tests/test_photobook/test_template_loader.py
```

- [ ] **Step 5: Fix existing integration test mocks**

The `test_full_photobook_pipeline` test in `test_integration.py` uses old template names in its mock data (`MOCK_PLAN` with `template_category`, `MOCK_GENERATE` with `hero_single`/`split_equal`/`grid_2x2`). Update these mocks:

In `MOCK_PLAN`, replace `template_category` → `preset_id`:
```python
MOCK_PLAN = {"message": {"content": json.dumps({
    "pages": [
        {"position": 0, "page_type": "cover", "preset_id": "cover_hero", "image_indices": [0], "purpose": "Cover"},
        {"position": 1, "page_type": "spread", "preset_id": "double_equal", "image_indices": [1, 2], "purpose": "Split"},
        {"position": 2, "page_type": "single", "preset_id": "quad_grid", "image_indices": [3, 4, 5, 6], "purpose": "Grid"},
    ],
    "dramatic_arc": "test"
})}}
```

In `MOCK_GENERATE`, replace old template IDs:
```python
MOCK_GENERATE = {"message": {"content": json.dumps([
    {"preset_id": "cover_hero", "slots": [{"slot_id": "main", "image_index": 0}]},
    {"preset_id": "double_equal", "slots": [
        {"slot_id": "left", "image_index": 1}, {"slot_id": "right", "image_index": 2},
    ]},
    {"preset_id": "quad_grid", "slots": [
        {"slot_id": "tl", "image_index": 3}, {"slot_id": "tr", "image_index": 4},
        {"slot_id": "bl", "image_index": 5}, {"slot_id": "br", "image_index": 6},
    ]},
])}}
```

Also update the assertion `assert "layout-hero-single" in` → `assert "preset-cover-hero" in`.

- [ ] **Step 6: Fix test_renderer.py for old template references**

Any tests in `test_renderer.py` that reference old templates (like `hero_single`, `grid_2x2`) need updating to use preset names. The `TestPresetRenderer` class was already added in Task 3. Update remaining old test cases.

- [ ] **Step 8: Run full test suite**

```bash
uv run pytest tests/test_photobook/ -v
```

Expected: All tests in test_photobook/ PASS. Fix any remaining failures.

- [ ] **Step 9: Run full project test suite**

```bash
uv run pytest tests/ -q
```

Expected: All tests pass (except the 1 pre-existing failure noted in NEXT_SESSION.md).

- [ ] **Step 10: Commit cleanup**

```bash
git add -A
git commit -m "chore: remove old template system, update all imports to preset_loader"
```

---

### Task 10: Integration test — end-to-end with presets

**Files:**
- Create/modify: `tests/test_photobook/test_integration.py`

- [ ] **Step 1: Write integration test**

The file `tests/test_photobook/test_integration.py` already has `import json` and `from unittest.mock import patch, MagicMock` at the top. Append this class at the end of the file:

```python
class TestPresetPipeline:
    """Integrationstest: Plan → Generate → Validate → Render mit Presets."""

    @patch("app.photobook.plan.requests.post")
    @patch("app.photobook.generate.requests.post")
    def test_full_pipeline_with_presets(self, mock_generate_post, mock_plan_post):
        """Die komplette Pipeline mit Presets muss ein gueltiges HTML liefern."""
        from app.photobook.plan import plan_photobook_layout
        from app.photobook.generate import generate_photobook_pages
        from app.photobook.validator import validate_all_pages
        from app.photobook.renderer import render_photobook
        from app.state import ImageData

        images = [ImageData(path=f"/tmp/img_{i}.jpg") for i in range(8)]

        # Mock Pass 1: Preset-Auswahl
        mock_plan_resp = MagicMock()
        mock_plan_resp.status_code = 200
        mock_plan_resp.json.return_value = {
            "message": {"content": json.dumps({
                "pages": [
                    {"position": 0, "preset_id": "cover_hero", "image_indices": [0]},
                    {"position": 1, "preset_id": "double_equal", "image_indices": [1, 2]},
                    {"position": 2, "preset_id": "triple_strip", "image_indices": [3, 4, 5]},
                    {"position": 3, "preset_id": "single_full", "image_indices": [6]},
                    {"position": 4, "preset_id": "single_text_below", "image_indices": [7]},
                ],
                "dramatic_arc": "cover → buildup → highlight → closing"
            })}
        }
        mock_plan_post.return_value = mock_plan_resp

        # Mock Pass 2: Slot-Befüllung
        mock_gen_resp = MagicMock()
        mock_gen_resp.status_code = 200
        mock_gen_resp.json.return_value = {
            "message": {"content": json.dumps([
                {"preset_id": "cover_hero", "slots": [
                    {"slot_id": "main", "image_index": 0},
                    {"slot_id": "title", "text": "Bergtour 2026"},
                ]},
                {"preset_id": "double_equal", "slots": [
                    {"slot_id": "left", "image_index": 1},
                    {"slot_id": "right", "image_index": 2},
                ]},
                {"preset_id": "triple_strip", "slots": [
                    {"slot_id": "left", "image_index": 3},
                    {"slot_id": "center", "image_index": 4},
                    {"slot_id": "right", "image_index": 5},
                ]},
                {"preset_id": "single_full", "slots": [
                    {"slot_id": "main", "image_index": 6},
                ]},
                {"preset_id": "single_text_below", "slots": [
                    {"slot_id": "main", "image_index": 7},
                    {"slot_id": "caption", "text": "Gipfelblick"},
                ]},
            ])}
        }
        mock_generate_post.return_value = mock_gen_resp

        # Pipeline ausführen
        plan = plan_photobook_layout(images, None, None, None, [], model="test")
        assert len(plan["pages"]) == 5
        assert plan["pages"][0]["preset_id"] == "cover_hero"

        pages = generate_photobook_pages(plan, images, None, None, model="test")
        assert len(pages) == 5

        validated, warnings = validate_all_pages(pages)
        assert len(validated) == 5
        # Variety-Check: cover_hero muss auf Position 0 sein
        assert validated[0].template_id == "cover_hero"

        html = render_photobook(validated, images)
        assert "preset-cover-hero" in html
        assert "Bergtour 2026" in html
        assert "Gipfelblick" in html
        assert "<html" in html
        assert "</html>" in html
```

- [ ] **Step 2: Run integration test**

```bash
uv run pytest tests/test_photobook/test_integration.py::TestPresetPipeline -v
```

Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/test_photobook/test_integration.py
git commit -m "test: add end-to-end integration test for preset pipeline"
```
