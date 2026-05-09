"""Preset-Metadaten fuer LLM-Prompts (leichtgewichtig, ohne JSON-Loading)."""

from pydantic import BaseModel


def _build_catalog():
    """Erzeugt Preset-Catalog aus geladenen JSON-Presets (vermeidet Divergenz)."""
    from app.photobook.preset_loader import load_all_presets
    presets = load_all_presets()
    # Sortierung wie im originalen PRESET_CATALOG: nach Bildanzahl,
    # dann spezifische Reihenfolge (cover zuerst, dann single/double/triple/quad/collage)
    _IMAGE_COUNT_PRIORITY = {
        "cover_hero": 0,
        "single_full": 1, "single_text_below": 2, "single_text_left": 3, "panorama": 4, "image_text_split": 5,
        "double_stacked": 1, "double_stacked_text": 2, "double_text_right": 3, "map_focus": 4,
        "triple_stacked": 1, "triple_stacked_text": 2, "triple_big_top": 3, "triple_big_text_below": 4,
        "quad_grid": 1, "quad_grid_text": 2, "quad_large_plus_3": 3,
        "collage_5": 1,
    }
    catalog = [(p.id, p.image_count, p.has_text) for p in presets.values()]
    catalog.sort(key=lambda x: (x[1], _IMAGE_COUNT_PRIORITY.get(x[0], 99)))
    return catalog


def _get_catalog() -> list:
    """Lazy-load den Catalog (einmaliger JSON-I/O)."""
    global _PRESET_CATALOG
    if _PRESET_CATALOG is None:
        _PRESET_CATALOG = _build_catalog()
    return _PRESET_CATALOG


_PRESET_CATALOG = None


def get_preset_summary() -> str:
    """Erzeugt kompakte Preset-Übersicht für den LLM-Prompt."""
    lines = []
    for pid, count, text in _get_catalog():
        lines.append(f"  {pid}: {count} Bilder, Text={'ja' if text else 'nein'}")
    return "\n".join(lines)


def get_presets_by_image_count(count: int, has_text: bool | None = None) -> list[str]:
    """Filtert Presets nach Bildanzahl und optional Text."""
    result = []
    for pid, c, t in _get_catalog():
        if c == count:
            if has_text is None or t == has_text:
                result.append(pid)
    return result


def get_any_preset(count: int) -> str:
    """Gibt das erste Preset mit der angegebenen Bildanzahl zurück (Fallback)."""
    for pid, c, _ in _get_catalog():
        if c == count:
            return pid
    return "quad_grid"  # ultimativer Fallback


def _build_text_constraints():
    """Erzeugt TEXT_CONSTRAINTS aus geladenen JSON-Presets (vermeidet Divergenz)."""
    from app.photobook.preset_loader import load_all_presets
    presets = load_all_presets()
    constraints = {}
    # Title ist universell (page-header), nicht in JSON-Slots definiert
    constraints["title"] = {"char_limit": 60, "font_size": "14pt", "description": "Seitentitel (bold)"}
    for preset in presets.values():
        for slot in preset.slots:
            if slot.type == "text" and slot.text_role and slot.text_role not in constraints:
                constraints[slot.text_role] = {
                    "char_limit": slot.char_limit or 0,
                    "font_size": slot.font_size or "inherit",
                    "description": _describe_text_role(slot.text_role),
                }
    return constraints


def _describe_text_role(role: str) -> str:
    """Beschreibung für Text-Rollen."""
    descriptions = {
        "title": "Seitentitel (bold)",
        "caption": "Bildunterschrift (italic)",
        "intro": "Einleitungstext",
    }
    return descriptions.get(role, role)


def _get_text_constraints():
    """Lazy-load Text-Constraints aus Presets."""
    global _TEXT_CONSTRAINTS
    if _TEXT_CONSTRAINTS is None:
        _TEXT_CONSTRAINTS = _build_text_constraints()
    return _TEXT_CONSTRAINTS


_TEXT_CONSTRAINTS = None


def get_constraint_summary() -> str:
    """Erzeugt Constraint-Text für den LLM-Prompt."""
    lines = ["TEXT-CONSTRAINTS (UNBEDINGT EINHALTEN):"]
    for role, c in _get_text_constraints().items():
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
