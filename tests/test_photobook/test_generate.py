"""Tests fuer LLM Pass 2: Template-Auswahl + Captions."""
import json
from unittest.mock import patch, MagicMock
from app.state import ImageData, PageDescription
from app.photobook.generate import generate_photobook_pages

MOCK_PLAN = {
    "pages": [
        {"position": 0, "page_type": "cover", "template_category": "hero", "image_indices": [0], "purpose": "Cover"},
        {"position": 1, "page_type": "spread", "template_category": "split", "image_indices": [1, 2], "purpose": "Aufstieg"},
    ]
}

MOCK_GENERATE_RESPONSE = {
    "message": {
        "content": json.dumps([
            {"template_id": "hero_single", "page_type": "single", "slots": [{"slot_id": "main", "image_index": 0, "caption": "Gipfelblick"}]},
            {"template_id": "split_equal", "page_type": "spread", "slots": [
                {"slot_id": "left", "image_index": 1, "caption": "Waldweg"},
                {"slot_id": "right", "image_index": 2, "caption": "Aussichtspunkt"},
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
        assert result[0].template_id == "hero_single"
        assert result[1].template_id == "split_equal"

    def test_fallback_on_empty_plan(self):
        result = generate_photobook_pages(
            plan={"pages": []}, images=SAMPLE_IMAGES[:4], gpx_stats={}, notes=None, model="test-model",
        )
        assert len(result) == 0

    @patch("app.photobook.generate.requests.post")
    def test_generate_handles_missing_images(self, mock_post):
        bad_response = {
            "message": {"content": json.dumps([
                {"template_id": "hero_single", "page_type": "single", "slots": [{"slot_id": "main", "image_index": 999, "caption": "Bad index"}]},
            ])}
        }
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = bad_response
        mock_post.return_value = mock_resp
        result = generate_photobook_pages(
            plan=MOCK_PLAN, images=SAMPLE_IMAGES[:3], gpx_stats={}, notes="Test", model="test-model",
        )
        assert len(result) > 0

    def test_fallback_uses_plan_categories(self):
        """Fallback soll Template-Kategorien aus dem Plan respektieren, nicht alles grid_2x2."""
        plan = {
            "pages": [
                {"position": 0, "template_category": "hero", "image_indices": [0]},
                {"position": 1, "template_category": "split", "image_indices": [1, 2]},
            ]
        }
        images = [
            ImageData(path=f"/tmp/img_{i}.jpg") for i in range(3)
        ]
        # LLM simulieren der fehlschlägt → Fallback wird aktiviert
        with patch("app.photobook.generate.requests.post", side_effect=Exception("LLM down")):
            pages = generate_photobook_pages(plan, images, None, None, model="test")
        assert len(pages) == 2
        assert pages[0].template_id == "hero_single"
        assert pages[1].template_id == "split_equal"

    def test_generate_includes_titles_and_captions(self):
        """LLM-Response mit 'title' und 'caption' Feldern muss korrekt geparst werden."""
        plan = {"pages": [{"position": 0, "template_category": "hero", "image_indices": [0]}]}
        images = [ImageData(path=f"/tmp/img_{i}.jpg") for i in range(1)]
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "message": {"content": '[{"template_id": "hero_single", "page_type": "single", "title": "Aufbruch", "slots": [{"slot_id": "main", "image_index": 0, "caption": "Morgendlicher Start bei Sonnenaufgang"}]}]'}
        }
        with patch("app.photobook.generate.requests.post", return_value=mock_resp):
            pages = generate_photobook_pages(plan, images, None, None, model="test")
        assert len(pages) == 1
        title_slot = next((s for s in pages[0].slots if s.get("slot_id") == "title"), None)
        assert title_slot is not None
        assert title_slot["text"] == "Aufbruch"
        main_slot = next((s for s in pages[0].slots if s.get("slot_id") == "main"), None)
        assert main_slot is not None
        assert "Sonnenaufgang" in main_slot.get("caption", "")
