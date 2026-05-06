# Photobook Layout Redesign — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 18-Preset-Fotobuch mit universellem Seitentitel oben, konsistenten 70/30-Bild/Text-Verhältnissen und gestapelten (nicht nebeneinander liegenden) Multi-Bild-Layouts.

**Architecture:** Renderer wrappt jede Seite in `<div class="page-header">` + `<div class="page-content preset-X">`. CSS macht `.page-single` zum Flex-Column. Alle 18 Preset-JSONs werden neu geschrieben/umbenannt. Validator stellt sicher, dass jeder title-Slot befüllt ist.

**Tech Stack:** Python 3.12, CSS Grid, Pydantic, Pytest

---

### Task 1: Preset-JSON-Dateien aktualisieren (18 Dateien)

**Files:**
- Modify: `app/photobook/preset_data/cover_hero.json`
- Modify: `app/photobook/preset_data/single_full.json`
- Modify: `app/photobook/preset_data/single_text_below.json`
- Rename: `single_text_right.json` → `single_text_left.json` (Text links statt rechts)
- Modify: `app/photobook/preset_data/panorama.json`
- Modify: `app/photobook/preset_data/image_text_split.json`
- Rename: `double_equal.json` → `double_stacked.json`
- Create: `app/photobook/preset_data/double_stacked_text.json`
- Delete: `app/photobook/preset_data/double_dominant.json`
- Modify: `app/photobook/preset_data/double_text_right.json`
- Modify: `app/photobook/preset_data/map_focus.json`
- Rename: `triple_strip.json` → `triple_stacked.json`
- Rename: `triple_text_right.json` → `triple_stacked_text.json`
- Modify: `app/photobook/preset_data/triple_big_top.json`
- Modify: `app/photobook/preset_data/triple_big_text_below.json`
- Delete: `app/photobook/preset_data/triple_text_below.json`
- Modify: `app/photobook/preset_data/quad_grid.json`
- Create: `app/photobook/preset_data/quad_grid_text.json`
- Delete: `app/photobook/preset_data/quad_strip_text_below.json`
- Modify: `app/photobook/preset_data/quad_large_plus_3.json`
- Modify: `app/photobook/preset_data/collage_5.json`

- [ ] **Step 1: cover_hero — Vollbild ohne Text-Slot**

```json
{
  "id": "cover_hero",
  "name": "Cover — Hero",
  "description": "Vollbild-Titelseite. Der Titel kommt aus dem universellen page-header.",
  "image_count": 1,
  "has_text": false,
  "css_class": "preset-cover-hero",
  "slots": [
    {"id": "main", "type": "image", "priority": "primary", "css_area": "main", "optional": false}
  ]
}
```

Änderung: `has_text` von `true` auf `false`, title-Slot entfernt (kommt jetzt aus page-header).

- [ ] **Step 2: single_full — unverändert (kein title-Slot, nie einen gehabt)**

Prüfen dass kein title-Slot existiert. Bleibt wie es ist.

- [ ] **Step 3: single_text_below — unverändert**

Prüfen: caption-Slot unverändert. Kein title-Slot.

- [ ] **Step 4: single_text_left — NEU (ersetzt single_text_right)**

```bash
mv app/photobook/preset_data/single_text_right.json app/photobook/preset_data/single_text_left.json
```

```json
{
  "id": "single_text_left",
  "name": "Einzelbild + Text links",
  "description": "Text links (30%), Bild rechts (70%).",
  "image_count": 1,
  "has_text": true,
  "css_class": "preset-single-text-left",
  "slots": [
    {"id": "text", "type": "text", "css_area": "text", "char_limit": 170, "font_size": "9pt", "text_role": "caption", "optional": true},
    {"id": "main", "type": "image", "priority": "primary", "css_area": "main", "optional": false}
  ]
}
```

- [ ] **Step 5: panorama — Text nach oben, doppelt so groß**

```json
{
  "id": "panorama",
  "name": "Panorama",
  "description": "Einleitungstext oben (25%), Breitformat-Bild darunter (75%).",
  "image_count": 1,
  "has_text": true,
  "css_class": "preset-panorama",
  "slots": [
    {"id": "caption", "type": "text", "css_area": "caption", "char_limit": 200, "font_size": "10pt", "text_role": "caption", "optional": true},
    {"id": "main", "type": "image", "priority": "primary", "css_area": "main", "optional": false}
  ]
}
```

Änderung: char_limit 100→200, font_size 9pt→10pt, Slots umsortiert (caption zuerst).

- [ ] **Step 6: image_text_split — 70:30 Text rechts**

