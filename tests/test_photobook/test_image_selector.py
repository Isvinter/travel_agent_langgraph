"""Tests fuer die Fotobuch-Bildauswahl."""
from unittest.mock import patch, MagicMock
from app.state import ImageData
from app.photobook.image_selector import select_photobook_images

SAMPLE_IMAGES = [ImageData(path=f"/tmp/img_{i}.jpg") for i in range(25)]


class TestImageSelector:
    @patch("app.photobook.image_selector.call_ollama")
    @patch("app.photobook.image_selector.encode_image_base64")
    def test_selects_correct_count(self, mock_encode, mock_call):
        mock_encode.return_value = "fake_base64_data"
        mock_call.return_value = "0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15"
        result = select_photobook_images(
            images=SAMPLE_IMAGES,
            tour_summary="Test Tour mit 5km Wanderung",
            model="test-model",
            photo_count=16,
        )
        assert len(result) == 16

    @patch("app.photobook.image_selector.call_ollama")
    @patch("app.photobook.image_selector.encode_image_base64")
    def test_fallback_when_llm_fails(self, mock_encode, mock_call):
        mock_encode.return_value = "fake_base64_data"
        mock_call.return_value = None
        result = select_photobook_images(
            images=SAMPLE_IMAGES[:10],
            tour_summary=None,
            model="test-model",
            photo_count=8,
        )
        assert len(result) == 8

    def test_returns_all_when_fewer_images(self):
        result = select_photobook_images(
            images=SAMPLE_IMAGES[:3],
            tour_summary=None,
            model="test-model",
            photo_count=16,
        )
        assert len(result) == 3
