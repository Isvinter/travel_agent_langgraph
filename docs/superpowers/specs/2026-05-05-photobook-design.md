# Fotobuch-Generator — Design-Dokument

**Datum:** 2026-05-05
**Status:** Design-Phase (vor Implementation)
**Ziel:** Erweiterung des Travel-Agent-Systems um KI-gestützte Fotobuch-Generierung

---

## 1. Überblick

Das System soll zusätzlich zur Blog-Generierung auch die automatische Erstellung von Fotobüchern ermöglichen. Kernprinzip: **Trennung von Inhalt (LLM) und Darstellung (Renderer).**

Das LLM trifft strukturelle Entscheidungen (Seiten-Reihenfolge, Template-Auswahl, Bild-zu-Slot-Zuordnung) und generiert Bildunterschriften. Eine deterministische CSS-Grid-basierte Rendering-Engine setzt diese Entscheidungen visuell um und erzeugt ein druckfähiges PDF.

### Design-Entscheidungen (getroffen im Brainstorming)

| Entscheidung | Gewählte Option |
|---|---|
| Pipeline-Integration | Neuer Graph-Zweig nach `generate_enriched_map` |
| Output-Format | PDF (via Headless Chrome CDP) |
| Seitenformat | A4 Hochformat (210×297mm) |
| Doppelseiten | Als A3 Querformat (420×297mm) |
| Bildanzahl | 12–24 (konfigurierbar) |
| Bildauswahl | Eigene Bildauswahl (andere Kriterien als Blog) |
| Textumfang | V1: nur Bildunterschriften. Später: Textblöcke |

---

## 2. Architektur — Drei-Komponenten-System

```
┌─────────────────────┐     ┌─────────────────────┐     ┌─────────────────────┐
│   Layout-Katalog    │     │  LLM "Art Director" │     │   Rendering Engine  │
│   (statisch, JSON)  │     │  (Ollama, 2-Pass)   │     │   (CSS Grid, HTML)  │
├─────────────────────┤     ├─────────────────────┤     ├─────────────────────┤
│ • Template-Sammlung │     │ • Pass 1: Planung    │     │ • HTML Assembler    │
│ • Slot-Struktur     │     │   - Dramaturgie      │     │ • CSS Grid Mapping  │
│ • Constraints       │  →  │   - Seiten-Sequenz   │  →  │ • Bild-Skalierung   │
│ • CSS-Area Mapping  │     │ • Pass 2: Ausführung │     │ • PDF via Chrome    │
│ • Erweiterbar (JSON)│     │   - Template-Auswahl │     │ • Doppelseiten      │
│                     │     │   - Slot-Zuweisung   │     │                     │
│                     │     │   - Captions         │     │                     │
└─────────────────────┘     └─────────────────────┘     └─────────────────────┘
```

### Verantwortlichkeiten

| Komponente | Verantwortung |
|---|---|
| **Layout-Katalog** | Definiert verfügbare Design-Optionen als JSON |
| **LLM Art Director** | Trifft inhaltliche Entscheidungen (Was wird gezeigt?) |
| **Rendering Engine** | Setzt visuell um (Wie wird es dargestellt?) |
| **Validator** | Prüft LLM-Ausgabe auf Konsistenz (Post-Processing) |

---

## 3. Pipeline-Integration

Das Fotobuch wird als **neuer Graph-Zweig** im bestehenden LangGraph StateGraph integriert. Die Verzweigung erfolgt nach `generate_enriched_map`, da dort alle angereicherten Daten für beide Pfade bereitstehen.

### Erweiterte Pipeline

```
... bestehende Nodes (GPX, Bilder, Clustering, Enrichment) ...
                              ↓
                       generate_enriched_map
                              ↓
                    ┌─── MODE = ? ───┐
                    ↓                ↓
              BLOG PATH       PHOTOBOOK PATH
              (bestehend)     (neu)
                    ↓                ↓
              generate_blog    select_photobook_images
                    ↓                ↓
              design_blog      plan_photobook_layout
                    ↓                ↓
              persist_art      generate_photobook
                    ↓                ↓
              generate_pdf     render_photobook
                    ↓                ↓
                   END         generate_photobook_pdf
                                    ↓
                                   END
```