```json
{
  "id": "image_text_split",
  "name": "Bild + Text — 70:30",
  "description": "Bild links (70%), Einleitungstext rechts (30%). Für Kapitelanfänge.",
  "image_count": 1,
  "has_text": true,
  "css_class": "preset-image-text-split",
  "slots": [
    {"id": "image", "type": "image", "priority": "primary", "css_area": "image", "optional": false},
    {"id": "text", "type": "text", "css_area": "text", "char_limit": 400, "font_size": "11pt", "text_role": "intro", "optional": false}
  ]
}
```

Änderung: Beschreibung von "50:50" auf "70:30". CSS-Klasse bleibt `preset-image-text-split` (CSS wird in Task 3 angepasst).

- [ ] **Step 7: double_stacked — 2 übereinander (ersetzt double_equal)**

```bash
mv app/photobook/preset_data/double_equal.json app/photobook/preset_data/double_stacked.json
```

```json
{
  "id": "double_stacked",
  "name": "Zwei übereinander",
  "description": "Zwei Bilder vertikal gestapelt, je 50% Höhe. Keine Text-Slots.",
  "image_count": 2,
  "has_text": false,
  "css_class": "preset-double-stacked",
  "slots": [
    {"id": "top", "type": "image", "priority": "primary", "css_area": "top", "optional": false},
    {"id": "bottom", "type": "image", "priority": "secondary", "css_area": "bottom", "optional": false}
  ]
}
```

Slot-IDs: `top`, `bottom` (statt `left`, `right`).

- [ ] **Step 8: double_stacked_text — NEU**

```json
{
  "id": "double_stacked_text",
  "name": "Zwei übereinander + Text",
  "description": "Zwei Bilder vertikal gestapelt (70%) mit Bildunterschrift darunter (30%).",
  "image_count": 2,
  "has_text": true,
  "css_class": "preset-double-stacked-text",
  "slots": [
    {"id": "top", "type": "image", "priority": "primary", "css_area": "top", "optional": false},
    {"id": "bottom", "type": "image", "priority": "secondary", "css_area": "bottom", "optional": false},
    {"id": "caption", "type": "text", "css_area": "caption", "char_limit": 170, "font_size": "9pt", "text_role": "caption", "optional": true}
  ]
}
```

- [ ] **Step 9: double_dominant — LÖSCHEN**

```bash
rm app/photobook/preset_data/double_dominant.json
```

- [ ] **Step 10: double_text_right — unverändert behalten**

Prüfen: Slots `main`, `secondary`, `text` bleiben. Kein title-Slot.

- [ ] **Step 11: map_focus — unverändert behalten**

Prüfen: Slots `map`, `photo`, `caption` bleiben.

- [ ] **Step 12: triple_stacked — 3 übereinander (ersetzt triple_strip)**

```bash
mv app/photobook/preset_data/triple_strip.json app/photobook/preset_data/triple_stacked.json
```

```json
{
  "id": "triple_stacked",
  "name": "Drei übereinander",
  "description": "Drei Bilder vertikal gestapelt, je 33% Höhe. Keine Text-Slots.",
  "image_count": 3,
  "has_text": false,
  "css_class": "preset-triple-stacked",
  "slots": [
    {"id": "top", "type": "image", "priority": "primary", "css_area": "top", "optional": false},
    {"id": "middle", "type": "image", "priority": "secondary", "css_area": "middle", "optional": false},
    {"id": "bottom", "type": "image", "priority": "secondary", "css_area": "bottom", "optional": false}
  ]
}
```

Slot-IDs: `top`, `middle`, `bottom`.

- [ ] **Step 13: triple_stacked_text — 3 übereinander + Text rechts (ersetzt triple_text_right)**

```bash
mv app/photobook/preset_data/triple_text_right.json app/photobook/preset_data/triple_stacked_text.json
```

```json
{
  "id": "triple_stacked_text",
  "name": "Drei übereinander + Text rechts",
  "description": "Drei Bilder vertikal links (75%) mit Textblock rechts (25%).",
  "image_count": 3,
  "has_text": true,
  "css_class": "preset-triple-stacked-text",
  "slots": [
    {"id": "top", "type": "image", "priority": "primary", "css_area": "top", "optional": false},
    {"id": "middle", "type": "image", "priority": "secondary", "css_area": "middle", "optional": false},
    {"id": "bottom", "type": "image", "priority": "secondary", "css_area": "bottom", "optional": false},
    {"id": "text", "type": "text", "css_area": "text", "char_limit": 170, "font_size": "9pt", "text_role": "caption", "optional": true}
  ]
}
```

Slot-IDs: `top`, `middle`, `bottom`, `text`.

- [ ] **Step 14: triple_big_top — unverändert**

Prüfen: Slots `top`, `bl`, `br` bleiben.

- [ ] **Step 15: triple_big_text_below — unverändert**

