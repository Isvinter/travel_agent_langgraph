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

    def test_handles_enrichment_failure(self):
        images = [ImageData(path="a.jpg")]
        state = AppState(images=images)
        with patch("app.nodes.extract_metadata.enrich_images_with_metadata",
                   side_effect=RuntimeError("EXIF parsing failed")):
            result = metadata_node(state)
            assert result is state  # Rückgabe trotz Fehler

    def test_metadata_node_with_multiple_images(self):
        images = [ImageData(path=f"img{i}.jpg") for i in range(5)]
        state = AppState(images=images)
        with patch("app.nodes.extract_metadata.enrich_images_with_metadata") as mock_enrich:
            result = metadata_node(state)
            mock_enrich.assert_called_once_with(state)
            # State sollte die ursprünglichen Bilder behalten
            assert len(result.images) == 5

    def test_metadata_node_with_empty_images(self):
        state = AppState(images=[])
        with patch("app.nodes.extract_metadata.enrich_images_with_metadata") as mock_enrich:
            result = metadata_node(state)
            mock_enrich.assert_called_once_with(state)
            assert result.images == []
