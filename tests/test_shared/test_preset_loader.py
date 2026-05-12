"""Tests für den shared Preset-Loader."""
import json
import pytest
from app.shared.preset_loader import load_preset, load_all_presets, PresetSlot, Preset


@pytest.fixture
def presets_dir(tmp_path):
    d = tmp_path / "presets"
    d.mkdir()
    preset_data = {
        "id": "test_single",
        "name": "Test Single",
        "description": "Ein Test-Preset",
        "image_count": 1,
        "has_text": False,
        "css_class": "preset-test-single",
        "slots": [
            {"id": "img", "type": "image", "css_area": "img", "optional": False}
        ],
    }
    (d / "test_single.json").write_text(json.dumps(preset_data))
    return str(d)


class TestPresetLoader:
    @pytest.mark.unit
    def test_load_single_preset(self, presets_dir):
        preset = load_preset("test_single", presets_dir)
        assert preset.id == "test_single"
        assert preset.image_count == 1
        assert len(preset.slots) == 1

    @pytest.mark.unit
    def test_load_all_presets(self, presets_dir):
        all_presets = load_all_presets(presets_dir)
        assert "test_single" in all_presets

    @pytest.mark.unit
    def test_missing_preset_raises(self, presets_dir):
        with pytest.raises(FileNotFoundError):
            load_preset("nicht_existent", presets_dir)

    @pytest.mark.unit
    def test_presets_dir_cache_is_isolated(self, tmp_path):
        """Zwei Verzeichnisse geben separate Presets."""
        d1 = tmp_path / "p1"
        d1.mkdir()
        d2 = tmp_path / "p2"
        d2.mkdir()
        (d1 / "a.json").write_text(json.dumps({
            "id": "a", "name": "A", "description": "", "image_count": 1,
            "has_text": False, "css_class": "c", "slots": []
        }))
        (d2 / "b.json").write_text(json.dumps({
            "id": "b", "name": "B", "description": "", "image_count": 2,
            "has_text": False, "css_class": "c", "slots": []
        }))
        p1 = load_all_presets(str(d1))
        p2 = load_all_presets(str(d2))
        assert "a" in p1
        assert "b" not in p1
        assert "b" in p2
        assert "a" not in p2