### Neue AppState-Felder

```python
class PhotobookConfig(BaseModel):
    photo_count: int = 16        # 12–24
    page_format: str = "A4"
    orientation: str = "portrait"

class OutputConfig(BaseModel):
    # ... bestehende Felder ...
    mode: str = "blog"           # "blog" | "photobook" | "both"
    photobook: PhotobookConfig = PhotobookConfig()

# Neue State-Felder:
class AppState(TypedDict):
    # ... bestehende Felder ...
    photobook_images: List[ImageData]
    photobook_plan: Optional[PhotobookPlan]
    photobook_pages: List[PageDescription]
    photobook_html: Optional[str]
    photobook_pdf_path: Optional[str]
```

### Neue LangGraph-Nodes

| Node | Input | Output | Beschreibung |
|---|---|---|---|
| `select_photobook_images` | Alle Bilder + Metadaten | `photobook_images` (12–24) | LLM-basierte Bildauswahl mit Layout-Eignungskriterien |
| `plan_photobook_layout` | `photobook_images` + Kontext | `photobook_plan` | LLM Pass 1: Dramaturgie + Seiten-Sequenz + grobe Bildverteilung |
| `generate_photobook` | `photobook_plan` | `photobook_pages` | LLM Pass 2: Template-Auswahl + Slot-Zuweisung + Captions |
| `render_photobook` | `photobook_pages` | `photobook_html` | CSS Grid HTML-Assemblierung |
| `generate_photobook_pdf` | `photobook_html` | `photobook_pdf_path` | Headless Chrome CDP → A4/A3 PDF |

### Routing-Logik

Der Routing-Node nach `generate_enriched_map` prüft `state.output_config.mode`:
- `"blog"` → bestehender Blog-Pfad (unverändert)
- `"photobook"` → Fotobuch-Pfad
- `"both"` → erst Blog-Pfad, dann Fotobuch-Pfad (sequentiell)

---

## 4. Template-Katalog

### Prinzip

Templates sind **datengetrieben** als JSON-Dateien im Verzeichnis `app/photobook/templates/` abgelegt. Neue Templates erfordern nur eine neue JSON-Datei + eine CSS-Klasse — kein Python-Code-Change.

### JSON-Schema

```json
{
  "id": "split_dominant",
  "name": "Split — Dominant + Sekundär",
  "category": "split",
  "description": "Großes Hauptbild + kleineres Sekundärbild auf einer Doppelseite",
  "page_type": "spread",
  "min_images": 2,
  "max_images": 2,
  "has_text": false,
  "supports_captions": true,
  "css_class": "layout-split-dominant",
  "slots": [
    {
      "id": "primary",
      "type": "image",
      "priority": "primary",
      "css_area": "main"
    },
    {
      "id": "secondary",
      "type": "image",
      "priority": "secondary",
      "css_area": "side"
    },
    {
      "id": "caption",
      "type": "caption",
      "css_area": "caption",
      "optional": true
    }
  ]
}
```

### Feld-Beschreibung

| Feld | Typ | Beschreibung |
|---|---|---|
| `id` | `str` | Eindeutige Template-ID (wird vom LLM referenziert) |
| `name` | `str` | Menschlich lesbarer Name |
| `category` | `str` | Kategorie für LLM-Gruppierung (hero, split, grid, mixed, strip) |
| `page_type` | `"single"` \| `"spread"` | A4 Einzelseite oder A3 Doppelseite |
| `min_images` / `max_images` | `int` | Bildanzahl-Constraints |
| `has_text` | `bool` | Enthält das Template Text-Slots? |
| `supports_captions` | `bool` | Können Caption-Slots verwendet werden? |
| `css_class` | `str` | CSS-Klasse für das Grid-Layout |
| `slots[]` | `List[Slot]` | Slot-Definitionen |

