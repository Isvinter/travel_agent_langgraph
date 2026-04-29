"""Tests for app/nodes/generate_blogpost.py"""
from unittest.mock import patch
from app.nodes.generate_blogpost import generate_blog_post_node
from app.state import AppState, ImageData
from app.services.gpx_analytics import TrackPoint, GPXStats


class TestGenerateBlogPostNode:
    def test_skips_when_no_images(self):
        state = AppState(images=[], gpx_stats=None)
        result = generate_blog_post_node(state)
        assert result.blog_post == {"success": False, "error": "No images"}

    def test_skips_when_no_gpx_stats(self):
        state = AppState(
            images=[ImageData(path="a.jpg")],
            gpx_stats=None,
        )
        result = generate_blog_post_node(state)
        assert result.blog_post == {"success": False, "error": "No GPX stats"}

    def test_generates_blog_with_mocked_service(self):
        points = [TrackPoint(lat=47.0, lon=8.0, elevation=500.0, time=None)]
        stats = GPXStats(
            total_distance_m=1000,
            elevation_gain_m=100,
            elevation_loss_m=50,
            avg_speed_kmh=5.0,
            max_speed_kmh=10.0,
            points=points,
        )
        images = [ImageData(path="a.jpg")]
        state = AppState(images=images, selected_images=images, gpx_stats=stats)
        mock_result = {
            "success": True,
            "markdown": "# Test Blog",
            "html": "<h1>Test Blog</h1>",
            "selected_images": [],
            "descriptions": {},
        }
        with patch("app.nodes.generate_blogpost.generate_blog_post", return_value=mock_result):
            result = generate_blog_post_node(state)
            assert result.blog_post["success"] is True
            assert "markdown" in result.blog_post
