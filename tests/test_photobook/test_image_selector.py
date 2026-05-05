"""Tests fuer die Fotobuch-Bildauswahl."""
import json
from unittest.mock import patch, MagicMock
from app.state import ImageData
from app.photobook.image_selector import select_photobook_images

SAMPLE_IMAGES = [ImageData(path=f"/tmp/img_{i}.jpg") for i in range(25)]


class TestImageSelector:
    @patch("app.photobook.image_selector.requests.post")
    def test_selects_correct_count(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "message": {
                "content": json.dumps({"selected_indices": list(range(16))})
            }
        }
        mock_post.return_value = mock_resp
        result = select_photobook_images(
            images=SAMPLE_IMAGES,
            gpx_stats={"total_distance_m": 5000},
            notes="Test Tour",
            model="test-model",
            photo_count=16,
        )
        assert len(result) == 16

    @patch("app.photobook.image_selector.requests.post")
    def test_fallback_when_llm_fails(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_post.return_value = mock_resp
        result = select_photobook_images(
            images=SAMPLE_IMAGES[:10],
            gpx_stats={},
            notes=None,
            model="test-model",
            photo_count=8,
        )
        assert len(result) == 8

    def test_returns_all_when_fewer_images(self):
        result = select_photobook_images(
            images=SAMPLE_IMAGES[:3],
            gpx_stats={},
            notes=None,
            model="test-model",
            photo_count=16,
        )
        assert len(result) == 3
