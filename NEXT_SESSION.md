# Photopuch — Nächste Session

## Ziel
Preset-basiertes Layout-System statt freier LLM-Template-Wahl.
~20 fixe Layout-Presets mit definierten Bildpositionen, Textblöcken (Schriftgröße, Zeichenlimit), die das LLM nur noch befüllt.

## Aktueller Stand
- Bildkompression (1200px, ≤1MB) via `app/utils/image_utils.py`
- Multimodale LLM-Pässe (`plan.py`, `generate.py`)
- Captions + Seitentitel werden generiert, aber Placement/Sizing unzureichend
- 309/310 Tests grün (1 pre-existing failure)

## Relevante Dateien
```
app/photobook/plan.py          — Pass 1: Layout-Planung (→ Preset-Auswahl)
app/photobook/generate.py      — Pass 2: Slot-Zuweisung + Text (→ Preset-Befüllung)
app/photobook/renderer.py      — HTML-Assembler (→ vereinfachen)
app/photobook/validator.py     — Validierung (→ an Presets anpassen)
app/photobook/styles.css       — CSS Grid Layouts (→ pro Preset)
app/photobook/templates/*.json — 8 Templates (→ ~20 Presets)
app/photobook/template_loader.py — Laden der Presets
app/utils/image_utils.py       — compress_image_to_jpeg, encode_image_base64
app/state.py                   — AppState, PageDescription, PhotobookConfig
```

## Wichtige Specs
- `docs/superpowers/specs/2026-05-05-photobook-multimodal-design.md`
- `docs/superpowers/specs/2026-05-05-photobook-validator-fallback-design.md`
- `docs/superpowers/specs/2026-05-05-photobook-image-compression-design.md`
- `docs/superpowers/specs/2026-05-05-photobook-caption-fix-design.md`

## Preset-Design-Idee
- LLM wählt aus ~20 Presets (nicht aus 8 freien Templates)
- Jedes Preset: fixe Anzahl Bilder, Textblock-Positionen, Schriftgrößen, Zeichenlimits
- Pass 1: Preset-Auswahl pro Seite
- Pass 2: Bilder zuweisen + Text generieren (innerhalb der Preset-Constraints)
- Optional: vordefinierte Text-Elemente ("Bild 1: *llm-text*")

## Kommando
```bash
uv sync && uv run pytest tests/ -q  # 309/310 pass
```
