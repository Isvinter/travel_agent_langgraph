# Design: Preset-basiertes Layout-System für Photopuch

**Datum:** 2026-05-05
**Status:** approved
**Kontext:** Layout-Qualität unzureichend — LLM hat zu viel Freiheit bei Template-Wahl, Textmenge unkontrolliert, Placement/Sizing arbiträr.

## Problem

Das aktuelle System (8 Templates, freie LLM-Wahl) führt zu:
- Monotoner Template-Wahl (grid_2x2 dominiert)
- Unkontrollierter Textmenge (LLM generiert zu viel/zu wenig)
- Falscher Slot-Zuordnung (Bilder landen in falschen Grid-Areas)
- Captions ohne dedizierten Platz im Layout
- Inkonsistenten Schriftgrößen

## Ziel

Preset-basiertes Layout-System: ~20 fixe Layout-Presets mit definierten Bildpositionen, Textblöcken (Schriftgröße, Zeichenlimit), die das LLM nur noch auswählt und befüllt.

## Entscheidungen

| Entscheidung | Gewählte Option | Begründung |
|---|---|---|
| Template-System | Komplett ersetzen durch Presets | Alte Templates + Kategorien fliegen raus — sauberer Schnitt |
| Preset-Anzahl | 20 (16 Pflicht + 4 kreativ) | Deckt 1-4 Bild-Seiten ab + Cover + Spezial-Layouts |
| Text-Constraints | Font-Size + Char-Limit im Preset verdrahtet | Verhindert zu viel Text; LLM sieht Limits im Prompt |
| Pipeline-Struktur | 2 LLM-Pässe (wie bisher) | Pass 1 = Preset wählen, Pass 2 = Slots befüllen |
| Variety-Enforcement | Prompt-Regeln + Validator Safety-Net | Doppelter Boden: LLM-Anleitung + harte Validator-Checks |
| Datenformat | JSON-Presets (wie alte Templates) | Bewährtes Format, backwards-kompatibel mit `template_loader.py` |

---

## 1. Preset-Katalog (21 Presets: 1 Cover + 16 Standard + 4 Extra)

### Cover (1)
| ID | Name | Bilder | Text | Beschreibung |
|---|---|---|---|---|
| `cover_hero` | Cover Hero | 1 | ✅ Titel (60 Z.) | Titelseite mit Bild und Buchtitel |

### 1-Bild-Seiten (3)
| ID | Name | Bilder | Text | Zeichen |
|---|---|---|---|---|
| `single_full` | Einzelbild Vollformat | 1 | ❌ | — |
| `single_text_below` | Einzelbild mit Unterschrift | 1 | ✅ Caption | 170 Z. |
| `single_text_right` | Einzelbild + Text rechts | 1 | ✅ Caption | 170 Z. |

### 2-Bild-Seiten (4)
| ID | Name | Bilder | Text | Zeichen |
|---|---|---|---|---|
| `double_equal` | Zwei Bilder gleich | 2 | ❌ | — |
| `double_dominant` | Groß + Klein | 2 | ❌ | — |
| `double_text_below` | Zwei Bilder + Unterschrift | 2 | ✅ Caption | 170 Z. |
| `double_text_right` | Zwei Bilder + Text rechts | 2 | ✅ Caption | 170 Z. |

### 3-Bild-Seiten (5)
| ID | Name | Bilder | Text | Zeichen |
|---|---|---|---|---|
| `triple_strip` | Drei quer | 3 | ❌ | — |
| `triple_big_top` | Eins groß + zwei klein | 3 | ❌ | — |
| `triple_text_below` | Drei quer + Unterschrift | 3 | ✅ Caption | 170 Z. |
| `triple_big_text_below` | Groß + zwei + Unterschrift | 3 | ✅ Caption | 170 Z. |
| `triple_text_right` | Drei + Text rechts | 3 | ✅ Caption | 170 Z. |

### 4-Bild-Seiten (4)
| ID | Name | Bilder | Text | Zeichen |
|---|---|---|---|---|
| `quad_grid` | 2×2 Raster | 4 | ❌ | — |
| `quad_grid_text_below` | 2×2 + Unterschrift | 4 | ✅ Caption | 170 Z. |
| `quad_strip_text_below` | Vier quer + Unterschrift | 4 | ✅ Caption | 170 Z. |
| `quad_large_plus_3` | Eins groß + drei + Text | 4 | ✅ Caption | 170 Z. |

### Extra / Kreativ (4)
| ID | Name | Bilder | Text | Zeichen |
|---|---|---|---|---|
| `panorama` | Panorama | 1 | ✅ Caption | 100 Z. |
| `collage_5` | Collage 5 Bilder | 5 | ❌ | — |
| `image_text_split` | Bild/Text 50:50 | 1 | ✅ Intro | 400 Z. |
| `map_focus` | Karte + Bild | 2 | ✅ Caption | 170 Z. |

