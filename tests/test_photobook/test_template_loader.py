# tests/test_photobook/test_template_loader.py
import pytest
from app.photobook.preset_loader import (
    load_preset,
    load_all_presets,
)


class TestPresetLoader:
    def test_load_cover_hero(self):
        preset = load_preset("cover_hero")
        assert preset.id == "cover_hero"
        assert preset.image_count == 1
        assert preset.has_text is True
        assert len(preset.slots) >= 1
        main_slot = [s for s in preset.slots if s.priority == "primary"]
        assert len(main_slot) == 1

    def test_load_double_dominant(self):
        preset = load_preset("double_dominant")
        assert preset.id == "double_dominant"
        assert preset.image_count == 2
        slot_ids = [s.id for s in preset.slots]
        assert "main" in slot_ids
        assert "secondary" in slot_ids

    def test_load_all_presets_returns_dict(self):
        presets = load_all_presets()
        assert isinstance(presets, dict)
        assert len(presets) >= 21
        assert "cover_hero" in presets
        assert "quad_grid" in presets
        assert "panorama" in presets

    def test_unknown_preset_raises(self):
        with pytest.raises(FileNotFoundError):
            load_preset("nonexistent_layout")

    def test_all_presets_have_valid_slots(self):
        presets = load_all_presets()
        for pid, p in presets.items():
            for slot in p.slots:
                assert slot.type in ("image", "text"), (
                    f"{pid}: slot {slot.id} has invalid type {slot.type}"
                )
                assert slot.css_area, f"{pid}: slot {slot.id} has no css_area"