Prüfen: Slots `top`, `bl`, `br`, `caption` bleiben.

- [ ] **Step 16: triple_text_below — LÖSCHEN**

```bash
rm app/photobook/preset_data/triple_text_below.json
```

- [ ] **Step 17: quad_grid — unverändert**

Prüfen: 2×2 Raster, Slots `tl`, `tr`, `bl`, `br`.

- [ ] **Step 18: quad_grid_text — NEU**

```json
{
  "id": "quad_grid_text",
  "name": "2×2 Raster + Text",
  "description": "Vier Bilder im 2×2-Raster (70%) mit Bildunterschrift darunter (30%).",
  "image_count": 4,
  "has_text": true,
  "css_class": "preset-quad-grid-text",
  "slots": [
    {"id": "tl", "type": "image", "priority": "primary", "css_area": "tl", "optional": false},
    {"id": "tr", "type": "image", "priority": "secondary", "css_area": "tr", "optional": false},
    {"id": "bl", "type": "image", "priority": "secondary", "css_area": "bl", "optional": false},
    {"id": "br", "type": "image", "priority": "secondary", "css_area": "br", "optional": false},
    {"id": "caption", "type": "text", "css_area": "caption", "char_limit": 170, "font_size": "9pt", "text_role": "caption", "optional": true}
  ]
}
```

- [ ] **Step 19: quad_strip_text_below — LÖSCHEN**

```bash
rm app/photobook/preset_data/quad_strip_text_below.json
```

- [ ] **Step 20: quad_large_plus_3 — Textbereich verkleinern**

Aktuelle Datei lesen, `char_limit` von caption prüfen. CSS wird in Task 3 angepasst (rows: `1fr 1fr 1fr 2fr` statt `1fr 1fr 1fr 3fr`). JSON unverändert lassen — nur CSS-Änderung in Task 3.

- [ ] **Step 21: collage_5 — unverändert**

Keine Änderung nötig. Prüfen dass kein title-Slot existiert.

- [ ] **Step 22: Verifiziere: genau 18 JSON-Dateien**

```bash
ls app/photobook/preset_data/*.json | wc -l
```

Erwartet: `18`

- [ ] **Step 23: Commit**

```bash
git add app/photobook/preset_data/
git commit -m "feat: restructure 18 photobook presets — stacked layouts, removed 3, added 2"
```

---

### Task 2: PRESET_CATALOG in presets.py aktualisieren

**Files:**
- Modify: `app/photobook/presets.py:4-32`

- [ ] **Step 1: Ersetze PRESET_CATALOG mit 18 Einträgen**

```python
PRESET_CATALOG = [
    # Cover
    ("cover_hero", 1, False),
    # 1-Bild
    ("single_full", 1, False),
    ("single_text_below", 1, True),
    ("single_text_left", 1, True),
    ("panorama", 1, True),
    ("image_text_split", 1, True),
    # 2-Bild
    ("double_stacked", 2, False),
    ("double_stacked_text", 2, True),
    ("double_text_right", 2, True),
    ("map_focus", 2, True),
    # 3-Bild
    ("triple_stacked", 3, False),
    ("triple_stacked_text", 3, True),
    ("triple_big_top", 3, False),
    ("triple_big_text_below", 3, True),
    # 4-Bild
    ("quad_grid", 4, False),
    ("quad_grid_text", 4, True),
    ("quad_large_plus_3", 4, True),
    # 5-Bild
    ("collage_5", 5, False),
]
```

Entfernte Einträge: `single_text_right`, `double_equal`, `double_dominant`, `double_text_below`, `triple_strip`, `triple_text_below`, `triple_text_right`, `quad_grid_text_below`, `quad_strip_text_below`.
Neue Einträge: `single_text_left`, `double_stacked`, `double_stacked_text`, `triple_stacked`, `triple_stacked_text`, `quad_grid_text`.
`cover_hero`: `has_text` von `True` auf `False`.

- [ ] **Step 2: Commit**

```bash
git add app/photobook/presets.py
git commit -m "feat: update PRESET_CATALOG to 18 presets matching new structure"
```

---

### Task 3: CSS (styles.css) komplett überarbeiten

**Files:**
- Modify: `app/photobook/styles.css`

- [ ] **Step 1: .page-single auf Flex-Column umstellen**

Ersetze:
```css
.page-single {
  width: 210mm;
  height: 297mm;
  padding: 10mm;
}
```

Durch:
```css
.page-single {
  width: 210mm;
  height: 297mm;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.page-header {
  flex: 0 0 auto;
  padding: 3mm 10mm;
  background: #1e293b;
}

.page-title {
  font-size: 12pt;
  font-weight: bold;
  color: #f1f5f9;
  font-family: Georgia, 'Times New Roman', serif;
  line-height: 1.3;
}

.page-content {
  flex: 1;
  padding: 10mm;
  min-height: 0;
}
```

