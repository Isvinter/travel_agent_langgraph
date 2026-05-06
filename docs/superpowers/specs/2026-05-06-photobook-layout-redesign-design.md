# Photobook Layout Redesign — Universal Page Titles & Restructured Presets

**Date:** 2026-05-06  
**Status:** approved  
**Scope:** `app/photobook/`, `tests/test_photobook/`

## Problem

1. Keine einheitlichen Seitentitel — nur cover_hero hatte einen Titel (als Bild-Overlay), alle anderen Seiten titellos
2. Textfelder fehlten oft komplett (Validator-Bug, bereits gefixt)
3. 2-Bild-Layouts nebeneinander erzeugen zu schmale Aspect-Ratios → Bilder werden stark beschnitten
4. Layout-Vielfalt zu gering für 3-Bild-Seiten
5. Textfelder teilweise zu klein oder falsch positioniert

## Design

### Architekturprinzip: Universeller Seitentitel

Jede Fotobuch-Seite erhält einen einzeiligen Titel oben in einer dunklen Leiste (ca. 5% der Seitenhöhe). Darunter füllt das Preset-Layout die restlichen 95%.

**Renderer-Änderung:** `render_photobook()` umschließt jede Seite mit `<div class="page-header">` + `<div class="page-content">`. Die `page-content`-Div erhält die Preset-CSS-Klasse. Der Title-Slot wird aus `page.slots` extrahiert (slot_id `"title"`, text_role `"title"`).

**CSS-Änderung:** `.page-single` wird Flex-Column. `.page-header` ist der Titel-Container. `.page-content` bekommt `flex:1`.

### Preset-Katalog (18 Presets, von 21)

Jedes Preset definiert ein `<div class="page-content preset-XXX">` Grid. Text-Presets folgen dem Prinzip **70% Bild / 30% Text**.

#### Cover (1)
| ID | Bilder | Text | Layout |
|----|--------|------|--------|
| `cover_hero` | 1 | — | Vollbild (Titel nur in page-header) |

#### 1-Bild (5)
| ID | Bilder | Text | Layout |
|----|--------|------|--------|
| `single_full` | 1 | — | 1 Bild, 100% |
| `single_text_below` | 1 | caption unten | 70/30 vertikal |
| `single_text_left` | 1 | caption links | 30/70 horizontal (NEU, ersetzt single_text_right) |
| `panorama` | 1 | caption oben (2× Größe) | Text oben, Bild unten (GEÄNDERT: Textposition und -größe) |
| `image_text_split` | 1 | intro rechts | 70/30 horizontal (GEÄNDERT: war 50/50) |

#### 2-Bild (4)
| ID | Bilder | Text | Layout |
|----|--------|------|--------|
| `double_stacked` | 2 | — | 2 übereinander, 50/50 (GEÄNDERT: war double_equal nebeneinander) |
| `double_stacked_text` | 2 | caption unten | 2 übereinander 70% + Text 30% (NEU) |
| `double_text_right` | 2 | text rechts | 70/30 horizontal, 2 Bilder vertikal links |
| `map_focus` | 2 | caption unten | Karte+Bild nebeneinander + Text |

**Entfernt:** `double_dominant` (1 groß + 1 klein, ersatzlos)

#### 3-Bild (4)
| ID | Bilder | Text | Layout |
|----|--------|------|--------|
| `triple_stacked` | 3 | — | 3 übereinander, 33/33/33 (GEÄNDERT: war triple_strip nebeneinander) |
| `triple_stacked_text` | 3 | text rechts (25%) | 3 vertikal links 75% + Text rechts 25% (GEÄNDERT: Text schmaler) |
| `triple_big_top` | 3 | — | 1 groß oben + 2 klein unten |
| `triple_big_text` | 3 | caption unten | 1 groß + 2 klein + Text unten |

**Entfernt:** `triple_text_below` (3 quer + Text, ersatzlos)

#### 4-Bild (3)
| ID | Bilder | Text | Layout |
|----|--------|------|--------|
| `quad_grid` | 4 | — | 2×2 Raster |
| `quad_grid_text` | 4 | caption unten | 2×2 Raster + Text (NEU) |
| `quad_large_plus_3` | 4 | caption unten | 1 groß + 3 klein + Text (GEÄNDERT: Textbereich −30%) |

