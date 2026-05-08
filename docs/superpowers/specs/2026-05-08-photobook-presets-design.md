# Photobook Presets — Thematische Fotobuch-Presets

**Datum:** 2026-05-08
**Status:** Approved

## Ziel

Integration von 5 thematischen Fotobuch-Presets, die primär über unterschiedliche LLM-Anweisungen in
den drei Photobook-Phasen (Bildauswahl, Layout-Planung, Seiten-Generierung) gesteuert werden.

## Presets

| ID                  | Name                     | Besonderheit                  |
|---------------------|--------------------------|-------------------------------|
| `nature_outdoor`    | Natur, Outdoor & Sport   | Adventure/Travel, hohe kreative Freiheit |
| `culture_architecture` | Kultur, Architektur & Städte | Fokus auf Gebäude, Geschichte |
| `people`            | Menschen                 | Porträts, Gruppen, Aktivitäten |
| `nature_collage`    | Natur-Bildercollagen     | Rein visuell, keine Texte      |
| `mixed`             | Gemischt                 | Aktuelles Verhalten (Default)  |

## Datenmodell

### Neues Model in `app/photobook/presets.py`

```python
class PhotobookPreset(BaseModel):
    id: str                       # "nature_outdoor", "mixed", ...
    name: str                     # "Natur, Outdoor & Sport"
    selection_criteria: str       # Prompt-Fragment für image_selector
    layout_preferences: str       # Prompt-Fragment für plan.py
    generation_instructions: str  # Prompt-Fragment für generate.py
    text_enabled: bool = True     # False für nature_collage
```

### Preset-Map (statisch, analog zu PRESET_CATALOG)

```python
PHOTOBOOK_PRESETS: dict[str, PhotobookPreset] = {
    "nature_outdoor": PhotobookPreset(
        id="nature_outdoor",
        name="Natur, Outdoor & Sport",
        selection_criteria="Fokussiere auf Bilder mit Outdoor-Aktivitäten (Wandern, Klettern, "
                           "Paragliding, Skitouren, Mountainbike), Landschaften und Natur. "
                           "Wähle eine abwechslungsreiche Mischung aus Action-Aufnahmen, "
                           "Panoramen, Detailaufnahmen und stimmungsvollen Momenten.",
        layout_preferences="Erstelle ein abwechslungsreiches Layout. Verwende grossformatige "
                            "Einzelbilder für Landschaftspanoramen, 2er/3er-Kombinationen für "
                            "Aktionssequenzen und 4er/5er-Grids für Stimmungs-Collagen. "
                            "Variiere zwischen Text- und Bild-lastigen Seiten.",
        generation_instructions="Schreibe im Stil eines Reise-/Adventure-Blogs: lebendig, "
                                 "atmosphärisch, mit Fokus auf das Erlebnis und die Aktivität. "
                                 "Beschreibe sowohl die Landschaft als auch die Aktion — was "
                                 "wurde gemacht, wie war die Stimmung, welche Herausforderungen "
                                 "gab es? Nutze die Zeichenlimits aus.",
        text_enabled=True,
    ),
    "culture_architecture": PhotobookPreset(
        id="culture_architecture",
        name="Kultur, Architektur & Städte",
        selection_criteria="Fokussiere auf Gebäude, Denkmäler, Stadtansichten, architektonische "
                           "Details, Kirchen, Burgen und kulturell interessante Motive. "
                           "Vermeide reine Naturbilder ohne kulturellen Bezug.",
        layout_preferences="Bevorzuge Presets mit Text (image_text_split, single_text_below) "
                            "für architektonische Beschreibungen. Nutze 2er/3er-Presets für "
                            "Detailvergleiche.",
        generation_instructions="Beschreibe Architektur, Geschichte und kulturellen Kontext. "
                                 "Gehe auf Baustil, Epoche, Besonderheiten und historische "
                                 "Hintergründe ein.",
        text_enabled=True,
    ),
    "people": PhotobookPreset(
        id="people",
        name="Menschen",
        selection_criteria="Fokussiere auf Menschen: Porträts, Gruppenaufnahmen, emotionale "
                           "Momente, Aktivitäten mit Personen. Vermeide reine Landschaftsbilder "
                           "ohne Menschen.",
        layout_preferences="Bevorzuge Presets mit mehreren Bildern (quad_grid, double_stacked) "
                            "für Personengruppen. Verwende Einzelbild-Presets für Porträts.",
        generation_instructions="Beschreibe die Menschen auf den Bildern: Stimmung, Aktivität, "
                                 "Situation, Emotionen. Erzähle kleine Geschichten zu den "
                                 "Momentaufnahmen.",
        text_enabled=True,
    ),
    "nature_collage": PhotobookPreset(
        id="nature_collage",
        name="Natur-Bildercollagen",
        selection_criteria="Fokussiere auf Landschaftsaufnahmen, weite Panoramen, Vegetation, "
                           "Tiere, Naturdetails.",
        layout_preferences="Verwende AUSSCHLIESSLICH Presets ohne Text. Bevorzuge 3er-, 4er- "
                            "und 5er-Grids (collage_5, quad_grid, triple_stacked). "
                            "Das Fotobuch ist eine reine Bilder-Collage.",
        generation_instructions="",
        text_enabled=False,
    ),
    "mixed": PhotobookPreset(
        id="mixed",
        name="Gemischt",
        selection_criteria="",
        layout_preferences="",
        generation_instructions="",
        text_enabled=True,
    ),
}
```

