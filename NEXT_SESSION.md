# Photopuch Preset Redesign — Nächste Session

## Aktueller Stand

- 21 Preset-JSONs mit Text-Constraints (char_limit, font_size, text_role) ✅
- 21 CSS-Grid-Layouts in styles.css ✅
- Plan.py: Preset-Auswahl mit Variety-Regeln ✅
- Generate.py: Constraint-basierte Slot-Befüllung ✅
- Validator: Char-Limit-Checks + Variety-Enforcement ✅
- Renderer: Font-Size aus Slot-Definition ✅
- Altes Template-System komplett entfernt ✅
- **324/325 Tests grün** (1 pre-existing failure)
- **Commit:** `f71e601`

## Offene Bugs

### Bug 1: Textfelder fehlen im HTML-Output ⚠️ KRITISCH

**Symptom:** Alle Bilder füllen die komplette Seite aus. Kein Platz für Text. Auch Cover hat keinen Titel mehr.

**Root Cause (Vermutung):** `validate_page()` in `validator.py` prüft NICHT auf leere Text-Slots. Daher:
1. LLM liefert keine Text-Slots zurück → Slots sind leer
2. `validate_page()` findet keine Fehler (leere Slots sind kein Fehler)
3. `enforce_fallback()` wird nicht aufgerufen → Platzhalter werden nie gesetzt
4. Renderer sieht nur Image-Slots → HTML hat keine Text-Elemente

**Fix-Ansatz:** `validate_page()` muss leere Text-Slots als Fehler melden. Dann greift `enforce_fallback()` und füllt Platzhalter. ODER: `enforce_fallback()` IMMER aufrufen (nicht nur bei Fehlern), um Text-Slots zu garantieren.

### Bug 2: Bilder füllen komplette Seite (kein Grid-Layout)

**Symptom:** CSS-Grid scheint nicht zu greifen — Bilder nehmen 100% der Seite ein.

**Root Cause (Vermutung):** Entweder:
- Der Renderer verwendet nicht die richtige CSS-Klasse (`preset-*`)
- ODER die Grid-Template-Areas matchen nicht mit den Slot-css_areas
- ODER die Preset-Slots werden nicht korrekt den Grid-Areas zugewiesen

**Fix-Ansatz:** Systematisch testen:
1. Rendere eine einzelne Seite (cover_hero) und prüfe das HTML
2. Verifiziere dass `preset-cover-hero` CSS-Klasse gesetzt ist
3. Verifiziere dass `grid-area: main` und `grid-area: title` im HTML stehen
4. Prüfe ob die CSS-Grid-Areas korrekt definiert sind

## Wichtige Dateien für Debugging

```
app/photobook/generate.py     — Prompt + LLM-Parsing
app/photobook/validator.py    — validate_page(), enforce_fallback()
app/photobook/renderer.py     — HTML-Assembler
app/photobook/styles.css      — CSS-Grid-Layouts
app/photobook/preset_loader.py — Preset-Modelle + Loader
```

## Kommando

```bash
uv sync && uv run pytest tests/ -q  # 324/325 pass
```