- [ ] **Step 2: Cover-Hero — Vollbild ohne Text**

Ersetze `.preset-cover-hero`:
```css
.preset-cover-hero {
  display: grid;
  grid-template-columns: 1fr;
  grid-template-rows: 1fr;
  gap: 0;
  padding: 0;
}
```

Entferne `grid-template-areas`. Das Image bekommt `grid-area: auto` (Standard).

- [ ] **Step 3: Single-Full**

Ersetze `.preset-single-full` (padding:0, kein gap):
```css
.preset-single-full {
  display: grid;
  grid-template-columns: 1fr;
  grid-template-rows: 1fr;
  gap: 0;
  padding: 0;
}
```

- [ ] **Step 4: Single-Text-Below — 70/30**

Unverändert:
```css
.preset-single-text-below {
  display: grid;
  grid-template-columns: 1fr;
  grid-template-rows: 7fr 3fr;
  grid-template-areas: "main" "caption";
  gap: 4mm;
}
```

- [ ] **Step 5: Single-Text-Left — NEU (30/70)**

```css
.preset-single-text-left {
  display: grid;
  grid-template-columns: 3fr 7fr;
  grid-template-rows: 1fr;
  grid-template-areas: "text main";
  gap: 4mm;
}
```

- [ ] **Step 6: Panorama — Text oben (25/75)**

Ersetze `.preset-panorama`:
```css
.preset-panorama {
  display: grid;
  grid-template-columns: 1fr;
  grid-template-rows: 2.5fr 7.5fr;
  grid-template-areas: "caption" "main";
  gap: 4mm;
  align-items: center;
}
```

- [ ] **Step 7: Image-Text-Split — 70/30**

Ersetze `.preset-image-text-split`:
```css
.preset-image-text-split {
  display: grid;
  grid-template-columns: 7fr 3fr;
  grid-template-rows: 1fr;
  grid-template-areas: "image text";
  gap: 4mm;
}
```

- [ ] **Step 8: Double-Stacked — NEU (2 vertikal)**

Ersetze `.preset-double-equal` → `.preset-double-stacked`:
```css
.preset-double-stacked {
  display: grid;
  grid-template-columns: 1fr;
  grid-template-rows: 1fr 1fr;
  grid-template-areas: "top" "bottom";
  gap: 4mm;
}
```

Entferne `.preset-double-equal`.

- [ ] **Step 9: Double-Stacked-Text — NEU**

```css
.preset-double-stacked-text {
  display: grid;
  grid-template-columns: 1fr;
  grid-template-rows: 3.5fr 3.5fr 3fr;
  grid-template-areas: "top" "bottom" "caption";
  gap: 4mm;
}
```

- [ ] **Step 10: Double-Dominant — ENTFERNEN**

Lösche `.preset-double-dominant { ... }` Block.

- [ ] **Step 11: Double-Text-Below — ENTFERNEN**

Lösche `.preset-double-text-below { ... }` Block.

- [ ] **Step 12: Double-Text-Right — unverändert**

Behält:
```css
.preset-double-text-right {
  display: grid;
  grid-template-columns: 7fr 3fr;
  grid-template-rows: 1fr 1fr;
  grid-template-areas:
    "main text"
    "secondary text";
  gap: 4mm;
}
```

Hinweis: CSS-Areas müssen zu den JSON-Slot-IDs passen. Prüfen dass die JSON-Slots `main`, `secondary`, `text` heißen.

- [ ] **Step 13: Map-Focus — unverändert**

```css
.preset-map-focus {
  display: grid;
  grid-template-columns: 1fr 1fr;
  grid-template-rows: 7fr 3fr;
  grid-template-areas:
    "map photo"
    "caption caption";
  gap: 4mm;
}
```

- [ ] **Step 14: Triple-Strip → Triple-Stacked**

Lösche `.preset-triple-strip`. Erstelle `.preset-triple-stacked`:
```css
.preset-triple-stacked {
  display: grid;
  grid-template-columns: 1fr;
  grid-template-rows: 1fr 1fr 1fr;
  grid-template-areas: "top" "middle" "bottom";
  gap: 3mm;
}
```

- [ ] **Step 15: Triple-Text-Right → Triple-Stacked-Text**

Lösche `.preset-triple-text-right`. Erstelle `.preset-triple-stacked-text`:
```css
.preset-triple-stacked-text {
  display: grid;
  grid-template-columns: 7.5fr 2.5fr;
  grid-template-rows: 1fr 1fr 1fr;
  grid-template-areas:
    "top text"
    "middle text"
    "bottom text";
  gap: 3mm;
}
```

