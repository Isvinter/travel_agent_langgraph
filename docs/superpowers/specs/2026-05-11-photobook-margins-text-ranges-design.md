# Photobuch-Layout-Überarbeitung: Rand + Layout-spezifische Text-Ranges

Datum: 2026-05-11

## Ziel

Photobücher mit konsistentem Rand (6mm) auf allen Non-Cover-Seiten und
layout-spezifischen Textmengen-Vorgaben für das LLM, sodass Textboxen
besser gefüllt werden.

## Änderungen

### Teil 1: Rand-Korrektur

**Problem:** `.preset-single-full` in `styles.css` setzt `padding: 0`,
was das 6mm-Padding von `.page-content` überschreibt. Diese Seite
rendert randlos (Full-Bleed), während alle anderen Non-Cover-Layouts
den 6mm-Rand haben.

**Fix:** `padding: 0` aus `.preset-single-full` entfernen. Cover
(cover_hero) bleibt randlos.

### Teil 2: Layout-spezifische Char-Ranges

**Problem:** Alle Text-Layouts nutzen global `char_limit: 500` für
captions. Kleine Textboxen werden überfüllt, große bleiben leer.

**Ansatz:** Hybrid — `char_min`/`char_max` in JSON-Preset-Dateien mit
Berechnungs-Fallback für neue Layouts ohne explizite Werte.

**Ranges pro Layout:**

| Preset | Slot | char_min | char_max (char_limit) |
|---|---|---|---|
| quad_large_plus_3 | caption | 400 | 700 |
| double_stacked_text | caption | 450 | 800 |
| triple_big_text_below | caption | 450 | 800 |
| panorama | caption | 700 | 1100 |
| image_text_split | intro | 800 | 1200 |
| single_text_below | caption | 900 | 1400 |
| single_text_left | caption | 900 | 1400 |
| map_focus | caption | 900 | 1400 |
| quad_grid_text | caption | 900 | 1400 |
| double_text_right | caption | 900 | 1400 |
| triple_stacked_text | caption | 1200 | 1800 |

### Teil 3: Prompt-Anpassung

Pro Preset werden `char_min` und `char_max` in der Preset-Übersicht
angezeigt. Die LLM-Aufgabe fordert: "Ziele auf MINDESTENS char_min,
überschreite NIEMALS char_max."

### Teil 4: Font-Größe

Zurückgestellt. Wird nach Sichtung der Ergebnisse entschieden.

## Betroffene Dateien

- `app/photobook/styles.css` — `.preset-single-full` padding entfernen
- `app/photobook/preset_data/*.json` — 10 Text-Layouts: `char_min` + `char_limit` updaten
- `app/photobook/preset_loader.py` — `PresetSlot`: `char_min` Feld hinzufügen
- `app/photobook/presets.py` — `get_constraint_summary()`: per-Preset char ranges
- `app/photobook/generate.py` — Prompt: char_min/char_max pro Preset anzeigen
- `app/photobook/validator.py` — keine Änderung (nutzt bereits `slot_def.char_limit`)

## Keine Änderungen

- Cover (cover_hero) bleibt randlos
- `@page { margin: 0 }` in `generate_pdf.py` bleibt unverändert
- `.page-content { padding: 6mm }` bleibt unverändert
- Font-Größen bleiben unverändert
