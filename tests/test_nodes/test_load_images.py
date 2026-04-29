"""Tests for app/nodes/load_images.py"""
from unittest.mock import patch
from app.nodes.load_images import load_images_node
from app.state import AppState, ImageData


class TestLoadImagesNode:
    def test_populates_state_images(self):
        mock_images = [ImageData(path="/tmp/a.jpg")]
        with patch("app.nodes.load_images.load_images_from_directory", return_value=mock_images):
            state = AppState(images=[])
            result = load_images_node(state)
            assert len(result.images) == 1
            assert result.images[0].path == "/tmp/a.jpg"