- [ ] **Step 16: Triple-Big-Top — unverändert**

```css
.preset-triple-big-top {
  display: grid;
  grid-template-columns: 1fr 1fr;
  grid-template-rows: 7fr 3fr;
  grid-template-areas:
    "top top"
    "bl br";
  gap: 3mm;
}
```

- [ ] **Step 17: Triple-Big-Text-Below — unverändert**

```css
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
```

- [ ] **Step 18: Triple-Text-Below — ENTFERNEN**

Lösche `.preset-triple-text-below { ... }` Block.

- [ ] **Step 19: Quad-Grid — unverändert**

```css
.preset-quad-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  grid-template-rows: 1fr 1fr;
  grid-template-areas:
    "tl tr"
    "bl br";
  gap: 3mm;
}
```

- [ ] **Step 20: Quad-Grid-Text — NEU**

Ersetze `.preset-quad-grid-text-below` → `.preset-quad-grid-text`:
```css
.preset-quad-grid-text {
  display: grid;
  grid-template-columns: 1fr 1fr;
  grid-template-rows: 3.5fr 3.5fr 3fr;
  grid-template-areas:
    "tl tr"
    "bl br"
    "caption caption";
  gap: 3mm;
}
```

Lösche alten `.preset-quad-grid-text-below` Block.

- [ ] **Step 21: Quad-Strip-Text-Below — ENTFERNEN**

Lösche `.preset-quad-strip-text-below { ... }` Block.

- [ ] **Step 22: Quad-Large-Plus-3 — Text kleiner (2fr statt 3fr)**

Ersetze:
```css
.preset-quad-large-plus-3 {
  display: grid;
  grid-template-columns: 7fr 3fr;
  grid-template-rows: 1fr 1fr 1fr 2fr;
  grid-template-areas:
    "main small1"
    "main small2"
    "main small3"
    "caption caption";
  gap: 3mm;
}
```

- [ ] **Step 23: Collage-5 — unverändert**

```css
.preset-collage-5 {
  display: grid;
  grid-template-columns: 2fr 1fr;
  grid-template-rows: 1fr 1fr 1fr 1fr;
  grid-template-areas:
    "big s1"
    "big s2"
    "big s3"
    "wide wide";
  gap: 3mm;
}
```

- [ ] **Step 24: Slot-Image — padding:0 für Vollbild-Presets**

Füge Utility-Klasse hinzu:
```css
.preset-cover-hero .slot-image,
.preset-single-full .slot-image {
  object-fit: cover;
  width: 100%;
  height: 100%;
  display: block;
}
```

- [ ] **Step 25: Commit**

```bash
git add app/photobook/styles.css
git commit -m "feat: rewrite CSS for 18 presets with universal page-header"
```

---

### Task 4: Renderer umbauen (page-header + page-content)

**Files:**
- Modify: `app/photobook/renderer.py`

- [ ] **Step 1: render_photobook() neu schreiben**

Ersetze die gesamte `render_photobook` Funktion:

```python
def render_photobook(pages: List[PageDescription], images: List[ImageData]) -> str:
    """Erzeugt ein vollstaendiges HTML-Dokument aus Seitenbeschreibungen.

    Jede Seite hat einen page-header (Titel) und page-content (Preset-Layout).
    """
    html_parts = [PHOTOBOOK_HEADER]

    for page_idx, page in enumerate(pages):
        preset = load_preset(page.template_id)
        css_class = preset.css_class

        # Seitentitel aus den Slots extrahieren
        page_title = _extract_title(page, page_idx)

        html_parts.append(f'<div class="photobook-page page-single">')
        html_parts.append(f'<div class="page-header">')
        html_parts.append(f'<div class="page-title">{html.escape(page_title)}</div>')
        html_parts.append(f'</div>')  # page-header

        html_parts.append(f'<div class="page-content {css_class}">')

        slot_defs = {s.id: s for s in preset.slots}

        for slot_data in page.slots:
            slot_id = slot_data.get("slot_id", "")
            slot_def = slot_defs.get(slot_id)
            if not slot_def:
                continue

            # Titel wird schon im page-header gerendert, nicht nochmal im content
            if slot_def.text_role == "title":
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
                font_size = slot_def.font_size or "11pt"
                style = f'style="grid-area: {slot_def.css_area}; font-size: {font_size}"'

                if slot_def.text_role == "title":
                    css_cls = "slot-title"
                elif slot_def.text_role == "caption":
                    css_cls = "slot-caption"
                else:
                    css_cls = "slot-text"

                html_parts.append(
                    f'<div class="{css_cls}" {style}>{text}</div>'
                )

        html_parts.append("</div>")  # page-content
        html_parts.append("</div>")  # photobook-page

    html_parts.append(PHOTOBOOK_FOOTER)
    return "\n".join(html_parts)
```

