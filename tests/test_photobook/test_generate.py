"""Tests fuer LLM Pass 2: Slot-Zuweisung mit Preset-Constraints."""
import json
from unittest.mock import patch, MagicMock
from app.state import ImageData, PageDescription
from app.photobook.generate import generate_photobook_pages

MOCK_PLAN = {
    "pages": [
        {"position": 0, "preset_id": "cover_hero", "image_indices": [0], "purpose": "Cover"},
        {"position": 1, "preset_id": "double_equal", "image_indices": [1, 2], "purpose": "Aufstieg"},
    ]
}

MOCK_GENERATE_RESPONSE = {
    "message": {
        "content": json.dumps([
            {"preset_id": "cover_hero", "slots": [
                {"slot_id": "main", "image_index": 0},
                {"slot_id": "title", "text": "Gipfelblick"},
            ]},
            {"preset_id": "double_equal", "slots": [
                {"slot_id": "left", "image_index": 1},
                {"slot_id": "right", "image_index": 2},
            ]},
        ])
    }
}

SAMPLE_IMAGES = [ImageData(path=f"/tmp/img_{i}.jpg") for i in range(16)]


class TestGenerate:
    @patch("app.photobook.generate.requests.post")
    def test_generate_returns_page_descriptions(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = MOCK_GENERATE_RESPONSE
        mock_post.return_value = mock_resp
        result = generate_photobook_pages(
            plan=MOCK_PLAN, images=SAMPLE_IMAGES, gpx_stats={}, notes="Test", model="test-model",
        )
        assert len(result) == 2
        assert isinstance(result[0], PageDescription)
        assert result[0].template_id == "cover_hero"
        assert result[1].template_id == "double_equal"

    def test_fallback_on_empty_plan(self):
        result = generate_photobook_pages(
            plan={"pages": []}, images=SAMPLE_IMAGES[:4], gpx_stats={}, notes=None, model="test-model",
        )
        assert len(result) == 0

    @patch("app.photobook.generate.requests.post")
    def test_generate_handles_missing_images(self, mock_post):
        bad_response = {
            "message": {"content": json.dumps([
                {"preset_id": "cover_hero", "slots": [{"slot_id": "main", "image_index": 999}]},
            ])}
        }
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = bad_response
        mock_post.return_value = mock_resp
        result = generate_photobook_pages(
            plan=MOCK_PLAN, images=SAMPLE_IMAGES[:3], gpx_stats={}, notes="Test", model="test-model",
        )
        assert len(result) >= 0

    def test_fallback_uses_preset_from_plan(self):
        """Fallback soll das im Plan gewählte Preset respektieren."""
        plan = {
            "pages": [
                {"position": 0, "preset_id": "cover_hero", "image_indices": [0]},
                {"position": 1, "preset_id": "double_equal", "image_indices": [1, 2]},
            ]
        }
        images = [ImageData(path=f"/tmp/img_{i}.jpg") for i in range(3)]
        with patch("app.photobook.generate.requests.post", side_effect=Exception("LLM down")):
            pages = generate_photobook_pages(plan, images, None, None, model="test")
        assert len(pages) == 2
        assert pages[0].template_id == "cover_hero"
        assert pages[1].template_id == "double_equal"

    def test_generate_includes_titles_and_captions(self):
        """LLM-Response mit 'title' und 'text' Feldern muss korrekt geparst werden."""
        plan = {"pages": [{"position": 0, "preset_id": "cover_hero", "image_indices": [0]}]}
        images = [ImageData(path=f"/tmp/img_{i}.jpg") for i in range(1)]
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "message": {"content": json.dumps([
                {"preset_id": "cover_hero", "slots": [
                    {"slot_id": "main", "image_index": 0},
                    {"slot_id": "title", "text": "Aufbruch"},
                ]}
            ])}
        }
        with patch("app.photobook.generate.requests.post", return_value=mock_resp):
            pages = generate_photobook_pages(plan, images, None, None, model="test")
        assert len(pages) == 1
        title_slot = next((s for s in pages[0].slots if s.get("slot_id") == "title"), None)
        assert title_slot is not None
        assert title_slot["text"] == "Aufbruch"

    def test_fallback_unknown_preset_uses_fallback_count(self):
        """Fallback mit unbekanntem Preset wählt passendes nach Bildanzahl."""
        plan = {"pages": [{"position": 0, "preset_id": "nonexistent", "image_indices": [0, 1]}]}
        images = [ImageData(path=f"/tmp/img_{i}.jpg") for i in range(2)]
        with patch("app.photobook.generate.requests.post", side_effect=Exception("LLM down")):
            pages = generate_photobook_pages(plan, images, None, None, model="test")
        assert len(pages) == 1
        assert pages[0].template_id != "nonexistent"
        # Sollte ein 2-Bild-Preset sein
        from app.photobook.preset_loader import load_preset
        preset = load_preset(pages[0].template_id)
        assert preset.image_count == 2
