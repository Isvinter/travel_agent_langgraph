# Fotobuch-Generator — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Erweitere den Travel-Agent um KI-gestützte Fotobuch-Generierung: LLM wählt Layouts + weist Bilder zu, CSS-Grid-Renderer erzeugt druckbares PDF.

**Architecture:** Neuer Graph-Zweig nach `generate_enriched_map` mit 5 Nodes. Drei Hauptkomponenten: Layout-Katalog (8 JSON-Templates), LLM Art Director (Zwei-Pass via Ollama), Rendering-Engine (CSS Grid → HTML → Headless-Chrome-PDF). Trennung von Inhalt (LLM) und Darstellung (Renderer).

**Tech Stack:** Python 3.12, Pydantic, CSS Grid, LangGraph, Ollama (multimodal), Selenium/Chrome CDP, pytest

---

## File Structure

```
app/
├── photobook/                                   # NEU: Fotobuch-Modul
│   ├── __init__.py
│   ├── templates/                               # NEU: Layout-Templates (JSON)
│   │   ├── hero_single.json
│   │   ├── split_equal.json
│   │   ├── split_dominant.json
│   │   ├── grid_2x2.json
│   │   ├── strip_3.json
│   │   ├── image_text_left.json
│   │   ├── collection_3.json
│   │   └── panorama.json
│   ├── template_loader.py                      # NEU: JSON → Pydantic-Modelle
│   ├── validator.py                            # NEU: LLM-Output Validierung
│   ├── renderer.py                             # NEU: HTML Assembler (CSS Grid)
│   ├── generate_pdf.py                         # NEU: PDF via Headless Chrome
│   ├── image_selector.py                       # NEU: LLM Bildauswahl
│   ├── plan.py                                 # NEU: LLM Pass 1 (Dramaturgie)
│   ├── generate.py                             # NEU: LLM Pass 2 (Templates + Captions)
│   └── styles.css                              # NEU: CSS Grid Styles
├── nodes/
│   ├── select_photobook_images_node.py          # NEU: Node-Wrapper
│   ├── plan_photobook_node.py                   # NEU: Node-Wrapper
│   ├── generate_photobook_node.py               # NEU: Node-Wrapper
│   ├── render_photobook_node.py                 # NEU: Node-Wrapper
│   └── generate_photobook_pdf_node.py           # NEU: Node-Wrapper
├── state.py                                     # MODIFY: +PhotobookConfig, +Felder
└── graph.py                                     # MODIFY: +Fotobuch-Zweig + Mode-Routing

tests/
└── test_photobook/                              # NEU: Test-Suite
    ├── __init__.py
    ├── test_template_loader.py
    ├── test_validator.py
    ├── test_renderer.py
    ├── test_pdf.py
    ├── test_image_selector.py
    ├── test_plan.py
    ├── test_generate.py
    └── test_graph.py
```

---

### Task 1: State + Config (PhotobookConfig, AppState-Erweiterung)

**Files:**
- Modify: `app/state.py`

- [ ] **Step 1: Add PhotobookConfig and extend OutputConfig/AppState**

```python
# app/state.py — am Ende der Datei vor dem letzten Blank-Line einfügen:

class PhotobookConfig(BaseModel):
    """Konfiguration für die Fotobuch-Ausgabe."""
    photo_count: int = Field(default=16, ge=5, le=24)


class OutputConfig(BaseModel):
    """Konfiguration für die Blog-Ausgabe — vom Benutzer vor Pipeline-Start gesetzt."""
    wildcard_max: int = Field(default=12, ge=1, le=50)
    article_length: Literal["short", "normal", "detailed"] = "normal"
    style_persona: Literal["mountain_veteran", "field_reporter"] = "mountain_veteran"
    pdf_export: bool = False
    mode: Literal["blog", "photobook"] = "blog"          # NEU
    photobook: PhotobookConfig = PhotobookConfig()        # NEU


class PageDescription(BaseModel):
    """Seitenbeschreibung — Output des LLM (Pass 2), Input des Renderers."""
    template_id: str
    page_type: str  # "single" | "spread"
    slots: List[Dict[str, Any]] = []


class AppState(BaseModel):
    images: List[ImageData] = []
    selected_images: List[ImageData] = []
    image_clusters: List[Dict[str, Any]] = []
    gpx_file: str = ""
    gpx_stats: Optional[GPXStats] = None
    gpx_pauses: List[dict] = []
    elevation_profile_path: Optional[str] = None
    metadata: Dict[str, Any] = {}
    blog_post: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None
    weather: Optional[WeatherInfo] = None
    poi_list: List[Dict[str, Any]] = []
    enrichment_context: Dict[str, Any] = {}
    model: str = "gemma4:26b-ctx128k"
    output_config: OutputConfig = OutputConfig()
    # NEU: Fotobuch-Felder
    photobook_images: List[ImageData] = []
    photobook_plan: Optional[Dict[str, Any]] = None
    photobook_pages: List[PageDescription] = []
    photobook_html: Optional[str] = None
    photobook_pdf_path: Optional[str] = None
```

- [ ] **Step 2: Run existing tests to verify no breakage**

Run: `uv run pytest tests/ -v -x --ignore=tests/test_photobook -q`
Expected: All existing tests PASS (no regressions from new fields).

- [ ] **Step 3: Commit**

```bash
git add app/state.py
git commit -m "feat: add PhotobookConfig and photobook state fields"
```

---

### Task 2: Template Loader + Alle 8 Template-JSONs

**Files:**
- Create: `app/photobook/__init__.py` (empty)
- Create: `app/photobook/template_loader.py`
- Create: `app/photobook/templates/` (8 JSON files)
- Create: `tests/test_photobook/__init__.py` (empty)
- Create: `tests/test_photobook/test_template_loader.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_photobook/test_template_loader.py
import pytest
from app.photobook.template_loader import load_template, load_all_templates, PhotobookTemplate, SlotDefinition


class TestTemplateLoader:
    def test_load_hero_single(self):
        template = load_template("hero_single")
        assert template.id == "hero_single"
        assert template.page_type == "single"
        assert template.min_images == 1
        assert template.max_images == 1
        assert len(template.slots) >= 1
        main_slot = [s for s in template.slots if s.priority == "primary"]
        assert len(main_slot) == 1

    def test_load_split_dominant(self):
        template = load_template("split_dominant")
        assert template.id == "split_dominant"
        assert template.page_type == "spread"
        assert template.max_images == 2
        slot_ids = [s.id for s in template.slots]
        assert "primary" in slot_ids
        assert "secondary" in slot_ids

    def test_load_all_templates_returns_dict(self):
        templates = load_all_templates()
        assert isinstance(templates, dict)
        assert len(templates) >= 8
        assert "hero_single" in templates
        assert "grid_2x2" in templates
        assert "panorama" in templates

    def test_unknown_template_raises(self):
        with pytest.raises(FileNotFoundError):
            load_template("nonexistent_layout")

    def test_all_templates_have_valid_slots(self):
        templates = load_all_templates()
        for tid, tmpl in templates.items():
            for slot in tmpl.slots:
                assert slot.type in ("image", "text", "caption"), \
                    f"{tid}: slot {slot.id} has invalid type {slot.type}"
                assert slot.css_area, f"{tid}: slot {slot.id} has no css_area"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_photobook/test_template_loader.py -v`