---

## 2. Text-Constraint-System

### Text-Rollen

| Rolle | Font-Size | Char-Limit | CSS-Style | Verwendung |
|---|---|---|---|---|
| `title` | 14pt bold | 60 Z. | Georgia, #222 | Seitentitel, Kapitelüberschrift |
| `caption` | 9pt italic | 170 Z. | Georgia, #777 | Bildunterschrift, Kurzkontext |
| `intro` | 11pt | 400 Z. | Georgia, #444, lh:1.6 | Einleitungstext, Kapitel-Intro |

### Slot-Definition (JSON)

```json
{
  "id": "caption",
  "type": "text",
  "css_area": "caption",
  "char_limit": 170,
  "font_size": "9pt",
  "text_role": "caption",
  "optional": true
}
```

**Kern-Idee:** Font-Size + Char-Limit sind im Preset fest verdrahtet. Das LLM sieht sie im Prompt und wird aufgefordert, sich daran zu halten. Der Validator prüft nach und kürzt Overflow-Text. Bilder stehen immer im Vordergrund — Text ist unterstützend, max. 30% der Seitenfläche.

---

## 3. Pipeline-Architektur

### Fluss

```
Bilder + Kontext
     │
     ▼
Pass 1: plan.py (LLM multimodal)
  → Wählt 1 Preset pro Seite
  → Kriterium: Bildanzahl + Text ja/nein
  → Variety-Regeln im Prompt
     │
     ▼
Pass 2: generate.py (LLM multimodal)
  → Bilder den Image-Slots zuweisen
  → Text generieren (≤ Char-Limit, Font-Size vorgegeben)
  → Output: Slots mit image_index + text + caption
     │
     ▼
Validator (deterministisch)
  → Char-Limit-Overflow → Text kürzen
  → Slot-Konsistenz gegen Preset prüfen
  → Variety-Checks (Cover, Back-to-Back, Text-Lücke, etc.)
     │
     ▼
Renderer
  → Font-Size aus Slot-Def direkt ins CSS
  → Grid-Layout aus Preset-css_class
  → Kein Template-Lookup nötig
```

### Änderungen pro Datei

| Datei | Änderung | Aufwand |
|---|---|---|
| `plan.py` | Prompt: Preset-Katalog statt Template-Kategorien. Output: `preset_id` pro Seite. Variety-Regeln im Prompt. Fallback überarbeitet. | mittel |
| `generate.py` | Prompt: Constraint-Tabelle (Char-Limits, Font-Sizes). Output: Slots innerhalb Limits. Kein Template-Wählen mehr. | mittel |
| `validator.py` | Neue Checks: Char-Limit-Overflow (kürzen), Preset-Konsistenz (statt Template), Variety-Checks. | mittel |
| `renderer.py` | Vereinfachung: Font-Size aus Slot-Definition. Kein Template-Lookup. Direktes Rendering aus PageDescription. | klein |
| `template_loader.py` | Umbenennen zu `preset_loader.py` oder anpassen. Lädt 20 neue Preset-JSONs. | klein |
| `templates/*.json` | 8 alte löschen, 20 neue erstellen (mit Text-Constraints). | mittel |
| `styles.css` | 20 neue CSS-Grid-Layouts. Alte 8 Layout-Klassen entfernen. | mittel |
| `state.py` | PageDescription unverändert. Optional: `PresetConfig`-Modell. | klein |

---

## 4. Variety-Enforcement

### Prompt-Regeln (lenken das LLM)

1. Max. 2× das gleiche Preset im gesamten Buch
2. Nicht 2× hintereinander das gleiche Preset
3. Max. 3 Seiten ohne Text hintereinander
4. Nicht 3× hintereinander gleiche Bildanzahl
5. Dramatischer Bogen: Cover → ruhig (1-Bild) → Mix (2-3) → Höhepunkt (4-Bild) → Ausklang (1-Bild)

### Validator-Checks (Safety-Net)

| Check | Regel | Bei Verstoß |
|---|---|---|
| Cover | Seite 0 muss `cover_hero` sein | Erzwingen |
| Back-to-Back | Nicht 2× gleiches Preset hintereinander | Nächstes Preset gleicher Bildanzahl |
| Text-Lücke | Max. 3 Seiten ohne Text | Nächstes No-Text → Text-Preset |
| Bildanzahl-Monotonie | Max. 2 Seiten gleiche Bildanzahl | Preset mit anderer Bildanzahl |
| Gesamt-Variety | Min. 5 verschiedene Presets | Duplikate ersetzen |

