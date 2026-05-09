"""Tests fuer LLM Pass 2: Slot-Zuweisung mit Preset-Constraints."""
import json
from unittest.mock import patch, MagicMock
from app.state import ImageData, PageDescription, PhotobookPlan, PagePlan
from app.photobook.generate import generate_photobook_pages

MOCK_PLAN = PhotobookPlan(pages=[
    PagePlan(position=0, preset_id="cover_hero", image_indices=[0], purpose="Cover"),
    PagePlan(position=1, preset_id="double_stacked", image_indices=[1, 2], purpose="Aufstieg"),
])

MOCK_GENERATE_CONTENT = json.dumps([
    {"preset_id": "cover_hero", "slots": [
        {"slot_id": "main", "image_index": 0},
        {"slot_id": "title", "text": "Gipfelblick"},
    ]},
    {"preset_id": "double_stacked", "slots": [
        {"slot_id": "top", "image_index": 1},
        {"slot_id": "bottom", "image_index": 2},
    ]},
])

SAMPLE_IMAGES = [ImageData(path=f"/tmp/img_{i}.jpg") for i in range(16)]


class TestGenerate:
    @patch("app.photobook.generate.call_ollama")
    def test_generate_returns_page_descriptions(self, mock_call):
        mock_call.return_value = MOCK_GENERATE_CONTENT
        result = generate_photobook_pages(
            plan=MOCK_PLAN, images=SAMPLE_IMAGES, gpx_stats={}, notes="Test", model="test-model",
        )
        assert len(result) == 2
        assert isinstance(result[0], PageDescription)
        assert result[0].template_id == "cover_hero"
        assert result[1].template_id == "double_stacked"

    def test_fallback_on_empty_plan(self):
        result = generate_photobook_pages(
            plan=PhotobookPlan(pages=[]), images=SAMPLE_IMAGES[:4], gpx_stats={}, notes=None, model="test-model",
        )
        assert len(result) == 0

    @patch("app.photobook.generate.call_ollama")
    def test_generate_handles_missing_images(self, mock_call):
        mock_call.return_value = json.dumps([
            {"preset_id": "cover_hero", "slots": [{"slot_id": "main", "image_index": 999}]},
        ])
        result = generate_photobook_pages(
            plan=MOCK_PLAN, images=SAMPLE_IMAGES[:3], gpx_stats={}, notes="Test", model="test-model",
        )
        assert len(result) >= 0

    def test_fallback_uses_preset_from_plan(self):
        """Fallback soll das im Plan gewählte Preset respektieren."""
        plan = PhotobookPlan(pages=[
            PagePlan(position=0, preset_id="cover_hero", image_indices=[0]),
            PagePlan(position=1, preset_id="double_stacked", image_indices=[1, 2]),
        ])
        images = [ImageData(path=f"/tmp/img_{i}.jpg") for i in range(3)]
        with patch("app.photobook.generate.call_ollama", return_value=None):
            pages = generate_photobook_pages(plan, images, None, None, model="test")
        assert len(pages) == 2
        assert pages[0].template_id == "cover_hero"
        assert pages[1].template_id == "double_stacked"

    def test_generate_includes_titles_and_captions(self):
        """LLM-Response mit 'title' und 'text' Feldern muss korrekt geparst werden."""
        plan = PhotobookPlan(pages=[PagePlan(position=0, preset_id="cover_hero", image_indices=[0])])
        images = [ImageData(path=f"/tmp/img_{i}.jpg") for i in range(1)]
        mock_content = json.dumps([
            {"preset_id": "cover_hero", "slots": [
                {"slot_id": "main", "image_index": 0},
                {"slot_id": "title", "text": "Aufbruch"},
            ]}
        ])
        with patch("app.photobook.generate.call_ollama", return_value=mock_content):
            pages = generate_photobook_pages(plan, images, None, None, model="test")
        assert len(pages) == 1
        title_slot = next((s for s in pages[0].slots if s.slot_id == "title"), None)
        assert title_slot is not None
        assert title_slot.text == "Aufbruch"

    def test_fallback_unknown_preset_uses_fallback_count(self):
        """Fallback mit unbekanntem Preset wählt passendes nach Bildanzahl."""
        plan = PhotobookPlan(pages=[PagePlan(position=0, preset_id="nonexistent", image_indices=[0, 1])])
        images = [ImageData(path=f"/tmp/img_{i}.jpg") for i in range(2)]
        with patch("app.photobook.generate.call_ollama", return_value=None):
            pages = generate_photobook_pages(plan, images, None, None, model="test")
        assert len(pages) == 1
        assert pages[0].template_id != "nonexistent"
        from app.photobook.preset_loader import load_preset
        preset = load_preset(pages[0].template_id)
        assert preset.image_count == 2