- [ ] **Step 2: _extract_title() Hilfsfunktion hinzufügen**

```python
def _extract_title(page: PageDescription, page_idx: int) -> str:
    """Extrahiert den Seitentitel aus den Slots oder generiert Fallback."""
    for slot in page.slots:
        if slot.get("slot_id") == "title" and slot.get("text", "").strip():
            return slot["text"]
    # Fallback: "Seite N" oder Preset-Name
    return f"Seite {page_idx + 1}"
```

- [ ] **Step 3: Commit**

```bash
git add app/photobook/renderer.py
git commit -m "feat: renderer adds universal page-header with title for every page"
```

---

### Task 5: Validator für title-Slots anpassen

**Files:**
- Modify: `app/photobook/validator.py`

- [ ] **Step 1: _text_placeholder für title anpassen**

Die Funktion `_text_placeholder` existiert bereits. Prüfen ob `title` → `"Fotobuch"` korrekt ist.

- [ ] **Step 2: enforce_fallback — title-Slot immer hinzufügen**

Nach dem bestehenden Block, der Text-Slots befüllt (Zeile ~112-118), zusätzlich prüfen ob ein `title`-Slot existiert:

Füge nach `# Stelle sicher, dass ALLE Text-Slots befüllt sind` folgenden Code ein, der einen title-Slot erstellt auch wenn das Preset keinen definiert:

```python
    # Universeller Title-Slot für page-header (auch wenn Preset keins hat)
    has_title = any(s.get("slot_id") == "title" for s in repaired_slots)
    if not has_title:
        repair_slots.append({"slot_id": "title", "text": "Fotobuch"})
```

Warte — stattdessen sollte der Renderer den Fallback-Titel setzen (das tut er bereits über `_extract_title`). Der Validator muss nur sicherstellen dass vorhandene title-Slots (wie in cover_hero früher) gefüllt sind. Da cover_hero jetzt KEINEN title-Slot mehr hat, ist das nicht nötig.

ABER: Der Validator sollte dennoch einen title-Slot in jede PageDescription einfügen, damit der Renderer ihn nutzen kann. Sonst sieht der Renderer nur "Seite 1", "Seite 2" etc.

**Entscheidung:** Wir fügen im `enforce_fallback` einen title-Slot hinzu, wenn keiner existiert. Das LLM kann in Pass 2 einen title-Text generieren (den es als `{"slot_id": "title", "text": "..."}` ausgibt). Falls nicht, setzt `enforce_fallback` den Platzhalter.

Füge am Ende von `enforce_fallback` (vor dem `return`) ein:

```python
    # Universeller Title-Slot für den page-header
    has_title = any(s.get("slot_id") == "title" and s.get("text", "").strip() for s in repaired_slots)
    if not has_title:
        repaired_slots.append({"slot_id": "title", "text": "Fotobuch"})
```

- [ ] **Step 3: _replace_preset — title weitergeben**

In `_replace_preset` wird bereits Text aus alten Slots kopiert. Füge am Ende (vor `return`) den gleichen title-Fallback ein:

```python
    # Universeller Title-Slot für den page-header
    has_title = any(s.get("slot_id") == "title" and s.get("text", "").strip() for s in new_slots)
    if not has_title:
        new_slots.append({"slot_id": "title", "text": "Fotobuch"})
```

- [ ] **Step 4: Commit**

```bash
git add app/photobook/validator.py
git commit -m "feat: validator ensures every page has a title slot for page-header"
```

---

### Task 6: LLM-Prompts anpassen (generate.py)

**Files:**
- Modify: `app/photobook/generate.py`

- [ ] **Step 1: Prompt um title-Slot-Instruktion erweitern**

In `_build_generate_prompt`, im `AUFGABE PRO SEITE`-Abschnitt, füge hinzu:

