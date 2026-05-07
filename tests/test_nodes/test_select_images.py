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
            assert result.selected_images[0].path == "img0.jpg"

    def test_handles_empty_image_list(self):
        state = AppState(images=[])
        with patch("app.nodes.select_images_node.select_images_for_blog", return_value=[]) as mock_select:
            result = select_images_node(state)
            mock_select.assert_called_once()
            assert len(result.selected_images) == 0
            assert result.metadata["selected_image_count"] == 0

    def test_handles_selection_failure_fallback(self):
        images = [ImageData(path=f"img{i}.jpg") for i in range(10)]
        state = AppState(images=images)
        with patch("app.nodes.select_images_node.select_images_for_blog",
                   side_effect=RuntimeError("Ollama not available")):
            result = select_images_node(state)
            # Fallback: all images used
            assert len(result.selected_images) > 0
            assert result.metadata["selected_image_count"] > 0

    def test_ignores_llm_hallucinated_paths(self):
        images = [ImageData(path=f"img{i}.jpg") for i in range(5)]
        state = AppState(images=images)
        mock_selected = [
            {"path": "img0.jpg"},
            {"path": "img99.jpg"},  # Existiert nicht
            {"path": "img2.jpg"},
        ]
        with patch("app.nodes.select_images_node.select_images_for_blog", return_value=mock_selected):
            result = select_images_node(state)
            assert len(result.selected_images) == 2
            assert result.metadata["selected_image_count"] == 2

    def test_selection_caps_at_wildcard_max_no_oversampling(self):
        """Wenn weniger als wildcard_max Bilder da sind, wird nicht oversampled."""
        images = [ImageData(path=f"img{i}.jpg") for i in range(3)]
        state = AppState(images=images)
        mock_selected = [{"path": f"img{i}.jpg"} for i in range(3)]
        with patch("app.nodes.select_images_node.select_images_for_blog", return_value=mock_selected):
            result = select_images_node(state)
            assert len(result.selected_images) == 3
