"""Fixe Layout-Sequenz und Monatsnamen."""

MONTH_NAMES = [
    "Januar", "Februar", "März", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember",
]

# (Monat-Name, Preset-ID) — fixe Reihenfolge über 12 Monate + Deckblatt
CALENDAR_LAYOUT_SEQUENCE: list[tuple[str, str]] = [
    ("Deckblatt", "cal_cover"),
    ("Januar", "cal_single_full"),
    ("Februar", "cal_double_side"),
    ("März", "cal_triple_big_top"),
    ("April", "cal_quad_grid"),
    ("Mai", "cal_triple_row"),
    ("Juni", "cal_double_stacked"),
    ("Juli", "cal_quad_big_left"),
    ("August", "cal_triple_stacked"),
    ("September", "cal_quad_panorama"),
    ("Oktober", "cal_triple_lshape"),
    ("November", "cal_quad_two_big"),
    ("Dezember", "cal_single_full"),
]


def get_total_image_slots() -> int:
    """Berechnet die Gesamtzahl der Bild-Slots über alle Seiten."""
    import os
    from app.shared.preset_loader import load_preset

    presets_dir = os.path.join(os.path.dirname(__file__), "preset_data")
    total = 0
    for _, preset_id in CALENDAR_LAYOUT_SEQUENCE:
        preset = load_preset(preset_id, presets_dir)
        total += preset.image_count
    return total
