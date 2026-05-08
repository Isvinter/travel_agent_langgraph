"""Preset-Metadaten fuer LLM-Prompts (leichtgewichtig, ohne JSON-Loading)."""

from pydantic import BaseModel

# Jeder Eintrag: (preset_id, image_count, has_text)
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


def get_preset_summary() -> str:
    """Erzeugt kompakte Preset-Übersicht für den LLM-Prompt."""
    lines = []
    for pid, count, text in PRESET_CATALOG:
        lines.append(f"  {pid}: {count} Bilder, Text={'ja' if text else 'nein'}")
    return "\n".join(lines)


def get_presets_by_image_count(count: int, has_text: bool | None = None) -> list[str]:
    """Filtert Presets nach Bildanzahl und optional Text."""
    result = []
    for pid, c, t in PRESET_CATALOG:
        if c == count:
            if has_text is None or t == has_text:
                result.append(pid)
    return result


def get_any_preset(count: int) -> str:
    """Gibt das erste Preset mit der angegebenen Bildanzahl zurück (Fallback)."""
    for pid, c, _ in PRESET_CATALOG:
        if c == count:
            return pid
    return "quad_grid"  # ultimativer Fallback


# Constraint-Tabelle für Pass-2-Prompt
TEXT_CONSTRAINTS = {
    "title":   {"char_limit": 60,   "font_size": "14pt", "description": "Seitentitel (bold)"},
    "caption": {"char_limit": 500,  "font_size": "10pt", "description": "Bildunterschrift (italic)"},
    "intro":   {"char_limit": 1200, "font_size": "11pt", "description": "Einleitungstext"},
}


def get_constraint_summary() -> str:
    """Erzeugt Constraint-Text für den LLM-Prompt."""
    lines = ["TEXT-CONSTRAINTS (UNBEDINGT EINHALTEN):"]
    for role, c in TEXT_CONSTRAINTS.items():
        lines.append(f"  {role}: max. {c['char_limit']} Zeichen, Schriftgröße {c['font_size']} ({c['description']})")
    return "\n".join(lines)


class PhotobookPreset(BaseModel):
    """Thematisches Fotobuch-Preset — steuert LLM-Anweisungen in 3 Phasen."""
    id: str
    name: str
    selection_criteria: str
    layout_preferences: str
    generation_instructions: str
    text_enabled: bool = True


PHOTOBOOK_PRESETS: dict[str, PhotobookPreset] = {
    "nature_outdoor": PhotobookPreset(
        id="nature_outdoor",
        name="Natur, Outdoor & Sport",
        selection_criteria=(
            "Fokussiere auf Bilder mit Outdoor-Aktivitäten (Wandern, Klettern, "
            "Paragliding, Skitouren, Mountainbike), Landschaften und Natur. "
            "Wähle eine abwechslungsreiche Mischung aus Action-Aufnahmen, "
            "Panoramen, Detailaufnahmen und stimmungsvollen Momenten."
        ),
        layout_preferences=(
            "Erstelle ein abwechslungsreiches Layout. Verwende grossformatige "
            "Einzelbilder für Landschaftspanoramen, 2er/3er-Kombinationen für "
            "Aktionssequenzen und 4er/5er-Grids für Stimmungs-Collagen. "
            "Variiere zwischen Text- und Bild-lastigen Seiten."
        ),
        generation_instructions=(
            "Schreibe im Stil eines Reise-/Adventure-Blogs: lebendig, "
            "atmosphärisch, mit Fokus auf das Erlebnis und die Aktivität. "
            "Beschreibe sowohl die Landschaft als auch die Aktion — was "
            "wurde gemacht, wie war die Stimmung, welche Herausforderungen "
            "gab es? Nutze die Zeichenlimits aus."
        ),
        text_enabled=True,
    ),
    "culture_architecture": PhotobookPreset(
        id="culture_architecture",
        name="Kultur, Architektur & Städte",
        selection_criteria=(
            "Fokussiere auf Gebäude, Denkmäler, Stadtansichten, architektonische "
            "Details, Kirchen, Burgen und kulturell interessante Motive. "
            "Vermeide reine Naturbilder ohne kulturellen Bezug."
        ),
        layout_preferences=(
            "Bevorzuge Presets mit Text (image_text_split, single_text_below) "
            "für architektonische Beschreibungen. Nutze 2er/3er-Presets für "
            "Detailvergleiche."
        ),
        generation_instructions=(
            "Beschreibe Architektur, Geschichte und kulturellen Kontext. "
            "Gehe auf Baustil, Epoche, Besonderheiten und historische "
            "Hintergründe ein."
        ),
        text_enabled=True,
    ),
    "people": PhotobookPreset(
        id="people",
        name="Menschen",
        selection_criteria=(
            "Fokussiere auf Menschen: Porträts, Gruppenaufnahmen, emotionale "
            "Momente, Aktivitäten mit Personen. Vermeide reine Landschaftsbilder "
            "ohne Menschen."
        ),
        layout_preferences=(
            "Bevorzuge Presets mit mehreren Bildern (quad_grid, double_stacked) "
            "für Personengruppen. Verwende Einzelbild-Presets für Porträts."
        ),
        generation_instructions=(
            "Beschreibe die Menschen auf den Bildern: Stimmung, Aktivität, "
            "Situation, Emotionen. Erzähle kleine Geschichten zu den "
            "Momentaufnahmen."
        ),
        text_enabled=True,
    ),
    "nature_collage": PhotobookPreset(
        id="nature_collage",
        name="Natur-Bildercollagen",
        selection_criteria=(
            "Fokussiere auf Landschaftsaufnahmen, weite Panoramen, Vegetation, "
            "Tiere, Naturdetails."
        ),
        layout_preferences=(
            "Verwende AUSSCHLIESSLICH Presets ohne Text. Bevorzuge 3er-, 4er- "
            "und 5er-Grids (collage_5, quad_grid, triple_stacked). "
            "Das Fotobuch ist eine reine Bilder-Collage."
        ),
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


def get_photobook_preset(preset_id: str) -> PhotobookPreset:
    """Liefert das Preset-Objekt, mit Fallback auf 'mixed'."""
    return PHOTOBOOK_PRESETS.get(preset_id, PHOTOBOOK_PRESETS["mixed"])
