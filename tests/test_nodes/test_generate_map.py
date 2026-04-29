"""Tests for app/nodes/generate_map.py"""
from unittest.mock import patch
from app.nodes.generate_map import generate_map_image_node
from app.state import AppState
from app.services.gpx_analytics import TrackPoint, GPXStats


class TestGenerateMapImageNode:
    def test_skips_when_no_gpx_stats(self):
        state = AppState(gpx_stats=None)
        result = generate_map_image_node(state)
        assert "map_image_path" not in result.metadata

    def test_generates_map_with_mocked_services(self):
        points = [TrackPoint(lat=47.0, lon=8.0, elevation=500.0, time=None)]
        stats = GPXStats(
            total_distance_m=1000,
            elevation_gain_m=100,
            elevation_loss_m=50,
            avg_speed_kmh=5.0,
            max_speed_kmh=10.0,
            points=points,
        )
        state = AppState(gpx_stats=stats)
        with patch("app.nodes.generate_map.generate_map_html") as mock_html, \
             patch("app.nodes.generate_map.html_to_png") as mock_png, \
             patch("os.makedirs"):
            result = generate_map_image_node(state)
            mock_html.assert_called_once()
            mock_png.assert_called_once()
            assert "map_image_path" in result.metadata