### Slot-Typen

| `type` | Beschreibung | Rendering |
|---|---|---|
| `image` | Bild-Slot (füllt Grid-Area) | `<img class="slot-image">` mit `object-fit: cover` |
| `text` | Textblock-Slot | `<div class="slot-text">` (für V2) |
| `caption` | Bildunterschrift | `<div class="slot-caption">` |

### V1 Templates (8 Layouts)

| # | ID | Slots | Kategorie | page_type | Captions |
|---|---|---|---|---|---|
| 1 | `hero_single` | 1 Bild | hero | single | Ja |
| 2 | `split_equal` | 2 Bilder, 50/50 | split | spread | Ja |
| 3 | `split_dominant` | 2 Bilder, 66/33 | split | spread | Ja |
| 4 | `grid_2x2` | 4 Bilder | grid | single | Nein |
| 5 | `strip_3` | 3 Bilder, Querstreifen | strip | single | Nein |
| 6 | `image_text_left` | 1 Bild + 1 Text | mixed | spread | Ja |
| 7 | `collection_3` | 3 Bilder, L+R unten | collection | single | Nein |
| 8 | `panorama` | 1 Bild, extragroß | hero | spread | Ja |

### Erweiterbarkeit

Neue Templates hinzufügen:
1. Neue JSON-Datei in `app/photobook/templates/` ablegen
2. CSS-Klasse mit `grid-template-areas` im Stylesheet definieren
3. Fertig — LLM und Renderer erkennen das Template automatisch

Overlap-Layouts: `css_area`-Namen können sich überlappende Grid-Areas zuweisen. Die visuelle Umsetzung (z-index, negative margins) passiert rein in CSS.

---

## 5. LLM Art Director — Zwei-Pass-Architektur

### Überblick

Das LLM arbeitet in zwei Durchläufen:
1. **Pass 1 (Planung):** Strukturelle Entscheidungen — Dramaturgie, Seiten-Sequenz, grobe Bildverteilung
2. **Pass 2 (Ausführung):** Konkrete Template-Auswahl, Slot-Zuweisung, Caption-Generierung

### Pass 1: Planung

**Input:**
- Alle Bilder (12–24) mit Cluster-Zugehörigkeit, GPS, Timestamp
- GPX-Stats (Distanz, Höhenmeter, Pausen)
- Tour-Notizen
- Wetter & POI-Kontext
- Template-**Kategorien** (nicht einzelne Templates): hero, split, grid, mixed, strip

**LLM-Aufgabe:**
- Dramaturgischen Bogen planen (Cover → Aufbau → Highlight → Variation → Abschluss)
- Jeder Seite eine Template-Kategorie zuweisen
- Bilder grob auf Seiten verteilen (nur image_indices)
- Globale Layout-Regeln beachten

**Output:**
```json
{
  "pages": [
    {
      "position": 0,
      "page_type": "cover",
      "template_category": "hero",
      "image_indices": [3],
      "purpose": "Cover — Gipfelaufnahme bei Sonnenaufgang"
    },
    {
      "position": 1,
      "page_type": "spread",
      "template_category": "split",
      "image_indices": [7, 12],
      "purpose": "Aufstieg durch den Wald"
    }
  ],
  "dramatic_arc": "intro → buildup → highlight → variation → conclusion"
}
```

### Pass 2: Ausführung

**Input:**
- Seitenplan aus Pass 1
- Vollständiger Template-Katalog (alle 8+ Templates mit Slot-Details)
- Bildqualitäts-Scores (aus `review_content`-Node)

**LLM-Aufgabe:**
- Für jede Seite das konkrete Template aus der Kategorie wählen
- Bilder auf Slots abbilden (primary-Slot bekommt das wichtigste Bild)
- Captions generieren (basierend auf Bildinhalt, GPS-Kontext, Tour-Notizen)
- Layout-Wiederholungs-Regeln final prüfen

