"""Tests for app/nodes/generate_enriched_map.py"""
from unittest.mock import patch
from app.nodes.generate_enriched_map import generate_enriched_map_node
from app.state import AppState, ImageData
from app.services.gpx_analytics import TrackPoint, GPXStats
from datetime import datetime


class TestGenerateEnrichedMapNode:
    def test_skips_when_no_gpx_stats(self):
        state = AppState(gpx_stats=None)
        result = generate_enriched_map_node(state)
        assert "enriched_map_image_path" not in result.metadata

    def test_generates_enriched_map_with_mocked_services(self):
        points = [TrackPoint(lat=47.0, lon=8.0, elevation=500.0, time=None)]
        stats = GPXStats(
            total_distance_m=1000,
            elevation_gain_m=100,
            elevation_loss_m=50,
            avg_speed_kmh=5.0,
            max_speed_kmh=10.0,
            points=points,
        )
        pauses = [
            {
                "start_time": datetime(2024, 7, 15, 10, 0),
                "end_time": datetime(2024, 7, 15, 10, 15),
                "duration_minutes": 15.0,
                "location": {"lat": 47.001, "lon": 8.001},
            }
        ]
        images = [
            ImageData(
                path="data/images/photo.jpg",
                timestamp="2024-07-15T10:00:00",
                latitude=47.0005,
                longitude=8.0005,
            )
        ]

        state = AppState(
            gpx_stats=stats,
            gpx_pauses=pauses,
            selected_images=images,
        )

        with patch(
            "app.nodes.generate_enriched_map.generate_enriched_map_html"
        ) as mock_html, patch(
            "app.nodes.generate_enriched_map.html_to_png"
        ) as mock_png, patch(
            "os.makedirs"
        ):
            result = generate_enriched_map_node(state)

            mock_html.assert_called_once()
            mock_png.assert_called_once()
            assert "enriched_map_image_path" in result.metadata
            assert result.metadata["enriched_map_image_path"] == "output/enriched_map.png"
