"""Tests für den Preset-Loader."""
import pytest
from app.photobook.preset_loader import (
    load_preset,
    load_all_presets,
)


class TestPresetLoader:
    def test_load_all_presets_returns_non_empty_dict(self):
        """Nachdem alle Presets erstellt sind, muss load_all_presets() sie alle liefern."""
        presets = load_all_presets()
        assert isinstance(presets, dict)
        assert len(presets) > 0, "No presets loaded"

    def test_unknown_preset_raises(self):
        with pytest.raises(FileNotFoundError):
            load_preset("nonexistent_preset")

    def test_all_presets_have_valid_slots(self):
        presets = load_all_presets()
        assert len(presets) > 0, "No presets loaded"
        for pid, preset in presets.items():
            for slot in preset.slots:
                assert slot.type in ("image", "text"), (
                    f"{pid}: slot {slot.id} hat ungültigen type {slot.type}"
                )
                assert slot.css_area, f"{pid}: slot {slot.id} hat kein css_area"
                if slot.type == "text":
                    assert slot.char_limit is not None, f"{pid}: text-slot {slot.id} hat kein char_limit"
                    assert slot.font_size is not None, f"{pid}: text-slot {slot.id} hat kein font_size"
                    assert slot.text_role is not None, f"{pid}: text-slot {slot.id} hat kein text_role"

    def test_cover_hero_exists(self):
        """Cover-Preset muss existieren (worst-case Fallback im Validator)."""
        preset = load_preset("cover_hero")
        assert preset.image_count == 1
        assert preset.has_text is True

    def test_preset_loader_returns_expected_structure(self):
        """Ein konkretes Preset hat die richtigen Werte."""
        preset = load_preset("single_text_below")
        assert preset.id == "single_text_below"
        assert preset.image_count == 1
        assert preset.has_text is True
        image_slots = [s for s in preset.slots if s.type == "image"]
        text_slots = [s for s in preset.slots if s.type == "text"]
        assert len(image_slots) == 1
        assert len(text_slots) >= 1
        caption = text_slots[0]
        assert caption.char_limit == 170
        assert caption.font_size == "9pt"
        assert caption.text_role == "caption"


class TestPresetCatalog:
    def test_catalog_has_21_entries(self):
        from app.photobook.presets import PRESET_CATALOG
        assert len(PRESET_CATALOG) == 21

    def test_get_presets_by_image_count(self):
        from app.photobook.presets import get_presets_by_image_count
        p1 = get_presets_by_image_count(1)
        # cover_hero, single_full, single_text_below, single_text_right, panorama, image_text_split
        assert len(p1) == 6
        p3 = get_presets_by_image_count(3)
        assert len(p3) == 5

    def test_get_presets_by_count_and_text(self):
        from app.photobook.presets import get_presets_by_image_count
        p3_no_text = get_presets_by_image_count(3, has_text=False)
        assert len(p3_no_text) == 2  # triple_strip, triple_big_top
        p3_text = get_presets_by_image_count(3, has_text=True)
        assert len(p3_text) == 3

    def test_get_any_preset_returns_valid(self):
        from app.photobook.presets import get_any_preset
        assert get_any_preset(1) == "cover_hero"
        assert get_any_preset(3) == "triple_strip"
        assert get_any_preset(99) == "quad_grid"

    def test_constraint_summary_contains_limits(self):
        from app.photobook.presets import get_constraint_summary
        summary = get_constraint_summary()
        assert "60" in summary
        assert "170" in summary
        assert "400" in summary
        assert "14pt" in summary
        assert "9pt" in summary
        assert "11pt" in summary