```python
    return f"""Du befuellst die Slots der gewaehlten Presets mit Bildern und Text.

SEITENPLAN (preset_id pro Seite):
{plan_text}

VERWENDETE PRESETS (nur diese sind relevant):
{catalog}
{gpx_text}{notes_text}

{constraints}

{"TEXT IST PFLICHT: Hat ein Preset Text-Slots, MUSST du diese befuellen. Lass KEINEN Text-Slot leer. Betrachte die Bilder und beschreibe, was du siehst." if text_required else ""}

AUFGABE PRO SEITE:
1. Weise jedem Image-Slot ein Bild zu (image_index aus dem Plan).
2. Text-Rollen: title (stimmungsvoller Titel, 60 Z.), caption (Bildbeschreibung, 170 Z.), intro (Einleitung, 400 Z.).
3. Generiere kurze, passende Texte — innerhalb der Zeichenlimits.
4. JEDE Seite MUSS einen title-Slot haben: {{"slot_id": "title", "text": "Einzeiliger Seitentitel"}}

BEISPIELE:
- cover_hero: [{{"preset_id": "cover_hero", "slots": [{{"slot_id": "title", "text": "Aufbruch im Morgengrauen"}}, {{"slot_id": "main", "image_index": 0}}]}}]
- single_text_below: [{{"preset_id": "single_text_below", "slots": [{{"slot_id": "title", "text": "Alpenwiese"}}, {{"slot_id": "main", "image_index": 1}}, {{"slot_id": "caption", "text": "Weitblick ueber das Tal"}}]}}]
- double_stacked (KEIN Text): [{{"preset_id": "double_stacked", "slots": [{{"slot_id": "title", "text": "Aufstieg"}}, {{"slot_id": "top", "image_index": 3}}, {{"slot_id": "bottom", "image_index": 4}}]}}]

ANTWORTE NUR mit JSON-Array:"""
```

- [ ] **Step 2: Fallback-Pfad title-Slots hinzufügen**

In `generate_photobook_pages`, im Fallback-Block (Zeile ~142-163), nach dem Erstellen der image-Slots, füge einen title-Slot hinzu:

```python
        slots = []
        for sid, idx in zip(image_slots, indices):
            slots.append({"slot_id": sid, "image_index": idx})
        # Universeller Title-Slot für den Fallback
        slots.append({"slot_id": "title", "text": "Fotobuch"})
        fallback.append(PageDescription(
            template_id=preset_id,
            page_type="single",
            slots=slots,
        ))
```

- [ ] **Step 3: Commit**

```bash
git add app/photobook/generate.py
git commit -m "feat: LLM prompt requires title slot on every page"
```

---

### Task 7: Fallback-Planung aktualisieren (plan.py)

**Files:**
- Modify: `app/photobook/plan.py`

- [ ] **Step 1: _generate_fallback_plan verwendet neue Preset-IDs**

Die Fallback-Planung nutzt `get_any_preset(count)`. Diese Funktion zieht aus `PRESET_CATALOG`. Da der Katalog bereits in Task 2 aktualisiert wurde, sollte das automatisch passen. Verifiziere:

```python
# get_any_preset(1) → "cover_hero" oder "single_full" (je nach Reihenfolge)
# get_any_preset(2) → "double_stacked"
# get_any_preset(3) → "triple_stacked"
# get_any_preset(4) → "quad_grid"
```

Das passt — die Fallback-Planung wird automatisch die richtigen Presets verwenden.

Keine Code-Änderung nötig.

---

### Task 8: Tests aktualisieren

**Files:**
- Modify: `tests/test_photobook/test_presets.py`
- Modify: `tests/test_photobook/test_renderer.py`
- Modify: `tests/test_photobook/test_validator.py`
- Modify: `tests/test_photobook/test_variety.py`

- [ ] **Step 1: test_presets.py — Catalog-Count auf 18 ändern**

```python
# test_catalog_has_21_entries → test_catalog_has_18_entries
def test_catalog_has_18_entries(self):
    from app.photobook.presets import PRESET_CATALOG
    assert len(PRESET_CATALOG) == 18
```

- [ ] **Step 2: test_presets.py — cover_hero has_text prüfen**

```python
def test_cover_hero_no_text(self):
    """cover_hero hat keinen Text-Slot mehr (Titel kommt aus page-header)."""
    from app.photobook.preset_loader import load_preset
    preset = load_preset("cover_hero")
    assert preset.has_text is False
```

- [ ] **Step 3: test_renderer.py — page-header prüfen**

Füge Test hinzu:

```python
def test_render_includes_page_header(self):
    """Jede Seite hat einen page-header mit Titel."""
    pages = [
        PageDescription(template_id="cover_hero", page_type="single",
                      slots=[{"slot_id": "main", "image_index": 0}]),
    ]
    html = render_photobook(pages, TEST_IMAGES)
    assert "page-header" in html
    assert "page-title" in html
    assert "page-content" in html

def test_render_title_in_header_not_in_content(self):
    """Title-Slot wird im page-header gerendert, nicht im page-content."""
    pages = [
        PageDescription(template_id="cover_hero", page_type="single",
                      slots=[
                          {"slot_id": "main", "image_index": 0},
                          {"slot_id": "title", "text": "Mein Titel"},
                      ]),
    ]
    html = render_photobook(pages, TEST_IMAGES)
    # Titel muss im page-header sein
    assert '<div class="page-title">Mein Titel</div>' in html

def test_render_fallback_title(self):
    """Ohne title-Slot wird 'Seite N' als Fallback verwendet."""
    pages = [
        PageDescription(template_id="single_full", page_type="single",
                      slots=[{"slot_id": "main", "image_index": 0}]),
    ]
    html = render_photobook(pages, TEST_IMAGES)
    assert '<div class="page-title">Seite 1</div>' in html

def test_render_double_stacked(self):
    """double_stacked: 2 Bilder vertikal, keine Text-Slots."""
    pages = [
        PageDescription(template_id="double_stacked", page_type="single",
                      slots=[
                          {"slot_id": "top", "image_index": 0},
                          {"slot_id": "bottom", "image_index": 1},
                      ]),
    ]
    html = render_photobook(pages, TEST_IMAGES)
    assert "preset-double-stacked" in html
    assert "slot-image" in html

def test_render_double_stacked_text(self):
    """double_stacked_text: 2 Bilder + caption."""
    pages = [
        PageDescription(template_id="double_stacked_text", page_type="single",
                      slots=[
                          {"slot_id": "top", "image_index": 0},
                          {"slot_id": "bottom", "image_index": 1},
                          {"slot_id": "caption", "text": "Waldpfad"},
                      ]),
    ]
    html = render_photobook(pages, TEST_IMAGES)
    assert "preset-double-stacked-text" in html
    assert "Waldpfad" in html

def test_render_quad_grid_text(self):
    """quad_grid_text: 2x2 Raster + caption."""
    pages = [
        PageDescription(template_id="quad_grid_text", page_type="single",
                      slots=[
                          {"slot_id": "tl", "image_index": 0},
                          {"slot_id": "tr", "image_index": 1},
                          {"slot_id": "bl", "image_index": 2},
                          {"slot_id": "br", "image_index": 3},
                          {"slot_id": "caption", "text": "Rundumblick"},
                      ]),
    ]
    html = render_photobook(pages, TEST_IMAGES)
    assert "preset-quad-grid-text" in html
    assert "Rundumblick" in html
```

Aktualisiere auch bestehende Tests, die `double_equal` oder `single_text_right` referenzieren:
- `test_render_spread_has_correct_dimensions`: `double_equal` → `double_stacked`, `left`/`right` → `top`/`bottom`
- `test_cover_hero_uses_preset_css_class`: title-Slot entfernen oder title-Text hinzufügen
- `test_render_title_slot`: Dieser testet dass `slot-title` CSS-Klasse verwendet wird. Da title jetzt im page-header ist und nicht mehr als slot-title, muss dieser Test angepasst oder entfernt werden. Der page-header rendert `.page-title`, nicht `.slot-title`.

- [ ] **Step 4: test_validator.py — title-presence Tests**

```python
def test_enforce_fallback_adds_title_slot(self):
    """enforce_fallback fügt title-Slot hinzu, wenn keiner existiert."""
    from app.photobook.validator import enforce_fallback
    from app.state import PageDescription

    page = PageDescription(template_id="single_full", page_type="single",
                         slots=[{"slot_id": "main", "image_index": 0}])
    result = enforce_fallback(page)
    title_slot = next((s for s in result.slots if s.get("slot_id") == "title"), None)
    assert title_slot is not None
    assert title_slot.get("text", "").strip() != ""

def test_replace_preset_adds_title_slot(self):
    """_replace_preset fügt title-Slot im neuen Preset hinzu."""
    from app.photobook.validator import _replace_preset
    from app.state import PageDescription

    page = PageDescription(template_id="single_full", page_type="single",
                         slots=[{"slot_id": "main", "image_index": 0}])
    result = _replace_preset(page, "double_stacked")
    title_slot = next((s for s in result.slots if s.get("slot_id") == "title"), None)
    assert title_slot is not None
```

- [ ] **Step 5: test_variety.py — alte Preset-Referenzen aktualisieren**

Ersetze:
- `double_equal` → `double_stacked`
- `triple_strip` → `triple_stacked`

- [ ] **Step 6: Commit**

```bash
git add tests/
git commit -m "test: update tests for 18-preset layout with page-header"
```

---

### Task 9: Vollständigen Test-Suite-Lauf

- [ ] **Step 1: Alle Photobook-Tests ausführen**

```bash
uv run pytest tests/test_photobook/ -v
```

Erwartet: Alle Tests grün.

- [ ] **Step 2: Komplette Test-Suite ausführen**

```bash
uv run pytest tests/ -v
```

Erwartet: Alle Tests grün, bis auf pre-existing `test_exif_timestamp_format`.

- [ ] **Step 3: Commit (falls nötig)**

```bash
git add -A
git commit -m "fix: final adjustments after full test suite run"
```