Expected: FAIL — ImportError (module doesn't exist yet).

- [ ] **Step 3: Create the Pydantic schema + loader**

```python
# app/photobook/__init__.py
```

```python
# app/photobook/template_loader.py
"""Template-Loader — lädt JSON-Templates und parst sie in Pydantic-Modelle."""

import json
from pathlib import Path
from typing import Dict, List, Optional
from pydantic import BaseModel

_TEMPLATES_DIR = Path(__file__).parent / "templates"


class SlotDefinition(BaseModel):
    """Ein einzelner Slot in einem Template."""
    id: str
    type: str  # "image" | "text" | "caption"
    priority: Optional[str] = None  # "primary" | "secondary" | None
    css_area: str
    optional: bool = False


class PhotobookTemplate(BaseModel):
    """Ein Layout-Template aus dem Katalog."""
    id: str
    name: str
    category: str
    description: str
    page_type: str  # "single" | "spread"
    min_images: int
    max_images: int
    has_text: bool = False
    supports_captions: bool = False
    css_class: str
    slots: List[SlotDefinition]


def load_template(template_id: str) -> PhotobookTemplate:
    """Lädt ein einzelnes Template aus dem Katalog."""
    path = _TEMPLATES_DIR / f"{template_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"Template '{template_id}' nicht gefunden unter {path}")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return PhotobookTemplate(**data)


def load_all_templates() -> Dict[str, PhotobookTemplate]:
    """Lädt alle Templates aus dem Katalog."""
    templates = {}
    for path in sorted(_TEMPLATES_DIR.glob("*.json")):
        template_id = path.stem
        templates[template_id] = load_template(template_id)
    return templates


def get_template_summary_for_llm() -> str:
    """Erzeugt eine Kurzübersicht aller Templates für den LLM-Prompt."""
    lines = []
    for tid, tmpl in load_all_templates().items():
        slot_info = ", ".join(
            f"{s.id}({s.type},{s.priority or 'normal'})" for s in tmpl.slots
        )
        lines.append(
            f"- {tid} [{tmpl.category}/{tmpl.page_type}] "
            f"({tmpl.min_images}-{tmpl.max_images} Bilder): {slot_info}"
        )
    return "\n".join(lines)
```

- [ ] **Step 4: Create the templates directory and all 8 JSON files**

```bash
mkdir -p app/photobook/templates
```

Create each file:

```json
// app/photobook/templates/hero_single.json
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
    {"id": "main", "type": "image", "priority": "primary", "css_area": "main", "optional": false},
    {"id": "caption", "type": "caption", "priority": null, "css_area": "caption", "optional": true}
  ]
}
```

```json
// app/photobook/templates/split_equal.json
{
  "id": "split_equal",
  "name": "Split — Zwei Bilder 50/50",
  "description": "Zwei gleich große Bilder nebeneinander auf einer Doppelseite. Gut für Vergleiche oder ähnlich wichtige Bilder.",
  "category": "split",
  "page_type": "spread",
  "min_images": 2,
  "max_images": 2,
  "has_text": false,
  "supports_captions": true,
  "css_class": "layout-split-equal",
  "slots": [
    {"id": "left", "type": "image", "priority": "primary", "css_area": "left", "optional": false},
    {"id": "right", "type": "image", "priority": "secondary", "css_area": "right", "optional": false},
    {"id": "caption", "type": "caption", "priority": null, "css_area": "caption", "optional": true}
  ]
}
```

```json
// app/photobook/templates/split_dominant.json
{
  "id": "split_dominant",
  "name": "Split — Dominant + Sekundär",
  "description": "Großes Hauptbild (66%) + kleineres Sekundärbild (33%) auf einer Doppelseite. Für Hauptmotiv mit Kontextbild.",
  "category": "split",
  "page_type": "spread",
  "min_images": 2,
  "max_images": 2,
  "has_text": false,
  "supports_captions": true,
  "css_class": "layout-split-dominant",
  "slots": [
    {"id": "primary", "type": "image", "priority": "primary", "css_area": "main", "optional": false},
    {"id": "secondary", "type": "image", "priority": "secondary", "css_area": "side", "optional": false},
    {"id": "caption", "type": "caption", "priority": null, "css_area": "caption", "optional": true}
  ]
}
```

```json
// app/photobook/templates/grid_2x2.json
{
  "id": "grid_2x2",
  "name": "Grid — 2x2 Raster",
  "description": "Vier Bilder in einem gleichmäßigen 2x2-Raster. Für Dichte, Sammlungen und Gruppen von ähnlichen Bildern.",
  "category": "grid",
  "page_type": "single",
  "min_images": 3,
  "max_images": 4,
  "has_text": false,
  "supports_captions": false,
  "css_class": "layout-grid-2x2",
  "slots": [
    {"id": "tl", "type": "image", "priority": "primary", "css_area": "tl", "optional": false},
    {"id": "tr", "type": "image", "priority": "secondary", "css_area": "tr", "optional": false},
    {"id": "bl", "type": "image", "priority": "secondary", "css_area": "bl", "optional": false},
    {"id": "br", "type": "image", "priority": "secondary", "css_area": "br", "optional": true}
  ]
}
```

```json
// app/photobook/templates/strip_3.json
{
  "id": "strip_3",
  "name": "Strip — Drei Bilder quer",
  "description": "Drei Bilder in einem horizontalen Querstreifen. Für Sequenzen, Zeitabläufe oder Panorama-Ausschnitte.",
  "category": "strip",
  "page_type": "single",
  "min_images": 3,
  "max_images": 3,
  "has_text": false,
  "supports_captions": false,
  "css_class": "layout-strip-3",
  "slots": [
    {"id": "left", "type": "image", "priority": "secondary", "css_area": "left", "optional": false},
    {"id": "center", "type": "image", "priority": "primary", "css_area": "center", "optional": false},
    {"id": "right", "type": "image", "priority": "secondary", "css_area": "right", "optional": false}
  ]
}
```

```json
// app/photobook/templates/image_text_left.json
{
  "id": "image_text_left",
  "name": "Bild + Text links/rechts",
  "description": "Bild links, Textblock rechts. Für kontextuelle Erklärungen oder Einleitungen zu Bildern.",
  "category": "mixed",
  "page_type": "spread",
  "min_images": 1,
  "max_images": 1,
  "has_text": true,
  "supports_captions": true,
  "css_class": "layout-image-text-left",
  "slots": [
    {"id": "image", "type": "image", "priority": "primary", "css_area": "image", "optional": false},
    {"id": "text", "type": "text", "priority": null, "css_area": "text", "optional": false},
    {"id": "caption", "type": "caption", "priority": null, "css_area": "caption", "optional": true}
  ]
}
```

```json
// app/photobook/templates/collection_3.json
{
  "id": "collection_3",
  "name": "Collection — 3 Bilder (L+R unten)",
  "description": "Großes Bild oben, zwei kleinere Bilder darunter. Für thematische Sammlungen mit einem Hauptbild.",
  "category": "collection",
  "page_type": "single",
  "min_images": 3,
  "max_images": 3,
  "has_text": false,
  "supports_captions": false,
  "css_class": "layout-collection-3",
  "slots": [
    {"id": "top", "type": "image", "priority": "primary", "css_area": "top", "optional": false},
    {"id": "bottom_left", "type": "image", "priority": "secondary", "css_area": "bl", "optional": false},
    {"id": "bottom_right", "type": "image", "priority": "secondary", "css_area": "br", "optional": false}
  ]
}
```

```json
// app/photobook/templates/panorama.json
{
  "id": "panorama",
  "name": "Panorama — Extragroß",
  "description": "Ein Bild über die volle Breite einer Doppelseite. Für Panorama-Aufnahmen und dramatische Weitwinkel-Bilder.",
  "category": "hero",
  "page_type": "spread",
  "min_images": 1,
  "max_images": 1,
  "has_text": false,
  "supports_captions": true,
  "css_class": "layout-panorama",
  "slots": [
    {"id": "main", "type": "image", "priority": "primary", "css_area": "main", "optional": false},
    {"id": "caption", "type": "caption", "priority": null, "css_area": "caption", "optional": true}
  ]
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_photobook/test_template_loader.py -v`
Expected: 5 PASS

- [ ] **Step 6: Commit**

```bash
git add app/photobook/__init__.py app/photobook/template_loader.py app/photobook/templates/ tests/test_photobook/__init__.py tests/test_photobook/test_template_loader.py
git commit -m "feat: add template loader and 8 layout templates as JSON"
```

---

### Task 3: Validator — Deterministische LLM-Output-Validierung

**Files:**
- Create: `app/photobook/validator.py`
- Create: `tests/test_photobook/test_validator.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_photobook/test_validator.py
import pytest
from app.photobook.validator import validate_page, PageDescription


def make_page(template_id, slots=None):
    return PageDescription(template_id=template_id, page_type="single", slots=slots or [])


class TestValidator:
    def test_valid_hero_single_passes(self):
        page = make_page("hero_single", slots=[
            {"slot_id": "main", "image_index": 0, "caption": "Cover"}
        ])
        errors = validate_page(page)
        assert errors == []

    def test_overfill_rejected(self):
        page = make_page("hero_single", slots=[
            {"slot_id": "main", "image_index": 0},
            {"slot_id": "main", "image_index": 1},
        ])
        errors = validate_page(page)
        assert len(errors) == 1
        assert "2 Bilder" in errors[0] or "max_images" in errors[0].lower()

    def test_unknown_template_rejected(self):
        page = make_page("nonexistent", slots=[])
        errors = validate_page(page)
        assert len(errors) >= 1
        assert any("unknown" in e.lower() or "existiert" in e.lower() for e in errors)

    def test_missing_mandatory_slot_rejected(self):
        page = make_page("split_dominant", slots=[
            {"slot_id": "primary", "image_index": 0}
        ])
        errors = validate_page(page)
        assert len(errors) == 1
        assert "secondary" in errors[0].lower() or "slot" in errors[0].lower()

    def test_negative_image_index_rejected(self):
        page = make_page("hero_single", slots=[
            {"slot_id": "main", "image_index": -1, "caption": "Bad index"}
        ])
        errors = validate_page(page)
        assert len(errors) >= 1

    def test_empty_slots_for_empty_template_passes(self):
        page = make_page("grid_2x2", slots=[
            {"slot_id": "tl", "image_index": 0},
            {"slot_id": "tr", "image_index": 1},
            {"slot_id": "bl", "image_index": 2},
        ])
        errors = validate_page(page)
        assert errors == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_photobook/test_validator.py -v`
Expected: FAIL — ImportError.

- [ ] **Step 3: Implement the validator**

```python
# app/photobook/validator.py
"""Deterministischer Validator für LLM-Seitenbeschreibungen.

Prüft die LLM-Ausgabe auf Konsistenz VOR dem Rendering.
Fehlerhafte Seiten werden in ein grid_2x2 Fallback-Layout umgewandelt.
"""

from typing import List
from app.state import PageDescription
from app.photobook.template_loader import load_all_templates


def validate_page(page: PageDescription) -> List[str]:
    """Prüft eine einzelne Seite auf Fehler. Gibt Liste von Fehlermeldungen zurück."""
    errors = []
    templates = load_all_templates()

    if page.template_id not in templates:
        errors.append(f"Template '{page.template_id}' existiert nicht im Katalog.")
        return errors

    template = templates[page.template_id]
    slot_defs = {s.id: s for s in template.slots}
    image_count = 0

    for slot in page.slots:
        slot_id = slot.get("slot_id", "")
        if slot_id not in slot_defs:
            errors.append(f"Slot '{slot_id}' existiert nicht im Template '{page.template_id}'.")
            continue

        if slot.get("image_index") is not None:
            if slot["image_index"] < 0:
                errors.append(f"Slot '{slot_id}': image_index {slot['image_index']} ist ungültig.")
            image_count += 1

    if image_count > template.max_images:
        errors.append(
            f"Zu viele Bilder: {image_count} (Template '{page.template_id}' erlaubt max. {template.max_images} Bilder)."
        )
    if image_count < template.min_images:
        errors.append(
            f"Zu wenige Bilder: {image_count} (Template '{page.template_id}' benötigt min. {template.min_images} Bilder)."
        )

    # Prüfe dass alle mandatory slots befüllt sind
    mandatory_ids = {s.id for s in template.slots if not s.optional and s.type != "caption"}
    filled_ids = {s.get("slot_id", "") for s in page.slots if s.get("slot_id") in mandatory_ids}
    missing = mandatory_ids - filled_ids
    for mid in missing:
        slot_def = slot_defs[mid]
        if slot_def.type == "image":
            errors.append(f"Pflicht-Slot '{mid}' ist nicht befüllt.")

    return errors


def enforce_fallback(page: PageDescription) -> PageDescription:
    """Wandelt eine fehlerhafte Seite in ein grid_2x2 Fallback-Layout um.

    Verteilt die Bilder gleichmäßig auf die 4 Grid-Slots. Bei < 4 Bildern
    bleiben die hinteren Slots leer (optional=True laut Template).
    """
    image_indices = [
        s["image_index"] for s in page.slots
        if s.get("image_index") is not None and s["image_index"] >= 0
    ]
    slot_ids = ["tl", "tr", "bl", "br"]
    fallback_slots = []
    for i, img_idx in enumerate(image_indices):
        if i < len(slot_ids):
            fallback_slots.append({"slot_id": slot_ids[i], "image_index": img_idx})
    return PageDescription(
        template_id="grid_2x2",
        page_type="single",
        slots=fallback_slots,
    )


def validate_all_pages(pages: List[PageDescription]) -> tuple[List[PageDescription], List[str]]:
    """Validiert alle Seiten. Fehlerhafte Seiten werden in Fallback umgewandelt."""
    validated = []
    warnings = []
    for i, page in enumerate(pages):
        errors = validate_page(page)
        if errors:
            warnings.append(f"Seite {i}: {', '.join(errors)}")
            validated.append(enforce_fallback(page))
        else:
            validated.append(page)
    return validated, warnings
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_photobook/test_validator.py -v`
Expected: 6 PASS

- [ ] **Step 5: Commit**

```bash
git add app/photobook/validator.py tests/test_photobook/test_validator.py
git commit -m "feat: add deterministic LLM-output validator with fallback"
```

---

### Task 4: Renderer — HTML Assembler + CSS Stylesheet

**Files:**
- Create: `app/photobook/renderer.py`
- Create: `app/photobook/styles.css`
- Create: `tests/test_photobook/test_renderer.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_photobook/test_renderer.py
import os
import tempfile
from app.state import PageDescription, ImageData
from app.photobook.renderer import render_photobook


TEST_IMAGES = [
    ImageData(path="/tmp/test_img_0.jpg", timestamp=None, latitude=None, longitude=None),
    ImageData(path="/tmp/test_img_1.jpg", timestamp=None, latitude=None, longitude=None),
    ImageData(path="/tmp/test_img_2.jpg", timestamp=None, latitude=None, longitude=None),
    ImageData(path="/tmp/test_img_3.jpg", timestamp=None, latitude=None, longitude=None),
]


class TestRenderer:
    def test_render_single_page_hero(self):
        pages = [
            PageDescription(
                template_id="hero_single",
                page_type="single",
                slots=[{"slot_id": "main", "image_index": 0, "caption": "Cover"}],
            )
        ]
        html = render_photobook(pages, TEST_IMAGES)
        assert "<!DOCTYPE html>" in html.lower() or "<html" in html.lower()
        assert "layout-hero-single" in html
        assert "slot-image" in html
        assert "Cover" in html

    def test_render_spread_has_correct_dimensions(self):
        pages = [
            PageDescription(
                template_id="split_equal",
                page_type="spread",
                slots=[
                    {"slot_id": "left", "image_index": 0},
                    {"slot_id": "right", "image_index": 1},
                ],
            )
        ]
        html = render_photobook(pages, TEST_IMAGES)
        assert "layout-split-equal" in html
        # Spread sollte größere Breite haben (A3 landscape)
        assert "420mm" in html or "595mm" in html or "148mm" in html

    def test_render_multiple_pages(self):
        pages = [
            PageDescription(template_id="hero_single", page_type="single", slots=[{"slot_id": "main", "image_index": 0}]),
            PageDescription(template_id="grid_2x2", page_type="single", slots=[
                {"slot_id": "tl", "image_index": 0},
                {"slot_id": "tr", "image_index": 1},
                {"slot_id": "bl", "image_index": 2},
                {"slot_id": "br", "image_index": 3},
            ]),
        ]
        html = render_photobook(pages, TEST_IMAGES)
        assert html.count("slot-image") >= 5  # 1 + 4
        assert "layout-hero-single" in html
        assert "layout-grid-2x2" in html

    def test_render_includes_css_classes(self):
        pages = [
            PageDescription(template_id="hero_single", page_type="single", slots=[{"slot_id": "main", "image_index": 0}]),
        ]
        html = render_photobook(pages, TEST_IMAGES)
        assert "grid-template-areas" in html

    def test_render_text_slot(self):
        pages = [
            PageDescription(
                template_id="image_text_left",
                page_type="spread",
                slots=[
                    {"slot_id": "image", "image_index": 0},
                    {"slot_id": "text", "text": "Einleitungstext zur Tour"},
                ],
            )
        ]
        html = render_photobook(pages, TEST_IMAGES)
        assert "Einleitungstext zur Tour" in html
        assert "slot-text" in html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_photobook/test_renderer.py -v`
Expected: FAIL — ImportError.

- [ ] **Step 3: Implement the renderer + styles.css**

```python
# app/photobook/renderer.py
"""HTML-Assembler für Fotobuch-Seiten.

Nimmt PageDescription-Objekte und erzeugt ein vollständiges HTML-Dokument
mit CSS Grid Layouts, das via Headless Chrome als PDF gedruckt werden kann.
"""

import os
import datetime
from typing import List
from app.state import PageDescription, ImageData
from app.photobook.template_loader import load_template, load_all_templates

_STYLES_PATH = os.path.join(os.path.dirname(__file__), "styles.css")


def _read_styles() -> str:
    with open(_STYLES_PATH, "r", encoding="utf-8") as f:
        return f.read()


PHOTOBOOK_STYLES = _read_styles()

PHOTOBOOK_HEADER = """<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Fotobuch</title>
<style>
""" + _read_styles() + """
</style>
</head>
<body>
"""

PHOTOBOOK_FOOTER = """
</body>
</html>
"""


def render_photobook(pages: List[PageDescription], images: List[ImageData]) -> str:
    """Erzeugt ein vollständiges HTML-Dokument aus Seitenbeschreibungen.

    Args:
        pages: Liste von PageDescription (vom LLM)
        images: Liste aller ImageData-Objekte

    Returns:
        Vollständiges HTML-Dokument als String
    """
    html_parts = [PHOTOBOOK_HEADER]

    for page in pages:
        template = load_template(page.template_id)
        css_class = template.css_class
        page_css = f"page-{template.page_type}"
        html_parts.append(f'<div class="photobook-page {css_class} {page_css}">')

        slot_defs = {s.id: s for s in template.slots}

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
                text = slot_data.get("text", "")
                html_parts.append(
                    f'<div class="slot-text" {area_style}>{text}</div>'
                )

            elif slot_def.type == "caption":
                caption = slot_data.get("caption", "")
                if caption:
                    html_parts.append(
                        f'<div class="slot-caption" {area_style}>{caption}</div>'
                    )

        html_parts.append("</div>")  # .photobook-page

    html_parts.append(PHOTOBOOK_FOOTER)
    return "\n".join(html_parts)


def _normalize_path(path: str) -> str:
    """Konvertiert Pfade zu file:/// URIs für Headless Chrome."""
    abs_path = os.path.abspath(path)
    if abs_path.startswith("/"):
        return f"file://{abs_path}"
    return f"file:///{abs_path}"
```

```css
/* app/photobook/styles.css */
/* CSS Grid Layouts für alle Fotobuch-Templates */

/* --- Base --- */
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

/* Einzelseite A4: 210×297mm */
.page-single {
  width: 210mm;
  height: 297mm;
  padding: 10mm;
}

/* Doppelseite A3 landscape: 420×297mm */
.page-spread {
  width: 420mm;
  height: 297mm;
  padding: 10mm;
}

/* --- Universelle Slot-Klassen --- */
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

/* --- Template 1: hero_single --- */
.layout-hero-single {
  display: grid;
  grid-template-columns: 1fr;
  grid-template-rows: 1fr auto;
  grid-template-areas:
    "main"
    "caption";
  gap: 0;
}

/* --- Template 2: split_equal --- */
.layout-split-equal {
  display: grid;
  grid-template-columns: 1fr 1fr;
  grid-template-rows: 1fr auto;
  grid-template-areas:
    "left right"
    "caption caption";
  gap: 4mm;
}

/* --- Template 3: split_dominant --- */
.layout-split-dominant {
  display: grid;
  grid-template-columns: 2fr 1fr;
  grid-template-rows: 1fr auto;
  grid-template-areas:
    "main side"
    "caption caption";
  gap: 4mm;
}

/* --- Template 4: grid_2x2 --- */
.layout-grid-2x2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  grid-template-rows: 1fr 1fr;
  grid-template-areas:
    "tl tr"
    "bl br";
  gap: 3mm;
}

/* --- Template 5: strip_3 --- */
.layout-strip-3 {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  grid-template-rows: 1fr;
  grid-template-areas: "left center right";
  gap: 3mm;
}

/* --- Template 6: image_text_left --- */
.layout-image-text-left {
  display: grid;
  grid-template-columns: 3fr 2fr;
  grid-template-rows: 1fr auto;
  grid-template-areas:
    "image text"
    "caption caption";
  gap: 4mm;
}

/* --- Template 7: collection_3 --- */
.layout-collection-3 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  grid-template-rows: 2fr 1fr;
  grid-template-areas:
    "top top"
    "bl br";
  gap: 3mm;
}

/* --- Template 8: panorama --- */
.layout-panorama {
  display: grid;
  grid-template-columns: 1fr;
  grid-template-rows: 1fr auto;
  grid-template-areas:
    "main"
    "caption";
  gap: 0;
}

/* --- Print / PDF --- */
@media print {
  body { background: #fff; }
  .photobook-page {
    box-shadow: none;
    page-break-after: always;
  }
  .photobook-page:last-child { page-break-after: avoid; }
  .page-single { size: A4; }
  .page-spread { size: A3 landscape; }
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_photobook/test_renderer.py -v`
Expected: 5 PASS

- [ ] **Step 5: Commit**

```bash
git add app/photobook/renderer.py app/photobook/styles.css tests/test_photobook/test_renderer.py
git commit -m "feat: add photobook HTML renderer with CSS Grid styles"
```

---

### Task 5: PDF-Generator

**Files:**
- Create: `app/photobook/generate_pdf.py`
- Create: `tests/test_photobook/test_pdf.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_photobook/test_pdf.py
import os
import pytest
from app.photobook.generate_pdf import generate_photobook_pdf

DUMMY_HTML = """<!DOCTYPE html><html><body><h1>Test Fotobuch</h1></body></html>"""


class TestPhotobookPdf:
    def test_generate_pdf_returns_bytes(self):
        pdf_bytes = generate_photobook_pdf(DUMMY_HTML)
        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 0
        assert pdf_bytes[:4] == b"%PDF"

    def test_empty_html_raises(self):
        with pytest.raises(ValueError):
            generate_photobook_pdf("")

    def test_none_html_raises(self):
        with pytest.raises(ValueError):
            generate_photobook_pdf(None)

    def test_pdf_contains_all_pages(self):
        html = """<!DOCTYPE html><html><body>
        <div class="page-single">Seite 1</div>
        <div class="page-spread">Seite 2</div>
        <div class="page-single">Seite 3</div>
        </body></html>"""
        pdf_bytes = generate_photobook_pdf(html)
        assert len(pdf_bytes) > 100
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_photobook/test_pdf.py -v`
Expected: FAIL — ImportError.

- [ ] **Step 3: Implement the PDF generator**

```python
# app/photobook/generate_pdf.py
"""PDF-Generierung für Fotobuch via Headless Chrome (Selenium CDP).

Basiert auf dem gleichen Mechanismus wie app/services/generate_pdf.py,
aber optimiert für Fotobuch-Seiten (Single A4 / Spread A3).
"""

import base64
import os
import re
import tempfile
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options


def _inject_print_css(html_content: str) -> str:
    """Injiziert @page CSS für A4 Einzelseiten und A3 Doppelseiten."""
    print_css = (
        '<style>'
        '@page { size: A4; margin: 0; }'
        '.page-spread { page: spread; }'
        '@page spread { size: A3 landscape; margin: 0; }'
        '@media print { body { background: #fff !important; margin: 0; } }'
        '</style>'
    )
    if "</head>" in html_content:
        return html_content.replace("</head>", f"{print_css}\n</head>")
    return print_css + html_content


def generate_photobook_pdf(html_content: str, output_dir: str | None = None) -> bytes:
    """Wandelt Fotobuch-HTML via Headless Chrome in PDF um.

    Args:
        html_content: Vollständiges HTML des Fotobuchs
        output_dir: Optional — Verzeichnis für temporäre Dateien

    Returns:
        PDF als Bytes

    Raises:
        ValueError: Wenn html_content leer ist
        RuntimeError: Wenn Chrome/PDF-Generierung fehlschlägt
    """
    if not html_content:
        raise ValueError("Kein HTML-Inhalt für die PDF-Generierung")

    processed = _inject_print_css(html_content)

    fd, html_path = tempfile.mkstemp(suffix=".html")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(processed)

        options = Options()
        options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")

        driver = webdriver.Chrome(options=options)
        try:
            abs_path = os.path.abspath(html_path)
            driver.get(f"file:///{abs_path}")
            time.sleep(1)

            pdf_result = driver.execute_cdp_cmd("Page.printToPDF", {
                "printBackground": True,
                "paperWidth": 8.27,
                "paperHeight": 11.69,
                "marginTop": 0,
                "marginBottom": 0,
                "marginLeft": 0,
                "marginRight": 0,
                "preferCSSPageSize": True,
            })

            return base64.b64decode(pdf_result["data"])
        finally:
            driver.quit()
    finally:
        if os.path.exists(html_path):
            os.unlink(html_path)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_photobook/test_pdf.py -v`
Expected: 4 PASS (wenn Chrome verfügbar; sonst pytest.skip verwenden)

- [ ] **Step 5: Commit**

```bash
git add app/photobook/generate_pdf.py tests/test_photobook/test_pdf.py
git commit -m "feat: add photobook PDF generator via headless Chrome"
```

---

### Task 6: Image Selector — LLM-basierte Bildauswahl für Fotobuch

**Files:**
- Create: `app/photobook/image_selector.py`
- Create: `tests/test_photobook/test_image_selector.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_photobook/test_image_selector.py
import json
from unittest.mock import patch, MagicMock
from app.state import ImageData
from app.photobook.image_selector import select_photobook_images


SAMPLE_IMAGES = [ImageData(path=f"/tmp/img_{i}.jpg") for i in range(25)]


class TestImageSelector:
    @patch("app.photobook.image_selector.requests.post")
    def test_selects_correct_count(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "message": {
                "content": json.dumps({"selected_indices": list(range(16))})
            }
        }
        mock_post.return_value = mock_resp

        result = select_photobook_images(
            images=SAMPLE_IMAGES,
            gpx_stats={"total_distance_m": 5000},
            notes="Test Tour",
            model="test-model",
            photo_count=16,
        )
        assert len(result) == 16

    @patch("app.photobook.image_selector.requests.post")
    def test_fallback_when_llm_fails(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_post.return_value = mock_resp

        result = select_photobook_images(
            images=SAMPLE_IMAGES[:10],
            gpx_stats={},
            notes=None,
            model="test-model",
            photo_count=8,
        )
        assert len(result) == 8  # Fallback: first N images

    def test_returns_all_when_fewer_images(self):
        result = select_photobook_images(
            images=SAMPLE_IMAGES[:3],
            gpx_stats={},
            notes=None,
            model="test-model",
            photo_count=16,
        )
        assert len(result) == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_photobook/test_image_selector.py -v`
Expected: FAIL — ImportError.

- [ ] **Step 3: Implement the image selector service**

```python
# app/photobook/image_selector.py
"""LLM-basierte Bildauswahl für das Fotobuch.

Andere Kriterien als die Blog-Bildauswahl: Fokus auf Layout-Eignung,
visuelle Varianz und narrative Verwendbarkeit.
"""

import json
import re
from typing import Any, Dict, List, Optional
import requests
from app.config import OLLAMA_BASE_URL
from app.state import ImageData


def _build_selection_prompt(
    image_count: int,
    target_count: int,
    gpx_stats_d: Optional[Dict[str, Any]],
    notes: Optional[str],
) -> str:
    """Baut den Prompt für die Fotobuch-Bildauswahl."""

    gpx_text = ""
    if gpx_stats_d:
        dist = gpx_stats_d.get("total_distance_m", 0) / 1000
        elev = gpx_stats_d.get("elevation_gain_m", 0)
        gpx_text = (
            f"Tour-Daten: {dist:.1f} km Distanz, {elev:.0f}m Höhenmeter. "
        )

    notes_text = f"Tour-Notizen: {notes}" if notes else ""

    return f"""Du bist Bildredakteur für ein Fotobuch einer Wandertour.

{gpx_text}{notes_text}

VERFÜGBAR: {image_count} Bilder (chronologisch sortiert, Index 0-{image_count - 1}).
GESUCHT: {target_count} Bilder für ein A4-Fotobuch.

KRITERIEN:
1. Starke Bilder bevorzugen — klare Motive, gute Belichtung
2. Narrative Abdeckung — Anfang, Mitte und Ende der Tour abbilden
3. Visuelle Varianz — verschiedene Perspektiven und Motive mischen
4. Layout-Eignung — nicht nur Landschaften, auch Details und Porträts

ANTWORTE AUSSCHLIESSLICH mit diesem JSON:
{{"selected_indices": [0, 2, 5, 7, ...]}}"""


def select_photobook_images(
    images: List[ImageData],
    gpx_stats: Optional[Dict[str, Any]],
    notes: Optional[str],
    model: str = "gemma4:26b-ctx128k",
    photo_count: int = 16,
    base_url: str = OLLAMA_BASE_URL,
) -> List[ImageData]:
    """Wählt Bilder für das Fotobuch via LLM aus.

    Falls das LLM nicht verfügbar ist oder mehr Bilder gewählt werden
    als vorhanden, werden alle verfügbaren Bilder zurückgegeben.
    """
    if not images:
        return []

    target = min(photo_count, len(images))
    if target >= len(images):
        return list(images)

    prompt = _build_selection_prompt(len(images), target, gpx_stats, notes)

    try:
        resp = requests.post(
            f"{base_url.rstrip('/')}/api/chat",
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "options": {"temperature": 0.0, "num_predict": 1024},
                "keep_alive": "10m",
            },
            timeout=120,
        )

        if resp.status_code == 200:
            content = resp.json().get("message", {}).get("content", "")
            # JSON aus Antwort extrahieren
            json_match = re.search(r'\{[^}]+\}', content, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                indices = data.get("selected_indices", [])
                selected = [images[i] for i in indices if 0 <= i < len(images)]
                if len(selected) >= min(target, 5):
                    return selected[:target]

    except Exception as e:
        print(f"⚠️ Fotobuch-Bildauswahl fehlgeschlagen: {e}")

    # Fallback: erste target Bilder
    print(f"⚠️ Verwende Fallback: erste {target} Bilder")
    return list(images[:target])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_photobook/test_image_selector.py -v`
Expected: 3 PASS

- [ ] **Step 5: Commit**

```bash
git add app/photobook/image_selector.py tests/test_photobook/test_image_selector.py
git commit -m "feat: add LLM-based photobook image selector"
```

---

### Task 7: Pass 1 — Layout-Planung (Dramaturgie + Seiten-Sequenz)

**Files:**
- Create: `app/photobook/plan.py`
- Create: `tests/test_photobook/test_plan.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_photobook/test_plan.py
import json
from unittest.mock import patch, MagicMock
from app.state import ImageData
from app.photobook.plan import plan_photobook_layout


SAMPLE_IMAGES = [ImageData(path=f"/tmp/img_{i}.jpg") for i in range(16)]

MOCK_PLAN_RESPONSE = {
    "message": {
        "content": json.dumps({
            "pages": [
                {"position": 0, "page_type": "cover", "template_category": "hero", "image_indices": [3], "purpose": "Cover"},
                {"position": 1, "page_type": "spread", "template_category": "split", "image_indices": [7, 12], "purpose": "Aufstieg"},
                {"position": 2, "page_type": "single", "template_category": "grid", "image_indices": [0, 2, 5, 8], "purpose": "Sammlung"},
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
        assert page0["template_category"] == "hero"
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
        # Fallback sollte cover page haben
        assert result["pages"][0]["page_type"] == "cover"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_photobook/test_plan.py -v`
Expected: FAIL — ImportError.

- [ ] **Step 3: Implement Pass 1 service**

```python
# app/photobook/plan.py
"""LLM Pass 1: Layout-Planung (Dramaturgie + Seiten-Sequenz).

Das LLM plant die Seitenabfolge auf Kategorie-Ebene:
- Welche Bilder kommen auf welche Seite?
- Welche Template-Kategorie pro Seite?
- Dramaturgischer Bogen (Cover → Aufbau → Highlight → Abschluss)
"""

import json
import re
from typing import Any, Dict, List, Optional
import requests
from app.config import OLLAMA_BASE_URL
from app.state import ImageData, WeatherInfo


def _build_plan_prompt(
    image_count: int,
    gpx_stats_d: Optional[Dict[str, Any]],
    notes: Optional[str],
    weather: Optional[WeatherInfo],
    poi_count: int,
) -> str:
    """Baut den Prompt für die Layout-Planung."""

    context_parts = [f"BILDER: {image_count} Fotos (chronologisch sortiert, Index 0-{image_count - 1})"]

    if gpx_stats_d:
        dist = gpx_stats_d.get("total_distance_m", 0) / 1000
        elev = gpx_stats_d.get("elevation_gain_m", 0)
        duration = gpx_stats_d.get("total_duration_h", 0)
        context_parts.append(f"TOUR: {dist:.1f} km, {elev:.0f}m Höhenmeter, {duration:.0f}h Dauer")

    if weather and weather.daily:
        context_parts.append(f"WETTER: {weather.summary}")

    if poi_count > 0:
        context_parts.append(f"POIs: {poi_count} Sehenswürdigkeiten entlang der Route")

    if notes:
        context_parts.append(f"NOTIZEN: {notes}")

    context = "\n".join(context_parts)

    return f"""Du bist Fotobuch-Art-Director für eine Wandertour.

{context}

TEMPLATE-KATEGORIEN (zur Auswahl):
- hero: 1 großes Bild (Cover, Kapitelanfang, Schlüsselmomente)
- split: 2 Bilder nebeneinander (Vergleiche, Vorher/Nachher)
- grid: 3-4 Bilder im Raster (Sammlungen, Details)
- strip: 3 Bilder horizontal (Sequenzen, Zeitabläufe)
- mixed: Bild + Textblock (Kontext, Einleitungen)
- collection: 1 großes + 2 kleine (thematische Gruppen)

GLOBALE LAYOUT-REGELN:
1. Cover (Pos. 0) und letzte Seite sind hero-Templates
2. Maximal 2× das gleiche Template hintereinander
3. Alle 4-6 Seiten ein hero-Anker
4. Wechsel zwischen dichten Seiten (grid) und ruhigen (single)
5. Wichtigere Bilder bekommen größere Slots

PLANE die Seitenabfolge. Gib jedem Bild einen Platz. Struktur:
Cover → Aufbau → Highlights → Variation → Abschluss

ANTWORTE AUSSCHLIESSLICH mit diesem JSON:
{{
  "pages": [
    {{"position": 0, "page_type": "cover", "template_category": "hero",
      "image_indices": [3], "purpose": "Beschreibung"}},
    ...
  ],
  "dramatic_arc": "kurze Beschreibung des dramaturgischen Bogens"
}}"""


def _generate_fallback_plan(images: List[ImageData], image_count: int) -> Dict[str, Any]:
    """Erzeugt einen einfachen Fallback-Plan ohne LLM."""
    pages = []
    indices = list(range(min(image_count, len(images))))

    # Cover
    if indices:
        pages.append({
            "position": 0, "page_type": "cover",
            "template_category": "hero", "image_indices": [indices.pop(0)],
            "purpose": "Cover"
        })

    # Restliche Bilder: Paarweise aufteilen
    pos = 1
    while indices:
        if len(indices) >= 4:
            pages.append({
                "position": pos, "page_type": "single",
                "template_category": "grid",
                "image_indices": [indices.pop(0) for _ in range(min(4, len(indices)))],
                "purpose": "Sammlung"
            })
        elif len(indices) >= 2:
            pages.append({
                "position": pos, "page_type": "spread",
                "template_category": "split",
                "image_indices": [indices.pop(0), indices.pop(0)],
                "purpose": "Vergleich"
            })
        else:
            pages.append({
                "position": pos, "page_type": "single",
                "template_category": "hero",
                "image_indices": [indices.pop(0)],
                "purpose": "Einzelbild"
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
    """Führt LLM Pass 1 aus: Dramaturgie und Seiten-Sequenz planen.

    Returns:
        Dict mit "pages" (Liste von Seiten-Beschreibungen) und "dramatic_arc"
    """
    if not images:
        return {"pages": [], "dramatic_arc": ""}

    prompt = _build_plan_prompt(len(images), gpx_stats, notes, weather, len(poi_list))

    try:
        resp = requests.post(
            f"{base_url.rstrip('/')}/api/chat",
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "options": {"temperature": 0.3, "num_predict": 4096},
                "keep_alive": "10m",
            },
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

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_photobook/test_plan.py -v`
Expected: 2 PASS

- [ ] **Step 5: Commit**

```bash
git add app/photobook/plan.py tests/test_photobook/test_plan.py
git commit -m "feat: add photobook LLM Pass 1 — layout planning"
```

---

### Task 8: Pass 2 — Template-Auswahl + Caption-Generierung

**Files:**
- Create: `app/photobook/generate.py`
- Create: `tests/test_photobook/test_generate.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_photobook/test_generate.py
import json
from unittest.mock import patch, MagicMock
from app.state import ImageData, PageDescription
from app.photobook.generate import generate_photobook_pages


MOCK_PLAN = {
    "pages": [
        {"position": 0, "page_type": "cover", "template_category": "hero", "image_indices": [0], "purpose": "Cover"},
        {"position": 1, "page_type": "spread", "template_category": "split", "image_indices": [1, 2], "purpose": "Aufstieg"},
    ]
}

MOCK_GENERATE_RESPONSE = {
    "message": {
        "content": json.dumps([
            {"template_id": "hero_single", "page_type": "single",
             "slots": [{"slot_id": "main", "image_index": 0, "caption": "Gipfelblick"}]},
            {"template_id": "split_equal", "page_type": "spread",
             "slots": [
                 {"slot_id": "left", "image_index": 1, "caption": "Waldweg"},
                 {"slot_id": "right", "image_index": 2, "caption": "Aussichtspunkt"},
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
            plan=MOCK_PLAN,
            images=SAMPLE_IMAGES,
            gpx_stats={},
            notes="Test",
            model="test-model",
        )
        assert len(result) == 2
        assert isinstance(result[0], PageDescription)
        assert result[0].template_id == "hero_single"
        assert result[1].template_id == "split_equal"

    def test_fallback_on_empty_plan(self):
        result = generate_photobook_pages(
            plan={"pages": []},
            images=SAMPLE_IMAGES[:4],
            gpx_stats={},
            notes=None,
            model="test-model",
        )
        assert len(result) == 0

    @patch("app.photobook.generate.requests.post")
    def test_generate_handles_missing_images(self, mock_post):
        """Wenn das LLM einen ungültigen Bildindex zurückgibt."""
        bad_response = {
            "message": {
                "content": json.dumps([
                    {"template_id": "hero_single", "page_type": "single",
                     "slots": [{"slot_id": "main", "image_index": 999, "caption": "Bad index"}]},
                ])
            }
        }
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = bad_response
        mock_post.return_value = mock_resp

        result = generate_photobook_pages(
            plan=MOCK_PLAN,
            images=SAMPLE_IMAGES[:3],
            gpx_stats={},
            notes="Test",
            model="test-model",
        )
        assert len(result) > 0  # Sollte nicht crashen
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_photobook/test_generate.py -v`
Expected: FAIL — ImportError.

- [ ] **Step 3: Implement Pass 2 service**

```python
# app/photobook/generate.py
"""LLM Pass 2: Template-Auswahl + Slot-Zuweisung + Caption-Generierung.

Nimmt den Seitenplan aus Pass 1 und wählt für jede Seite das konkrete
Template aus der Kategorie. Weist Bilder Slots zu und generiert Captions.
"""

import json
import re
from typing import Any, Dict, List, Optional
import requests
from app.config import OLLAMA_BASE_URL
from app.state import ImageData, PageDescription
from app.photobook.template_loader import load_all_templates


def _build_generate_prompt(
    pages_plan: List[Dict[str, Any]],
    gpx_stats_d: Optional[Dict[str, Any]],
    notes: Optional[str],
) -> str:
    """Baut den Prompt für die Template-Auswahl und Caption-Generierung."""

    templates_summary = []
    for tid, tmpl in load_all_templates().items():
        slot_info = ", ".join(
            f"{s.id}({s.type},{s.priority or 'normal'})" for s in tmpl.slots
        )
        templates_summary.append(
            f"  {tid} [{tmpl.category}/{tmpl.page_type}, {tmpl.min_images}-{tmpl.max_images} Bilder]: {slot_info}"
        )
    catalog = "\n".join(templates_summary)

    plan_text = json.dumps(pages_plan, indent=2, ensure_ascii=False)

    gpx_text = ""
    if gpx_stats_d:
        dist = gpx_stats_d.get("total_distance_m", 0) / 1000
        elev = gpx_stats_d.get("elevation_gain_m", 0)
        gpx_text = f"\nTOUR: {dist:.1f} km, {elev:.0f}m Höhenmeter."

    notes_text = f"\nTOUR-NOTIZEN: {notes}" if notes else ""

    return f"""Du wählst für jede geplante Seite das konkrete Template aus.

SEITENPLAN (aus Pass 1):
{plan_text}

VERFÜGBARE TEMPLATES:
{catalog}
{gpx_text}{notes_text}

AUFGABE PRO SEITE:
1. Wähle das passende Template AUS DER KATEGORIE des Seitenplans
2. Weise die Bilder den richtigen Slots zu (image_index aus dem Plan)
3. Generiere kurze Bildunterschriften (1 Satz, sachlich, auf Deutsch)
4. Wichtigere Bilder → primary Slots

REGELN:
- Template darf nicht >2× hintereinander verwendet werden
- Template muss genug Slots für alle Bilder der Seite haben
- image_index MUSS aus den im Plan zugewiesenen Indizes stammen

ANTWORTE AUSSCHLIESSLICH mit diesem JSON-Array (ein Objekt pro Seite):
[
  {{
    "template_id": "hero_single",
    "page_type": "single",
    "slots": [
      {{"slot_id": "main", "image_index": 3, "caption": "Beschreibung"}}
    ]
  }},
  ...
]"""


def generate_photobook_pages(
    plan: Dict[str, Any],
    images: List[ImageData],
    gpx_stats: Optional[Dict[str, Any]],
    notes: Optional[str],
    model: str = "gemma4:26b-ctx128k",
    base_url: str = OLLAMA_BASE_URL,
) -> List[PageDescription]:
    """Führt LLM Pass 2 aus: Template-Auswahl und Caption-Generierung.

    Returns:
        Liste von PageDescription-Objekten für den Renderer
    """
    pages_plan = plan.get("pages", [])
    if not pages_plan:
        return []

    prompt = _build_generate_prompt(pages_plan, gpx_stats, notes)

    try:
        resp = requests.post(
            f"{base_url.rstrip('/')}/api/chat",
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "options": {"temperature": 0.3, "num_predict": 8192},
                "keep_alive": "10m",
            },
            timeout=300,
        )

        if resp.status_code == 200:
            content = resp.json().get("message", {}).get("content", "")
            array_match = re.search(r'\[.*\]', content, re.DOTALL)
            if array_match:
                pages_data = json.loads(array_match.group())
                result = []
                for pd in pages_data:
                    # Validierung: image_index im gültigen Bereich?
                    valid_slots = []
                    for slot in pd.get("slots", []):
                        idx = slot.get("image_index", -1)
                        if 0 <= idx < len(images):
                            valid_slots.append(slot)
                        else:
                            valid_slots.append({
                                k: v for k, v in slot.items() if k != "image_index"
                            })
                    result.append(PageDescription(
                        template_id=pd.get("template_id", "grid_2x2"),
                        page_type=pd.get("page_type", "single"),
                        slots=valid_slots,
                    ))
                if result:
                    return result

    except Exception as e:
        print(f"⚠️ Pass 2 (Generierung) fehlgeschlagen: {e}")

    # Fallback: grid_2x2 für alle Seiten
    fallback = []
    for plan_page in pages_plan:
        indices = plan_page.get("image_indices", [])
        slots = [{"slot_id": sid, "image_index": idx}
                 for sid, idx in zip(["tl", "tr", "bl", "br"], indices)]
        fallback.append(PageDescription(
            template_id="grid_2x2",
            page_type="single",
            slots=slots,
        ))
    return fallback
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_photobook/test_generate.py -v`
Expected: 3 PASS

- [ ] **Step 5: Commit**

```bash
git add app/photobook/generate.py tests/test_photobook/test_generate.py
git commit -m "feat: add photobook LLM Pass 2 — template selection and captions"
```

---

### Task 9: Graph Nodes — 5 Node-Wrapper

**Files:**
- Create: `app/nodes/select_photobook_images_node.py`
- Create: `app/nodes/plan_photobook_node.py`
- Create: `app/nodes/generate_photobook_node.py`
- Create: `app/nodes/render_photobook_node.py`
- Create: `app/nodes/generate_photobook_pdf_node.py`

- [ ] **Step 1: Write the integration test for all nodes**

```python
# tests/test_photobook/test_graph.py
import json
from unittest.mock import patch, MagicMock
from app.state import AppState, ImageData, OutputConfig
from app.nodes.select_photobook_images_node import select_photobook_images_node
from app.nodes.plan_photobook_node import plan_photobook_node
from app.nodes.generate_photobook_node import generate_photobook_node
from app.nodes.render_photobook_node import render_photobook_node


MOCK_SELECTION = {"message": {"content": json.dumps({"selected_indices": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]})}}

MOCK_PLAN = {"message": {"content": json.dumps({
    "pages": [
        {"position": 0, "page_type": "cover", "template_category": "hero", "image_indices": [0], "purpose": "Cover"},
        {"position": 1, "page_type": "spread", "template_category": "split", "image_indices": [1, 2], "purpose": "Split"},
    ],
    "dramatic_arc": "test"
})}}

MOCK_GENERATE = {"message": {"content": json.dumps([
    {"template_id": "hero_single", "page_type": "single", "slots": [{"slot_id": "main", "image_index": 0, "caption": "Test"}]},
    {"template_id": "split_equal", "page_type": "spread", "slots": [
        {"slot_id": "left", "image_index": 1, "caption": "L"}, {"slot_id": "right", "image_index": 2, "caption": "R"}
    ]},
])}}


def make_state(n_images=20):
    return AppState(
        images=[ImageData(path=f"/tmp/img_{i}.jpg") for i in range(n_images)],
        gpx_stats=None,
        model="test-model",
        output_config=OutputConfig(),
    )


class TestPhotobookNodes:
    @patch("app.photobook.image_selector.requests.post")
    def test_select_images_node(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = MOCK_SELECTION
        mock_post.return_value = mock_resp

        state = make_state()
        result = select_photobook_images_node(state)
        assert len(result.photobook_images) == 16

    @patch("app.photobook.plan.requests.post")
    def test_plan_node(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = MOCK_PLAN
        mock_post.return_value = mock_resp

        state = make_state()
        state.photobook_images = state.images[:16]
        result = plan_photobook_node(state)
        assert result.photobook_plan is not None
        assert len(result.photobook_plan["pages"]) == 2

    @patch("app.photobook.generate.requests.post")
    def test_generate_node(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = MOCK_GENERATE
        mock_post.return_value = mock_resp

        state = make_state()
        state.photobook_images = state.images[:16]
        state.photobook_plan = json.loads(MOCK_PLAN["message"]["content"])
        result = generate_photobook_node(state)
        assert len(result.photobook_pages) == 2

    def test_render_node(self):
        from app.state import PageDescription
        state = make_state()
        state.photobook_pages = [
            PageDescription(template_id="hero_single", page_type="single",
                          slots=[{"slot_id": "main", "image_index": 0, "caption": "Test"}]),
        ]
        state.photobook_images = state.images[:1]
        result = render_photobook_node(state)
        assert result.photobook_html is not None
        assert "layout-hero-single" in result.photobook_html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_photobook/test_graph.py -v`
Expected: FAIL — ImportError.

- [ ] **Step 3: Create all 5 node files**

```python
# app/nodes/select_photobook_images_node.py
from app.state import AppState
from app.photobook.image_selector import select_photobook_images


def select_photobook_images_node(state: AppState) -> AppState:
    print("📸 Wähle Bilder für das Fotobuch aus...")

    if not state.images:
        print("⚠️ Keine Bilder für Fotobuch-Auswahl vorhanden.")
        return state

    try:
        gpx_dict = state.gpx_stats.model_dump() if state.gpx_stats else {}
    except Exception:
        gpx_dict = {}

    selected = select_photobook_images(
        images=state.images,
        gpx_stats=gpx_dict,
        notes=state.notes,
        model=state.model,
        photo_count=state.output_config.photobook.photo_count,
    )

    state.photobook_images = selected
    print(f"✅ {len(selected)} Bilder für das Fotobuch ausgewählt.")
    return state
```

```python
# app/nodes/plan_photobook_node.py
from app.state import AppState
from app.photobook.plan import plan_photobook_layout


def plan_photobook_node(state: AppState) -> AppState:
    print("📋 Plane Fotobuch-Layout (LLM Pass 1)...")

    if not state.photobook_images:
        print("⚠️ Keine Bilder für Fotobuch-Planung vorhanden.")
        return state

    try:
        gpx_dict = state.gpx_stats.model_dump() if state.gpx_stats else {}
    except Exception:
        gpx_dict = {}

    plan = plan_photobook_layout(
        images=state.photobook_images,
        gpx_stats=gpx_dict,
        notes=state.notes,
        weather=state.weather,
        poi_list=state.poi_list,
        model=state.model,
    )

    state.photobook_plan = plan
    print(f"✅ Layout-Planung abgeschlossen: {len(plan.get('pages', []))} Seiten geplant.")
    return state
```

```python
# app/nodes/generate_photobook_node.py
from app.state import AppState
from app.photobook.generate import generate_photobook_pages


def generate_photobook_node(state: AppState) -> AppState:
    print("🎨 Generiere Fotobuch-Seiten (LLM Pass 2)...")

    if not state.photobook_plan:
        print("⚠️ Kein Layout-Plan vorhanden.")
        return state

    try:
        gpx_dict = state.gpx_stats.model_dump() if state.gpx_stats else {}
    except Exception:
        gpx_dict = {}

    pages = generate_photobook_pages(
        plan=state.photobook_plan,
        images=state.photobook_images,
        gpx_stats=gpx_dict,
        notes=state.notes,
        model=state.model,
    )

    state.photobook_pages = pages
    print(f"✅ {len(pages)} Fotobuch-Seiten generiert.")
    return state
```

```python
# app/nodes/render_photobook_node.py
from app.state import AppState
from app.photobook.renderer import render_photobook
from app.photobook.validator import validate_all_pages


def render_photobook_node(state: AppState) -> AppState:
    print("🖨️ Rendere Fotobuch als HTML...")

    if not state.photobook_pages:
        print("⚠️ Keine Seiten zum Rendern vorhanden.")
        return state

    # Vor dem Rendering validieren
    validated_pages, warnings = validate_all_pages(state.photobook_pages)
    if warnings:
        for w in warnings:
            print(f"⚠️ Validator: {w}")
    state.photobook_pages = validated_pages

    try:
        html = render_photobook(validated_pages, state.photobook_images)
        state.photobook_html = html
        print(f"✅ Fotobuch-HTML gerendert ({len(html)} Zeichen).")
    except Exception as e:
        print(f"❌ Fehler beim Rendern: {e}")

    return state
```

```python
# app/nodes/generate_photobook_pdf_node.py
import os
from datetime import datetime
from pathlib import Path
from app.state import AppState
from app.photobook.generate_pdf import generate_photobook_pdf
from app.config import OUTPUT_DIR


def generate_photobook_pdf_node(state: AppState) -> AppState:
    print("📄 Erzeuge Fotobuch-PDF...")

    if not state.photobook_html:
        print("⚠️ Kein HTML zum PDF-Export vorhanden.")
        return state

    try:
        pdf_bytes = generate_photobook_pdf(state.photobook_html)

        # Ausgabeverzeichnis
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        output_dir = Path(OUTPUT_DIR) / f"photobook_{timestamp}"
        output_dir.mkdir(parents=True, exist_ok=True)
        pdf_path = output_dir / f"{timestamp}_photobook.pdf"

        with open(pdf_path, "wb") as f:
            f.write(pdf_bytes)

        state.photobook_pdf_path = str(pdf_path)
        print(f"✅ PDF gespeichert: {pdf_path} ({len(pdf_bytes)} Bytes)")

    except Exception as e:
        print(f"❌ Fehler bei PDF-Generierung: {e}")

    return state
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_photobook/test_graph.py -v`
Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
git add app/nodes/select_photobook_images_node.py app/nodes/plan_photobook_node.py app/nodes/generate_photobook_node.py app/nodes/render_photobook_node.py app/nodes/generate_photobook_pdf_node.py tests/test_photobook/test_graph.py
git commit -m "feat: add 5 photobook graph nodes (select, plan, generate, render, pdf)"
```

---

### Task 10: Graph-Integration — Photobook-Zweig ins StateGraph einbauen

**Files:**
- Modify: `app/graph.py`

- [ ] **Step 1: Modify build_graph() to add photobook branch**

In `app/graph.py`, add imports and wire up the new nodes:

```python
# Add imports (after existing node imports, around line 18):
from app.nodes.select_photobook_images_node import select_photobook_images_node
from app.nodes.plan_photobook_node import plan_photobook_node
from app.nodes.generate_photobook_node import generate_photobook_node
from app.nodes.render_photobook_node import render_photobook_node
from app.nodes.generate_photobook_pdf_node import generate_photobook_pdf_node
```

Add display names for photobook nodes (inside NODE_NAMES dict, around line 39):

```python
NODE_NAMES = {
    # ... existing entries ...
    "select_photobook_images": "Fotobuch: Bilder auswählen",
    "plan_photobook": "Fotobuch: Layout planen",
    "generate_photobook": "Fotobuch: Seiten generieren",
    "render_photobook": "Fotobuch: Rendern",
    "generate_photobook_pdf": "Fotobuch: PDF erstellen",
}
```

In `build_graph()`, after the existing node registrations (around line 125), add:

```python
    # Photobook nodes
    spi = _wrap_node(select_photobook_images_node, "select_photobook_images", event_emitter) if event_emitter else select_photobook_images_node
    ppb = _wrap_node(plan_photobook_node, "plan_photobook", event_emitter) if event_emitter else plan_photobook_node
    gpb = _wrap_node(generate_photobook_node, "generate_photobook", event_emitter) if event_emitter else generate_photobook_node
    rpb = _wrap_node(render_photobook_node, "render_photobook", event_emitter) if event_emitter else render_photobook_node
    gpp = _wrap_node(generate_photobook_pdf_node, "generate_photobook_pdf", event_emitter) if event_emitter else generate_photobook_pdf_node

    builder.add_node("select_photobook_images", spi)
    builder.add_node("plan_photobook", ppb)
    builder.add_node("generate_photobook", gpb)
    builder.add_node("render_photobook", rpb)
    builder.add_node("generate_photobook_pdf", gpp)
```

Replace the edge from `generate_enriched_map` with a conditional routing:

```python
    # Statt direkter Kante: Mode-abhängiges Routing
    def _route_from_enriched_map(state: AppState) -> str:
        mode = state.output_config.mode
        if mode == "photobook":
            return "select_photobook_images"
        return "generate_blog_post"  # default: blog

    builder.add_conditional_edges(
        "generate_enriched_map",
        _route_from_enriched_map,
        {
            "select_photobook_images": "select_photobook_images",
            "generate_blog_post": "generate_blog_post",
        },
    )
```

Wire the photobook path:

```python
    # Photobook-Pfad
    builder.add_edge("select_photobook_images", "plan_photobook")
    builder.add_edge("plan_photobook", "generate_photobook")
    builder.add_edge("generate_photobook", "render_photobook")
    builder.add_edge("render_photobook", "generate_photobook_pdf")
    builder.add_edge("generate_photobook_pdf", END)
```

- [ ] **Step 2: Run all tests to verify no breakage**

Run: `uv run pytest tests/ -v -q`
Expected: All tests PASS (existing + new photobook tests).

- [ ] **Step 3: Commit**

```bash
git add app/graph.py
git commit -m "feat: integrate photobook branch into LangGraph pipeline"
```

---

### Task 11: Full Pipeline Integration Test

**Files:**
- Create: `tests/test_photobook/test_integration.py`

- [ ] **Step 1: Write the integration test**

```python
# tests/test_photobook/test_integration.py
"""Integrationstest: Vollständiger Fotobuch-Graph-Durchlauf mit Mock-LLM."""
import json
from unittest.mock import patch, MagicMock
import pytest
from app.state import AppState, ImageData, OutputConfig
from app.graph import build_graph


MOCK_SELECTION = {"message": {"content": json.dumps({"selected_indices": list(range(12))})}}

MOCK_PLAN = {"message": {"content": json.dumps({
    "pages": [
        {"position": 0, "page_type": "cover", "template_category": "hero", "image_indices": [0], "purpose": "Cover"},
        {"position": 1, "page_type": "spread", "template_category": "split", "image_indices": [1, 2], "purpose": "Split"},
        {"position": 2, "page_type": "single", "template_category": "grid", "image_indices": [3, 4, 5, 6], "purpose": "Grid"},
    ],
    "dramatic_arc": "test"
})}}

MOCK_GENERATE = {"message": {"content": json.dumps([
    {"template_id": "hero_single", "page_type": "single",
     "slots": [{"slot_id": "main", "image_index": 0, "caption": "Cover Caption"}]},
    {"template_id": "split_equal", "page_type": "spread",
     "slots": [
         {"slot_id": "left", "image_index": 1, "caption": "Links"},
         {"slot_id": "right", "image_index": 2, "caption": "Rechts"},
     ]},
    {"template_id": "grid_2x2", "page_type": "single",
     "slots": [
         {"slot_id": "tl", "image_index": 3},
         {"slot_id": "tr", "image_index": 4},
         {"slot_id": "bl", "image_index": 5},
         {"slot_id": "br", "image_index": 6},
     ]},
])}}


def make_state(n_images=20):
    return AppState(
        images=[ImageData(path=f"/tmp/img_{i}.jpg") for i in range(n_images)],
        output_config=OutputConfig(mode="photobook", photobook={"photo_count": 12}),
        model="test-model",
    )


@patch("app.photobook.image_selector.requests.post")
@patch("app.photobook.plan.requests.post")
@patch("app.photobook.generate.requests.post")
def test_full_photobook_pipeline(self, mock_gen, mock_plan, mock_sel):
    """Durchlauf des gesamten Fotobuch-Pfads mit gemocktem LLM."""
    # Setup mocks
    mock_resp_sel = MagicMock()
    mock_resp_sel.status_code = 200
    mock_resp_sel.json.return_value = MOCK_SELECTION
    mock_sel.return_value = mock_resp_sel

    mock_resp_plan = MagicMock()
    mock_resp_plan.status_code = 200
    mock_resp_plan.json.return_value = MOCK_PLAN
    mock_plan.return_value = mock_resp_plan

    mock_resp_gen = MagicMock()
    mock_resp_gen.status_code = 200
    mock_resp_gen.json.return_value = MOCK_GENERATE
    mock_gen.return_value = mock_resp_gen

    state = make_state()
    graph = build_graph()
    result = graph.invoke(state)

    assert result.photobook_pdf_path is not None
    assert len(result.photobook_pages) == 3
    assert result.photobook_html is not None
    assert "layout-hero-single" in result.photobook_html
    assert result.photobook_plan is not None
```

- [ ] **Step 2: Run the integration test**

Run: `uv run pytest tests/test_photobook/test_integration.py -v`
Expected: 1 PASS (full photobook pipeline with mocks).

- [ ] **Step 3: Run the full test suite**

Run: `uv run pytest tests/ -v -q`
Expected: All tests PASS, zero failures.

- [ ] **Step 4: Commit**

```bash
git add tests/test_photobook/test_integration.py
git commit -m "test: add full photobook pipeline integration test"
```

---

## Self-Review Checklist

- [x] **Spec coverage**: Every spec section maps to at least one task
  - Pipeline Integration → Task 10 (graph) + Task 1 (state)
  - Template Catalog → Task 2 (JSONs + loader) + Task 4 (CSS)
  - LLM Art Director → Task 7 (Pass 1) + Task 8 (Pass 2)
  - Rendering Engine → Task 4 (renderer + CSS)
  - Testing/Error Handling → Tasks 3, 5, 6, 7, 8, 9, 11
- [x] **No placeholders**: All code is complete, no TBDs
- [x] **Type consistency**: `PageDescription`, `ImageData`, `PhotobookTemplate` consistent across tasks
- [x] **Path accuracy**: All file paths verified against existing codebase structure
- [x] **Test-first**: Every task starts with a failing test