**Entfernt:** `quad_strip_text` (4er-Streifen, ersatzlos)

#### 5-Bild (1)
| ID | Bilder | Text | Layout |
|----|--------|------|--------|
| `collage_5` | 5 | — | Collage (unverändert) |

### CSS Grid-Definitionen (in `styles.css`)

Jedes Preset ist ein CSS Grid auf `.page-content`. Die Dimensionen beziehen sich auf die verfügbare Fläche NACH Abzug des page-headers.

| Preset | grid-template |
|--------|--------------|
| `cover_hero` | `1fr` |
| `single_full` | `1fr` |
| `single_text_below` | `rows: 7fr 3fr` |
| `single_text_left` | `columns: 3fr 7fr` |
| `panorama` | `rows: 2.5fr 7.5fr` (Text oben) |
| `image_text_split` | `columns: 7fr 3fr` |
| `double_stacked` | `rows: 1fr 1fr` |
| `double_stacked_text` | `rows: 3.5fr 3.5fr 3fr` |
| `double_text_right` | `columns: 7fr 3fr`, `rows: 1fr 1fr` |
| `map_focus` | `columns: 1fr 1fr`, `rows: 7fr 3fr` |
| `triple_stacked` | `rows: 1fr 1fr 1fr` |
| `triple_stacked_text` | `columns: 7.5fr 2.5fr`, `rows: 1fr 1fr 1fr` |
| `triple_big_top` | `columns: 1fr 1fr`, `rows: 7fr 3fr` |
| `triple_big_text` | `columns: 1fr 1fr`, `rows: 5fr 2fr 3fr` |
| `quad_grid` | `columns: 1fr 1fr`, `rows: 1fr 1fr` |
| `quad_grid_text` | `columns: 1fr 1fr`, `rows: 3.5fr 3.5fr 3fr` |
| `quad_large_plus_3` | `columns: 7fr 3fr`, `rows: 1fr 1fr 1fr 2fr` |
| `collage_5` | `columns: 2fr 1fr`, `rows: 1fr 1fr 1fr 1fr` |

Alle Presets: `gap: 3mm` (bis 4mm für 1-Bild-Layouts). Slot-Images: `object-fit: cover`.

### Datenfluss

```
Preset JSON (18 Dateien) → preset_loader (Preset+Pydantic)
                                   ↓
LLM Pass 1 (plan.py) → wählt preset_id pro Seite
LLM Pass 2 (generate.py) → füllt Slots (image_index + text)
                                   ↓
validator.py → enforce_fallback (immer!) → check_variety → _replace_preset
                                   ↓
renderer.py → page-header (Titel) + page-content (Preset-Grid)
                                   ↓
styles.css → Grid-Layouts
                                   ↓
HTML → PDF via Headless Chrome
```

### Geänderte Dateien

| Datei | Änderung |
|-------|----------|
| `app/photobook/preset_data/*.json` | 18 Preset-JSONs erstellen/aktualisieren, 3 entfernen |
| `app/photobook/styles.css` | `.page-single` → Flex-Column, `.page-header`/`.page-content`/`.page-title` neu, alle Preset-CSS anpassen |
| `app/photobook/renderer.py` | `render_photobook()`: page-header + page-content Wrapper, Title-Slot-Extraktion |
| `app/photobook/presets.py` | `PRESET_CATALOG` auf 18 Einträge aktualisieren |
| `app/photobook/validator.py` | `_replace_preset()` und `enforce_fallback()`: title-Slot immer befüllen |
| `tests/test_photobook/test_renderer.py` | Tests für page-header, neue Presets |
| `tests/test_photobook/test_validator.py` | Tests für title-presence, neue Presets |
| `tests/test_photobook/test_presets.py` | Catalog-Count von 21 auf 18 aktualisieren |

### Constraints

- 18 Presets (war 21)
- Jeder Text-Slot hat `char_limit` aus `TEXT_CONSTRAINTS` (title: 60, caption: 170, intro: 400)
- `PRESET_CATALOG` in `presets.py` muss mit den JSON-Dateien übereinstimmen
- Alle Tests müssen weiterhin grün sein (329 Tests, bis auf pre-existing `test_exif_timestamp_format`)
- `generate.py` Fallback-Pfad muss title-Slots setzen
- `plan.py` Fallback-Pfad (`_generate_fallback_plan`) muss existierende Preset-IDs verwenden
