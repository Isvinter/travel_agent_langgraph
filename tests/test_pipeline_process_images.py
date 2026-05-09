"""Tests für app/pipeline/process_images.py — enrich_images_with_metadata."""
from unittest.mock import patch
from app.pipeline.process_images import enrich_images_with_metadata
from app.state import AppState, ImageData


class TestEnrichImagesWithMetadata:
    def test_enriches_all_images_in_state(self):
        images = [
            ImageData(path="a.jpg"),
            ImageData(path="b.jpg"),
            ImageData(path="c.jpg"),
        ]
        state = AppState(images=images)

        mock_results = [
            {"timestamp": "2024-07-15T10:00:00", "latitude": 47.0, "longitude": 8.0},
            {"timestamp": "2024-07-15T11:00:00", "latitude": 47.1, "longitude": 8.1},
            {"timestamp": None, "latitude": None, "longitude": None},
        ]

        with patch("app.pipeline.process_images.extract_metadata",
                   side_effect=mock_results) as mock_extract:
            enrich_images_with_metadata(state)
            assert mock_extract.call_count == 3
            assert state.images[0].timestamp == "2024-07-15T10:00:00"
            assert state.images[0].latitude == 47.0
            assert state.images[1].timestamp == "2024-07-15T11:00:00"
            assert state.images[2].timestamp is None

    def test_handles_extraction_failure(self):
        images = [ImageData(path="broken.jpg")]
        state = AppState(images=images)
        with patch("app.pipeline.process_images.extract_metadata",
                   side_effect=OSError("Cannot read file")):
            enrich_images_with_metadata(state)
        # Testet dass der Node nicht crasht — die Node-Ebene fängt das via try/except
        assert state.images[0].path == "broken.jpg"
        assert state.images[0].timestamp is None

    def test_empty_images_list(self):
        state = AppState(images=[])
        enrich_images_with_metadata(state)
        assert state.images == []

    def test_metadata_with_german_umlauts_path(self):
        images = [ImageData(path="/data/Schönau.jpg")]
        state = AppState(images=images)
        with patch("app.pipeline.process_images.extract_metadata",
                   return_value={"timestamp": None, "latitude": 47.0, "longitude": 8.0}):
            enrich_images_with_metadata(state)
            assert state.images[0].latitude == 47.0
            assert "Schönau" in state.images[0].path
