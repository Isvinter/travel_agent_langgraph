import os
import pytest
from app.calendar.layouts import CALENDAR_LAYOUT_SEQUENCE, MONTH_NAMES, get_total_image_slots


class TestCalendarLayoutSequence:
    @pytest.mark.unit
    def test_sequence_has_13_entries(self):
        assert len(CALENDAR_LAYOUT_SEQUENCE) == 13

    @pytest.mark.unit
    def test_first_entry_is_cover(self):
        assert CALENDAR_LAYOUT_SEQUENCE[0][0] == "Deckblatt"
        assert CALENDAR_LAYOUT_SEQUENCE[0][1] == "cal_cover"

    @pytest.mark.unit
    def test_last_entry_is_december(self):
        assert CALENDAR_LAYOUT_SEQUENCE[12][0] == "Dezember"

    @pytest.mark.unit
    def test_all_presets_exist(self):
        presets_dir = os.path.join(
            os.path.dirname(__file__), "..", "..", "app", "calendar", "preset_data"
        )
        for month, preset_id in CALENDAR_LAYOUT_SEQUENCE:
            json_path = os.path.join(presets_dir, f"{preset_id}.json")
            assert os.path.exists(json_path), f"Preset {preset_id} fehlt: {json_path}"


class TestMonthNames:
    @pytest.mark.unit
    def test_12_months(self):
        assert len(MONTH_NAMES) == 12

    @pytest.mark.unit
    def test_januar_first(self):
        assert MONTH_NAMES[0] == "Januar"

    @pytest.mark.unit
    def test_dezember_last(self):
        assert MONTH_NAMES[11] == "Dezember"


class TestTotalImageSlots:
    @pytest.mark.unit
    def test_total_is_35(self):
        total = get_total_image_slots()
        assert total == 35

    @pytest.mark.unit
    def test_cover_has_one_slot(self):
        total = get_total_image_slots()
        month_total = total - 1
        assert month_total == 34
