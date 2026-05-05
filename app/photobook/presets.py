"""Preset-Metadaten fuer LLM-Prompts (leichtgewichtig, ohne JSON-Loading)."""

# Jeder Eintrag: (preset_id, image_count, has_text)
PRESET_CATALOG = [
    # Cover
    ("cover_hero", 1, True),
    # 1-Bild
    ("single_full", 1, False),
    ("single_text_below", 1, True),
    ("single_text_right", 1, True),
    # 2-Bild
    ("double_equal", 2, False),
    ("double_dominant", 2, False),
    ("double_text_below", 2, True),
    ("double_text_right", 2, True),
    # 3-Bild
    ("triple_strip", 3, False),
    ("triple_big_top", 3, False),
    ("triple_text_below", 3, True),
    ("triple_big_text_below", 3, True),
    ("triple_text_right", 3, True),
    # 4-Bild
    ("quad_grid", 4, False),
    ("quad_grid_text_below", 4, True),
    ("quad_strip_text_below", 4, True),
    ("quad_large_plus_3", 4, True),
    # Extra
    ("panorama", 1, True),
    ("collage_5", 5, False),
    ("image_text_split", 1, True),
    ("map_focus", 2, True),
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
    "title":   {"char_limit": 60,  "font_size": "14pt", "description": "Seitentitel (bold)"},
    "caption": {"char_limit": 170, "font_size": "9pt",  "description": "Bildunterschrift (italic)"},
    "intro":   {"char_limit": 400, "font_size": "11pt", "description": "Einleitungstext"},
}


def get_constraint_summary() -> str:
    """Erzeugt Constraint-Text für den LLM-Prompt."""
    lines = ["TEXT-CONSTRAINTS (UNBEDINGT EINHALTEN):"]
    for role, c in TEXT_CONSTRAINTS.items():
        lines.append(f"  {role}: max. {c['char_limit']} Zeichen, Schriftgröße {c['font_size']} ({c['description']})")
    return "\n".join(lines)
