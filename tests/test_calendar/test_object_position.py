"""Layer 4: object-position Berechnung."""
import pytest
from app.calendar.layouts import SlotDimensions, SLOT_DIMENSIONS


def _get_object_position(slot_dims: SlotDimensions, image_orientation: str) -> str:
    """Bestimmt den object-position Wert basierend auf Slot-Format und Bild-Orientierung."""
    if slot_dims.aspect_ratio > 1.5 and image_orientation == "portrait":
        return "center 30%"
    elif slot_dims.aspect_ratio > 1.5:
        return "center center"
    elif slot_dims.aspect_ratio < 0.67 and image_orientation == "landscape":
        return "30% center"
    else:
        return "center center"


class TestObjectPosition:
    @pytest.mark.unit
    def test_portrait_in_wide_slot(self):
        """Portrait-Bild in breitem Slot: obere Hälfte zeigen."""
        wide_slot = SLOT_DIMENSIONS["cal_double_stacked"]["top"]
        assert wide_slot.aspect_ratio > 1.5
        assert _get_object_position(wide_slot, "portrait") == "center 30%"

    @pytest.mark.unit
    def test_landscape_in_wide_slot(self):
        """Landscape in Breitslot: normal zentriert."""
        wide_slot = SLOT_DIMENSIONS["cal_double_stacked"]["top"]
        assert _get_object_position(wide_slot, "landscape") == "center center"

    @pytest.mark.unit
    def test_landscape_in_tall_slot(self):
        """Landscape in Hochslot: linke Hälfte zeigen."""
        tall_slot = SLOT_DIMENSIONS["cal_triple_row"]["l"]
        assert tall_slot.aspect_ratio < 0.67
        assert _get_object_position(tall_slot, "landscape") == "30% center"

    @pytest.mark.unit
    def test_portrait_in_tall_slot(self):
        """Portrait in Hochslot: normal zentriert."""
        tall_slot = SLOT_DIMENSIONS["cal_triple_row"]["l"]
        assert _get_object_position(tall_slot, "portrait") == "center center"

    @pytest.mark.unit
    def test_square_slot_always_center(self):
        """Quadratischer Slot: immer center center."""
        square_slot = SLOT_DIMENSIONS["cal_double_side"]["left"]
        assert 0.67 <= square_slot.aspect_ratio <= 1.5
        assert _get_object_position(square_slot, "landscape") == "center center"
        assert _get_object_position(square_slot, "portrait") == "center center"
        assert _get_object_position(square_slot, "square") == "center center"

    @pytest.mark.unit
    def test_square_image_always_center(self):
        """Square-Bild: immer center center, unabhängig vom Slot."""
        wide_slot = SLOT_DIMENSIONS["cal_double_stacked"]["top"]
        tall_slot = SLOT_DIMENSIONS["cal_triple_row"]["l"]
        assert _get_object_position(wide_slot, "square") == "center center"
        assert _get_object_position(tall_slot, "square") == "center center"