### Hilfsfunktion

```python
def get_photobook_preset(preset_id: str) -> PhotobookPreset:
    """Liefert das Preset-Objekt, mit Fallback auf 'mixed'."""
    return PHOTOBOOK_PRESETS.get(preset_id, PHOTOBOOK_PRESETS["mixed"])
```

## OutputConfig-Änderung

In `app/state.py`:

```python
class OutputConfig(BaseModel):
    # ... bestehende Felder ...
    photobook_preset: Literal[
        "nature_outdoor", "culture_architecture", "people", "nature_collage", "mixed"
    ] = "mixed"
```

## Integration in die 3 LLM-Phasen

### Phase 1: Bildauswahl (`app/photobook/image_selector.py`)

- `select_photobook_images()` bekommt neuen Parameter `preset: PhotobookPreset`
- Wenn `preset.selection_criteria` nicht leer ist, ersetzt es die hartkodierten Kriterien in `_build_batch_prompt()`
- Bei leerem String (mixed) bleibt das aktuelle Verhalten

### Phase 2: Layout-Planung (`app/photobook/plan.py`)

- `plan_photobook_layout()` bekommt neuen Parameter `preset: PhotobookPreset`
- `_build_plan_prompt()` fügt `preset.layout_preferences` nach den Variety-Regeln ein
- Bei leerem String (mixed) bleibt das aktuelle Verhalten

### Phase 3: Seiten-Generierung (`app/photobook/generate.py`)

- `generate_photobook_pages()` bekommt neuen Parameter `preset: PhotobookPreset`
- `_build_generate_prompt()`:
  - Fügt `preset.generation_instructions` bei "AUFGABE PRO SEITE" ein
  - Wenn `text_enabled=False`: Text-Pflicht-Block entfällt komplett, keine Text-Slot-Anforderungen
  - Bei leerem String (mixed) bleibt das aktuelle Verhalten

## Node-Änderungen

Drei Node-Funktionen lesen das Preset aus `state.output_config.photobook_preset`:

- `select_photobook_images_node` → `preset = get_photobook_preset(state.output_config.photobook_preset)`
- `plan_photobook_node` → dito
- `generate_photobook_node` → dito

## Was sich NICHT ändert

- `renderer.py`, `generate_pdf.py` — Rendering ist preset-unabhängig
- Graph-Routing — Datenfluss bleibt identisch
- `PhotobookConfig` — keine Änderung
- Frontend — Preset-Auswahl wird im Frontend hinzugefügt (separates Ticket)

## Testing

- Unit-Tests für `get_photobook_preset()` mit gültigen und ungültigen IDs
- Unit-Tests für die Prompt-Builder: verifizieren dass Preset-Fragmente korrekt eingewebt werden
- Integrationstest: Pipeline-Durchlauf mit `mixed`-Preset produziert identische Ergebnisse wie zuvor
- Keine LLM-abhängigen Tests nötig (die Prompt-Wirkung lässt sich nicht deterministisch testen)