**Output (pro Seite):**
```json
{
  "template_id": "split_dominant",
  "page_type": "spread",
  "slots": [
    {
      "slot_id": "primary",
      "image_index": 7,
      "caption": "Der schmale Waldweg schlängelt sich durch dichtes Unterholz."
    },
    {
      "slot_id": "secondary",
      "image_index": 12,
      "caption": "Erster freier Blick ins Tal auf 1200m Höhe."
    }
  ]
}
```

### Globale Layout-Regeln (im System-Prompt)

| Regel | Beschreibung | Durchsetzung |
|---|---|---|
| Keine Wiederholung >2× | Gleiches Template max. 2× hintereinander | LLM (Pass 1+2) |
| Hero-Anker | Mind. jede 4.–6. Seite ein Hero-Template | LLM (Pass 1) |
| Dichte-Wechsel | Grid-Seiten (dicht) ↔ Single-Seiten (ruhig) abwechseln | LLM (Pass 1+2) |
| Cover + Rückseite | Erste und letzte Seite sind Hero-Templates | LLM (Pass 1) |
| Priorität → Slot-Größe | Wichtigere Bilder → größere Slots (primary) | LLM (Pass 2) |
| Bildanzahl = Slot-Anzahl | Template muss genug Slots haben | Validator |

### Validator (Post-Processing, deterministisch)

Ein deterministischer Validator prüft die LLM-Ausgabe vor dem Rendering:

- `template_id` existiert im Katalog
- Bildanzahl pro Seite ≤ `template.max_images`
- Pflicht-Slots sind befüllt
- Image-Indizes sind im gültigen Bereich
- Kein Bild wird doppelt verwendet
- `page_type` konsistent mit Template

---

## 6. Rendering Engine

### Architektur

```
Seitenbeschreibungen (JSON)  →  HTML Assembler  →  CSS Grid HTML  →  Headless Chrome  →  PDF
```

### CSS Grid Mapping

Jedes Template-JSON definiert `css_area`-Namen pro Slot. Diese korrespondieren 1:1 mit CSS `grid-template-areas`:

```css
/* Template: split_dominant (spread) */
.layout-split-dominant {
  display: grid;
  grid-template-columns: 2fr 1fr;
  grid-template-rows: 1fr auto;
  grid-template-areas:
    "main side"
    "caption caption";
  gap: 4mm;
  width: 420mm;    /* A3 landscape = 2× A4 */
  height: 297mm;
  padding: 8mm;
  box-sizing: border-box;
  background: #fff;
}

/* Einzelseite (A4) */
.layout-hero-single {
  display: grid;
  grid-template-areas:
    "main"
    "caption";
  grid-template-rows: 1fr auto;
  width: 210mm;
  height: 297mm;
  padding: 8mm;
  box-sizing: border-box;
  background: #fff;
}

/* Universelle Slot-Klassen */
.slot-image {
  object-fit: cover;
  width: 100%;
  height: 100%;
}

.slot-caption {
  font-family: Georgia, serif;
  font-size: 10pt;
  color: #555;
  line-height: 1.4;
  padding: 4mm 0 0 0;
}
```

### Seiten-Typen

| page_type | CSS-Dimensionen | @page Regel |
|---|---|---|
| `single` | 210mm × 297mm | `@page { size: A4; margin: 0; }` |
| `spread` | 420mm × 297mm | `@page { size: A3 landscape; margin: 0; }` |

### Renderer-Pseudocode

