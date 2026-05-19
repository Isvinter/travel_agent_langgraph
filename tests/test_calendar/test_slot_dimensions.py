"""Layer 2: Slot-Dimensionen und Aspekt-Verhältnisse."""
import pytest
from app.calendar.layouts import (
    CALENDAR_LAYOUT_SEQUENCE,
    SLOT_DIMENSIONS,
    SlotDimensions,
    IMAGE_AREA_ASPECT_RATIO,
)


class TestSlotDimensionsExist:
    @pytest.mark.unit
    def test_all_presets_have_dimensions(self):
        """Alle 13 Presets aus CALENDAR_LAYOUT_SEQUENCE sind in SLOT_DIMENSIONS."""
        for _, preset_id in CALENDAR_LAYOUT_SEQUENCE:
            assert preset_id in SLOT_DIMENSIONS, (
                f"Preset {preset_id} fehlt in SLOT_DIMENSIONS"
            )

    @pytest.mark.unit
    def test_slot_ids_match_preset_slots(self):
        """Jeder Slot in SLOT_DIMENSIONS entspricht den Preset-JSON-Slots."""
        import os
        from app.shared.preset_loader import load_preset

        presets_dir = os.path.join(
            os.path.dirname(__file__), "..", "..",
            "app", "calendar", "preset_data",
        )
        for _, preset_id in CALENDAR_LAYOUT_SEQUENCE:
            preset = load_preset(preset_id, presets_dir)
            dims = SLOT_DIMENSIONS[preset_id]
            json_slot_ids = {s.id for s in preset.slots if s.type == "image"}
            dim_slot_ids = set(dims.keys())
            assert json_slot_ids == dim_slot_ids, (
                f"{preset_id}: JSON={json_slot_ids}, DIMS={dim_slot_ids}"
            )


class TestSlotAspectRatios:
    @pytest.mark.unit
    def test_double_stacked_top_is_wide(self):
        """cal_double_stacked top slot ist breit (>1.5)."""
        top = SLOT_DIMENSIONS["cal_double_stacked"]["top"]
        assert top.aspect_ratio > 1.5, f"Erwartet >1.5, ist {top.aspect_ratio}"

    @pytest.mark.unit
    def test_double_stacked_bottom_is_ultra_wide(self):
        """cal_double_stacked bottom slot ist sehr breit (>3.0)."""
        bottom = SLOT_DIMENSIONS["cal_double_stacked"]["bottom"]
        assert bottom.aspect_ratio > 3.0, f"Erwartet >3.0, ist {bottom.aspect_ratio}"

    @pytest.mark.unit
    def test_triple_row_slots_are_tall(self):
        """cal_triple_row slots sind hochformatig (<0.67)."""
        for slot_id in ["l", "m", "r"]:
            slot = SLOT_DIMENSIONS["cal_triple_row"][slot_id]
            assert slot.aspect_ratio < 0.67, (
                f"{slot_id}: Erwartet <0.67, ist {slot.aspect_ratio}"
            )

    @pytest.mark.unit
    def test_double_side_slots_are_squareish(self):
        """cal_double_side slots sind etwa quadratisch (0.67–1.5)."""
        for slot_id in ["left", "right"]:
            slot = SLOT_DIMENSIONS["cal_double_side"][slot_id]
            assert 0.67 <= slot.aspect_ratio <= 1.5, (
                f"{slot_id}: Erwartet 0.67–1.5, ist {slot.aspect_ratio}"
            )

    @pytest.mark.unit
    def test_quad_big_left_right_slots_are_wide(self):
        """cal_quad_big_left rechte Slots sind breit (>1.5)."""
        for slot_id in ["rt", "rm", "rb"]:
            slot = SLOT_DIMENSIONS["cal_quad_big_left"][slot_id]
            assert slot.aspect_ratio > 1.5, (
                f"{slot_id}: Erwartet >1.5, ist {slot.aspect_ratio}"
            )

    @pytest.mark.unit
    def test_all_aspect_ratios_positive(self):
        """Alle Aspekt-Verhältnisse sind >0 und endlich."""
        for preset_id, slots in SLOT_DIMENSIONS.items():
            for slot_id, dims in slots.items():
                assert dims.aspect_ratio > 0, (
                    f"{preset_id}/{slot_id}: aspekt={dims.aspect_ratio}"
                )
                assert dims.aspect_ratio != float("inf"), (
                    f"{preset_id}/{slot_id}: aspekt=inf"
                )

    @pytest.mark.unit
    def test_slot_classification(self):
        """Hilfsfunktion zum Klassifizieren von Slots."""
        def classify(ratio: float) -> str:
            if ratio > 1.5:
                return "wide"
            elif ratio < 0.67:
                return "tall"
            return "square"

        # cal_single_full: ganzes Bild → breit
        assert classify(SLOT_DIMENSIONS["cal_single_full"]["img"].aspect_ratio) == "wide"

        # cal_triple_row: 3 Spalten → hoch
        assert classify(SLOT_DIMENSIONS["cal_triple_row"]["l"].aspect_ratio) == "tall"

        # cal_double_side: 2 Spalten nebeneinander → quadratisch
        assert classify(SLOT_DIMENSIONS["cal_double_side"]["left"].aspect_ratio) == "square"

        # cal_quad_grid: 2×2 → breit (Landscape)
        assert classify(SLOT_DIMENSIONS["cal_quad_grid"]["tl"].aspect_ratio) == "wide"
