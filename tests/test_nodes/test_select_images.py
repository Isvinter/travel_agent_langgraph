"""Tests for app/nodes/select_images_node.py"""
from unittest.mock import patch
from app.nodes.select_images_node import select_images_node
from app.state import AppState, ImageData


class TestSelectImagesNode:
    def test_selects_images_from_state(self):
        images = [ImageData(path=f"img{i}.jpg") for i in range(10)]
        state = AppState(images=images)
        mock_selected = [
            {"path": "img0.jpg"},
            {"path": "img3.jpg"},
            {"path": "img7.jpg"},
        ]
        with patch("app.nodes.select_images_node.select_images_for_blog", return_value=mock_selected):
            result = select_images_node(state)
            assert len(result.selected_images) == 3
            assert result.metadata.get("selected_image_count") == 3