```python
def render_photobook(pages: List[PageDescription], images: List[ImageData]) -> str:
    """Erzeugt vollständiges HTML-Dokument aus Seitenbeschreibungen."""
    templates = load_all_templates()  # aus app/photobook/templates/*.json

    html_parts = [PHOTOBOOK_HEADER]  # <!DOCTYPE>, <head>, <style>

    for page in pages:
        template = templates[page.template_id]
        css = f'page {template.page_type}'
        html_parts.append(f'<div class="{template.css_class} {css}">')

        for slot_desc in page.slots:
            slot_def = find_slot_def(template, slot_desc.slot_id)
            if slot_def.type == "image":
                img = images[slot_desc.image_index]
                html_parts.append(
                    f'<img class="slot-image" '
                    f'style="grid-area:{slot_def.css_area}" '
                    f'src="{normalize_path(img.path)}">'
                )
            elif slot_def.type == "caption":
                html_parts.append(
                    f'<div class="slot-caption" '
                    f'style="grid-area:{slot_def.css_area}">'
                    f'{slot_desc.caption}</div>'
                )

        html_parts.append('</div>')

    html_parts.append(PHOTOBOOK_FOOTER)
    return "\n".join(html_parts)
```

### Bildverarbeitung

- **object-fit: cover** — Bilder füllen Slots ohne Verzerrung
- **object-position**: V1 `center`; V2: LLM kann Fokus setzen (z.B. `center top`)
- **Komprimierung**: Vor Rendering auf 300dpi-Zielauflösung skalieren (2480×3508px für A4)
- **Pfade**: Absolute `file:///` Pfade für Chrome-PDF
- **Fehlende Bilder**: Grauer Platzhalter mit Dateiname als Fallback

### PDF-Generierung

Wiederverwendung des bestehenden `generate_pdf`-Patterns (Selenium + Chrome CDP):

```python
def generate_photobook_pdf(html_content: str, output_path: str) -> str:
    """Headless Chrome → PDF via CDP Page.printToPDF."""
    # Gleicher Mechanismus wie app/services/generate_pdf.py
    # @page CSS regelt A4/A3 abhängig von page_type
```

---

## 7. Testing & Error Handling

### Test-Pyramide

1. **Unit Tests** — Renderer, Validator, Template Loader (ohne LLM)
2. **Integration Tests** — Graph Nodes, Image Selection, PDF (mit mock_ollama)
3. **E2E (manuell)** — Vollständiger Pipeline-Run

### Unit Tests (ohne LLM)

```python
# tests/test_photobook/test_renderer.py
def test_render_split_dominant():
    page = PageDescription(
        template_id="split_dominant",
        page_type="spread",
        slots=[
            SlotAssignment(slot_id="primary", image_index=0, caption="Hauptbild"),
            SlotAssignment(slot_id="secondary", image_index=1, caption="Nebenbild"),
        ]
    )
    html = render_photobook([page])
    assert "layout-split-dominant" in html
    assert "slot-image" in html
    assert "grid-template-areas" in html

def test_render_single_page_dimensions():
    page = PageDescription(template_id="hero_single", page_type="single", slots=[...])
    html = render_photobook([page])
    assert "width: 210mm" in html
    assert "height: 297mm" in html

# tests/test_photobook/test_validator.py
def test_validator_rejects_overfill():
    page = PageDescription(template_id="hero_single", slots=[
        SlotAssignment(slot_id="main", image_index=0),
        SlotAssignment(slot_id="main", image_index=1),  # FEHLER
    ])
    errors = validate_page(page)
    assert len(errors) == 1

def test_validator_unknown_template():
    page = PageDescription(template_id="nonexistent", slots=[])
    errors = validate_page(page)
    assert any("unknown template" in e.lower() for e in errors)
```

### Integration Tests (mit Mock-LLM)

```python
# tests/test_graph/test_photobook_graph.py
def test_select_photobook_images(mock_ollama_response, sample_state):
    mock_ollama_response.return_value = {
        "message": {"content": json.dumps({"selected_indices": list(range(16))})}
    }
    result = select_photobook_images_node(sample_state)
    assert len(result["photobook_images"]) == 16

def test_graph_photobook_branch(sample_state):
    sample_state["output_config"].mode = "photobook"
    graph = build_graph()
    result = graph.invoke(sample_state)
    assert result["photobook_pdf_path"] is not None
```

### Fehlerstrategie

