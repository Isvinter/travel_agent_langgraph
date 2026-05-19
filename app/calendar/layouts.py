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


from dataclasses import dataclass


@dataclass
class SlotDimensions:
    """Berechnete Slot-Maße aus dem CSS-Grid-Layout.

    width_ratio:  Anteil an der image-area-Breite (0..1)
    height_ratio: Anteil an der image-area-Höhe (0..1)
    aspect_ratio: width_ratio / height_ratio * IMAGE_AREA_ASPECT
                  (>1.5 = breit, <0.67 = hoch, sonst quadratisch)
    """
    width_ratio: float
    height_ratio: float
    aspect_ratio: float


IMAGE_AREA_ASPECT_RATIO = 1.86


def _compute_aspect(w: float, h: float) -> float:
    """Berechnet den Slot-Aspekt aus Grid-Fraktionen."""
    if h == 0:
        return float("inf")
    return (w / h) * IMAGE_AREA_ASPECT_RATIO


SLOT_DIMENSIONS: dict[str, dict[str, SlotDimensions]] = {
    "cal_single_full": {
        "img": SlotDimensions(1.0, 1.0, _compute_aspect(1.0, 1.0)),
    },
    "cal_double_side": {
        "left":  SlotDimensions(0.5, 1.0, _compute_aspect(0.5, 1.0)),
        "right": SlotDimensions(0.5, 1.0, _compute_aspect(0.5, 1.0)),
    },
    "cal_double_stacked": {
        "top":    SlotDimensions(1.0, 2/3, _compute_aspect(1.0, 2/3)),
        "bottom": SlotDimensions(1.0, 1/3, _compute_aspect(1.0, 1/3)),
    },
    "cal_triple_big_top": {
        "big":        SlotDimensions(1.0, 2/3, _compute_aspect(1.0, 2/3)),
        "small_left":  SlotDimensions(0.5, 1/3, _compute_aspect(0.5, 1/3)),
        "small_right": SlotDimensions(0.5, 1/3, _compute_aspect(0.5, 1/3)),
    },
    "cal_triple_row": {
        "l": SlotDimensions(1/3, 1.0, _compute_aspect(1/3, 1.0)),
        "m": SlotDimensions(1/3, 1.0, _compute_aspect(1/3, 1.0)),
        "r": SlotDimensions(1/3, 1.0, _compute_aspect(1/3, 1.0)),
    },
    "cal_triple_stacked": {
        "big":    SlotDimensions(2/3, 1.0, _compute_aspect(2/3, 1.0)),
        "top":    SlotDimensions(1/3, 0.5, _compute_aspect(1/3, 0.5)),
        "bottom": SlotDimensions(1/3, 0.5, _compute_aspect(1/3, 0.5)),
    },
    "cal_triple_lshape": {
        "main":   SlotDimensions(2/3, 1.0, _compute_aspect(2/3, 1.0)),
        "top":    SlotDimensions(1/3, 0.5, _compute_aspect(1/3, 0.5)),
        "bottom": SlotDimensions(1/3, 0.5, _compute_aspect(1/3, 0.5)),
    },
    "cal_quad_grid": {
        "tl": SlotDimensions(0.5, 0.5, _compute_aspect(0.5, 0.5)),
        "tr": SlotDimensions(0.5, 0.5, _compute_aspect(0.5, 0.5)),
        "bl": SlotDimensions(0.5, 0.5, _compute_aspect(0.5, 0.5)),
        "br": SlotDimensions(0.5, 0.5, _compute_aspect(0.5, 0.5)),
    },
    "cal_quad_big_left": {
        "big": SlotDimensions(2/3, 1.0, _compute_aspect(2/3, 1.0)),
        "rt":  SlotDimensions(1/3, 1/3, _compute_aspect(1/3, 1/3)),
        "rm":  SlotDimensions(1/3, 1/3, _compute_aspect(1/3, 1/3)),
        "rb":  SlotDimensions(1/3, 1/3, _compute_aspect(1/3, 1/3)),
    },
    "cal_quad_panorama": {
        "wide": SlotDimensions(1.0, 2/3, _compute_aspect(1.0, 2/3)),
        "bl":   SlotDimensions(1/3, 1/3, _compute_aspect(1/3, 1/3)),
        "bm":   SlotDimensions(1/3, 1/3, _compute_aspect(1/3, 1/3)),
        "br":   SlotDimensions(1/3, 1/3, _compute_aspect(1/3, 1/3)),
    },
    "cal_quad_two_big": {
        "tl": SlotDimensions(0.5, 2/3, _compute_aspect(0.5, 2/3)),
        "tr": SlotDimensions(0.5, 2/3, _compute_aspect(0.5, 2/3)),
        "bl": SlotDimensions(0.5, 1/3, _compute_aspect(0.5, 1/3)),
        "br": SlotDimensions(0.5, 1/3, _compute_aspect(0.5, 1/3)),
    },
    "cal_cover": {
        "cover_img": SlotDimensions(1.0, 1.0, _compute_aspect(1.0, 1.0)),
    },
}