**Reparatur-Priorität:** Preset erhalten → nächstbestes Preset gleicher Bildanzahl → Bildanzahl wechseln (letzte Instanz).

---

## 5. Datenmodell

### Preset-JSON (Beispiel: `single_text_below.json`)

```json
{
  "id": "single_text_below",
  "name": "Einzelbild mit Unterschrift",
  "image_count": 1,
  "has_text": true,
  "css_class": "preset-single-text-below",
  "slots": [
    {
      "id": "main",
      "type": "image",
      "css_area": "main",
      "priority": "primary"
    },
    {
      "id": "caption",
      "type": "text",
      "css_area": "caption",
      "char_limit": 170,
      "font_size": "9pt",
      "text_role": "caption",
      "optional": true
    }
  ]
}
```

### SlotDefinition (Pydantic, neu)

```python
class SlotDefinition(BaseModel):
    id: str
    type: str                              # "image" | "text"
    priority: Optional[str] = None         # "primary" | "secondary" | None
    css_area: str
    optional: bool = False
    char_limit: Optional[int] = None       # NEU: nur für type="text"
    font_size: Optional[str] = None        # NEU: z.B. "9pt", "11pt", "14pt"
    text_role: Optional[str] = None        # NEU: "title" | "caption" | "intro"
```

### Prompt-Format für Pass 1 (Preset-Katalog)

```json
[
  {"preset_id": "single_full",      "images": 1, "has_text": false},
  {"preset_id": "single_text_below", "images": 1, "has_text": true},
  {"preset_id": "single_text_right", "images": 1, "has_text": true},
  {"preset_id": "double_equal",     "images": 2, "has_text": false},
  ...
]
```

### Prompt-Format für Pass 2 (Constraints)

```
TEXT-CONSTRAINTS:
- title: max. 60 Zeichen, Schriftgröße 14pt bold
- caption: max. 170 Zeichen, Schriftgröße 9pt italic
- intro: max. 400 Zeichen, Schriftgröße 11pt
```

---

## 6. CSS Grid Layouts

Pro Preset ein CSS-Grid (20 Layout-Klassen). Namensschema: `preset-{preset_id}`.

Beispiel:
```css
.preset-single-text-below {
  display: grid;
  grid-template-columns: 1fr;
  grid-template-rows: 7fr 3fr;
  grid-template-areas: "main" "caption";
  gap: 4mm;
}
```

---

## 7. Migration

Schritte in Reihenfolge:

1. **Preset-JSONs erstellen** — 20 neue JSON-Dateien in `app/photobook/presets/` (neues Verzeichnis)
2. **Preset-Loader anpassen** — `template_loader.py` → lädt aus `presets/` statt `templates/`
3. **SlotDefinition erweitern** — `char_limit`, `font_size`, `text_role` hinzufügen
4. **styles.css neu** — 20 Grid-Layouts, alte 8 entfernen
5. **plan.py umbauen** — Preset-Katalog im Prompt, Variety-Regeln, Fallback
6. **generate.py umbauen** — Constraint-Tabelle im Prompt, Text innerhalb Limits
7. **validator.py erweitern** — Char-Limit-Checks, Variety-Checks
8. **renderer.py vereinfachen** — Font-Size aus Slot, kein Template-Lookup
9. **Alte Templates löschen** — `app/photobook/templates/*.json` entfernen
10. **Tests anpassen + neu schreiben**

---

## 8. Tests

### Anzupassen
- `test_plan.py` — Prompt und Fallback auf Presets umstellen
- `test_generate.py` — Prompt und Fallback auf Presets umstellen
- `test_renderer.py` — Font-Size-Rendering, keine Template-Auflösung
- `test_validator.py` — Neue Checks abdecken
- `test_template_loader.py` — Preset-Loader statt Template-Loader

### Neu
- `test_presets.py` — Alle 20 Presets laden, Slots validieren, Char-Limits prüfen
- `test_variety.py` — Variety-Validator-Checks (Cover, Back-to-Back, Text-Lücke, etc.)
- `test_text_overflow.py` — Validator kürzt Text über Char-Limit

### Integration
- `test_photobook_pipeline.py` — End-to-End mit Presets (Mock-LLM)
- `test_variety_integration.py` — Variety-Checks in voller Pipeline

---

## Risiken

- **Mittel:** 20 CSS-Grid-Layouts müssen korrekt sein — visuelle Tests mit Screenshots
- **Mittel:** LLM könnte Preset-Auswahl trotz Prompt-Regeln monoton treffen — Validator als Safety-Net
- **Gering:** Migration von 8 zu 20 Presets — Tests fangen Regressions ab
- **Gering:** Alte Test-Mocks müssen auf neue Preset-Struktur umgestellt werden
