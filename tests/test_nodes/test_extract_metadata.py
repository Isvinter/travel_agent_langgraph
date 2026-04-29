"""Tests for app/nodes/extract_metadata.py"""
from unittest.mock import patch
from app.nodes.extract_metadata import metadata_node
from app.state import AppState, ImageData


class TestMetadataNode:
    def test_calls_enrich_images(self):
        images = [ImageData(path="a.jpg")]
        state = AppState(images=images)
        with patch("app.nodes.extract_metadata.enrich_images_with_metadata") as mock_enrich:
            result = metadata_node(state)
            mock_enrich.assert_called_once_with(state)
