"""Tests für PhotobookPreset und get_photobook_preset."""
from app.photobook.presets import (
    PhotobookPreset,
    PHOTOBOOK_PRESETS,
    get_photobook_preset,
)
from app.photobook.image_selector import _build_batch_prompt
from app.photobook.plan import _build_plan_prompt


class TestPhotobookPresetModel:
    def test_valid_preset_creation(self):
        preset = PhotobookPreset(
            id="test",
            name="Test Preset",
            selection_criteria="wähle testbilder",
            layout_preferences="nutze tests",
            generation_instructions="schreibe testtext",
            text_enabled=True,
        )
        assert preset.id == "test"
        assert preset.name == "Test Preset"
        assert preset.selection_criteria == "wähle testbilder"
        assert preset.layout_preferences == "nutze tests"
        assert preset.generation_instructions == "schreibe testtext"
        assert preset.text_enabled is True

    def test_text_enabled_defaults_to_true(self):
        preset = PhotobookPreset(
            id="test",
            name="Test",
            selection_criteria="",
            layout_preferences="",
            generation_instructions="",
        )
        assert preset.text_enabled is True


class TestPhotobookPresetsMap:
    def test_all_five_presets_defined(self):
        expected_ids = {
            "nature_outdoor",
            "culture_architecture",
            "people",
            "nature_collage",
            "mixed",
        }
        assert set(PHOTOBOOK_PRESETS.keys()) == expected_ids

    def test_each_preset_is_valid_model(self):
        for preset in PHOTOBOOK_PRESETS.values():
            assert isinstance(preset, PhotobookPreset)
            assert preset.id
            assert preset.name

    def test_nature_collage_has_text_disabled(self):
        preset = PHOTOBOOK_PRESETS["nature_collage"]
        assert preset.text_enabled is False

    def test_mixed_has_empty_criteria_prefs_instructions(self):
        preset = PHOTOBOOK_PRESETS["mixed"]
        assert preset.selection_criteria == ""
        assert preset.layout_preferences == ""
        assert preset.generation_instructions == ""
        assert preset.text_enabled is True

    def test_non_mixed_presets_have_criteria(self):
        for pid, preset in PHOTOBOOK_PRESETS.items():
            if pid != "mixed":
                assert preset.selection_criteria != "", f"{pid} hat leere selection_criteria"
                assert preset.layout_preferences != "", f"{pid} hat leere layout_preferences"
                # nature_collage generiert keine Texte, daher keine instructions nötig
                if pid != "nature_collage":
                    assert preset.generation_instructions != "", f"{pid} hat leere generation_instructions"


class TestGetPhotobookPreset:
    def test_valid_id_returns_correct_preset(self):
        preset = get_photobook_preset("nature_outdoor")
        assert preset.id == "nature_outdoor"
        assert preset.name == "Natur, Outdoor & Sport"

    def test_invalid_id_falls_back_to_mixed(self):
        preset = get_photobook_preset("nonexistent")
        assert preset.id == "mixed"

    def test_empty_string_falls_back_to_mixed(self):
        preset = get_photobook_preset("")
        assert preset.id == "mixed"


class TestImageSelectorPresetIntegration:
    def test_build_batch_prompt_injects_selection_criteria(self):
        preset = PhotobookPreset(
            id="test",
            name="Test Preset",
            selection_criteria="Wähle nur Sonnenuntergänge.",
            layout_preferences="",
            generation_instructions="",
            text_enabled=True,
        )
        prompt = _build_batch_prompt(batch_size=5, select_count=2, preset=preset)
        assert "Test Preset" in prompt
        assert "Wähle nur Sonnenuntergänge." in prompt
        assert "--- Bild 0 ---" in prompt
        assert "--- Bild 4 ---" in prompt

    def test_build_batch_prompt_mixed_preset_uses_default_criteria(self):
        preset = PHOTOBOOK_PRESETS["mixed"]
        prompt = _build_batch_prompt(batch_size=3, select_count=1, preset=preset)
        assert "Gemischt" in prompt
        assert "starke Motive" in prompt


class TestPlanPresetIntegration:
    def test_build_plan_prompt_injects_layout_preferences(self):
        preset = PhotobookPreset(
            id="test",
            name="Test Layout",
            selection_criteria="",
            layout_preferences="Bevorzuge nur 1-Bild-Presets.",
            generation_instructions="",
            text_enabled=True,
        )
        prompt = _build_plan_prompt(
            image_count=5,
            gpx_stats_d=None,
            notes=None,
            weather=None,
            poi_count=0,
            page_range=None,
            preset=preset,
        )
        assert "THEMA: Test Layout" in prompt
        assert "Bevorzuge nur 1-Bild-Presets." in prompt

    def test_build_plan_prompt_mixed_has_no_theme_section(self):
        preset = PHOTOBOOK_PRESETS["mixed"]
        prompt = _build_plan_prompt(
            image_count=5,
            gpx_stats_d=None,
            notes=None,
            weather=None,
            poi_count=0,
            page_range=None,
            preset=preset,
        )
        assert "THEMA:" not in prompt