| Fehlerfall | Strategie | Level |
|---|---|---|
| LLM liefert kein valides JSON | JSON extrahieren, Re-Prompt mit Fehlerhinweis | ERROR |
| Validator findet Fehler | Einzelne fehlerhafte Seiten → Fallback `grid_2x2` | WARN |
| Bild fehlt auf Disk | Platzhalter generieren, Log-Warnung | WARN |
| Chrome/PDF nicht verfügbar | HTML speichern, Fehler melden | ERROR |
| Ollama Timeout | Retry 3× mit exponentiellem Backoff | ERROR |
| < 5 Bilder verfügbar | Pipeline stoppt, klare Fehlermeldung | ERROR |

### Test-Fixtures

```json
// tests/fixtures/photobook_pages.json — Mock-Seiten für Renderer-Tests
[
  {
    "template_id": "hero_single",
    "page_type": "single",
    "slots": [
      {"slot_id": "main", "image_index": 0, "caption": "Titelbild"}
    ]
  },
  {
    "template_id": "grid_2x2",
    "page_type": "single",
    "slots": [
      {"slot_id": "tl", "image_index": 1},
      {"slot_id": "tr", "image_index": 2},
      {"slot_id": "bl", "image_index": 3},
      {"slot_id": "br", "image_index": 4}
    ]
  }
]
```

---

## 8. Dateistruktur (geplant)

```
app/
├── photobook/
│   ├── __init__.py
│   ├── templates/
│   │   ├── hero_single.json
│   │   ├── split_equal.json
│   │   ├── split_dominant.json
│   │   ├── grid_2x2.json
│   │   ├── strip_3.json
│   │   ├── image_text_left.json
│   │   ├── collection_3.json
│   │   └── panorama.json
│   ├── template_loader.py       # JSON → Template-Objekte laden
│   ├── plan_photobook.py        # LLM Pass 1: Seitenplan
│   ├── generate_photobook.py    # LLM Pass 2: Templates + Captions
│   ├── render_photobook.py      # HTML Assembler (CSS Grid)
│   ├── generate_photobook_pdf.py # Headless Chrome → PDF
│   ├── validator.py             # LLM-Output Validierung
│   └── styles.css               # CSS Grid Styles für alle Templates
├── nodes/
│   ├── select_photobook_images_node.py
│   ├── plan_photobook_node.py
│   ├── generate_photobook_node.py
│   ├── render_photobook_node.py
│   └── generate_photobook_pdf_node.py
└── state.py                     # Erweiterte AppState + PhotobookConfig

tests/
├── test_photobook/
│   ├── __init__.py
│   ├── test_renderer.py
│   ├── test_validator.py
│   ├── test_template_loader.py
│   ├── test_photobook_pdf.py
│   └── test_photobook_graph.py
└── fixtures/
    ├── photobook_pages.json
    └── mock_templates.json
```

---

## 9. Zusammenfassung

### Was diese Architektur gut macht

1. **Trennung von Verantwortung** — LLM entscheidet WAS, Renderer entscheidet WIE
2. **Deterministischer Renderer** — CSS Grid ist vorhersagbar und druckbar
3. **Datengetriebene Templates** — Neue Layouts = JSON + CSS, kein Code
4. **Zwei-Pass-LLM** — Planung und Ausführung sind getrennt validierbar
5. **Robuste Fehlerbehandlung** — Fallback-Layouts, deterministischer Validator
6. **Minimal invasiv** — Bestehende Blog-Pipeline bleibt unverändert
7. **Testbar ohne LLM** — Renderer + Validator arbeiten mit Mock-Daten

### Offene Punkte für V2+

- Bildqualitäts-Ranking für bessere Slot-Priorisierung
- Automatische Fokus-Erkennung für `object-position`
- Mehr Text-Layouts (V1 nur Captions)
- Overlap-/Collage-Layouts
- Frontend-UI-Komponente für Fotobuch-Konfiguration
- `mode="both"` (Blog + Fotobuch in einem Durchlauf)
- Kunden-spezifische Template-Pakete
