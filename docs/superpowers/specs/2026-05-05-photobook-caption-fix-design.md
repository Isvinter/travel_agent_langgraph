# Design: Caption-Rendering-Fix für Photopuch

**Datum:** 2026-05-05
**Status:** approved
**Kontext:** Bugfixing — Subtask B aus Photopuch-Root-Cause-Analyse

## Problem

In `app/photobook/renderer.py:81-86` werden Captions, die an Image-Slots hängen, im gleichen CSS-Grid-Area wie das Bild gerendert. Beispiel: Hero-Template hat `grid-area: main` (Bild) und `grid-area: caption` (Unterschrift). Der Renderer platziert das `<img>` und das Caption-`<div>` beide in `grid-area: main` → Caption überlappt mit dem Bild und ist unsichtbar.

## Ziel

Captions in den dedizierten Caption-Slot des Templates rendern, sodass sie sichtbar im richtigen Grid-Bereich erscheinen.

## Entscheidung

**Approach A: Caption-Slot aus Template auflösen.** Der Renderer sucht beim Rendern eines Image-Slots mit Caption den dedizierten Caption-Slot des Templates und verwendet dessen `css_area`. Minimal-invasiv, kein LLM-Interface-Change.

## Änderung

### Datei: `app/photobook/renderer.py` (Zeilen 81–86)

**Vorher:**
```python
# Caption kann auch am Image-Slot haengen
caption = html.escape(slot_data.get("caption", ""))
if caption:
    html_parts.append(
        f'<div class="slot-caption" {area_style}>{caption}</div>'
    )
```

**Nachher:**
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

### Template-Verhalten

| Template | Caption-Slot? | `supports_captions` | Caption wird gerendert? |
|----------|:---:|:---:|:---:|
| hero_single | ✅ | true | Ja, in `grid-area: caption` |
| panorama | ✅ | true | Ja, in `grid-area: caption` |
| split_equal | ✅ | true | Ja, in `grid-area: caption` |
| split_dominant | ✅ | true | Ja, in `grid-area: caption` |
| image_text_left | ✅ | true | Ja, in `grid-area: caption` |
| grid_2x2 | ❌ | false | Nein |
| strip_3 | ❌ | false | Nein |
| collection_3 | ❌ | false | Nein |

## Tests

### Bestehender Test (muss weiterhin grün sein)
- `test_renderer.py::test_render_single_page_hero` — prüft `"Cover" in html`

### Neuer Test
- `test_renderer.py::test_caption_uses_correct_grid_area` — prüft explizit dass `grid-area: caption` (nicht `grid-area: main`) im HTML für die Caption verwendet wird

## Abhängigkeiten

Keine. Nur `renderer.py` wird geändert.

## Risiken

- **Gering:** Templates ohne Caption-Slot (grid_2x2, strip_3, collection_3) rendern keine Captions mehr — das ist korrekt, da sie keinen Platz im Grid haben.
