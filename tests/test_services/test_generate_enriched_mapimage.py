"""Tests for generate_enriched_map_html in app/services/generate_mapimage.py"""
import os
import pytest
from app.services.generate_mapimage import generate_enriched_map_html
from app.services.gpx_analytics import TrackPoint
from app.state import ImageData


@pytest.fixture
def sample_points():
    return [
        TrackPoint(lat=47.3, lon=8.5, elevation=500.0, time=None),
        TrackPoint(lat=47.301, lon=8.501, elevation=510.0, time=None),
        TrackPoint(lat=47.302, lon=8.502, elevation=520.0, time=None),
    ]


@pytest.fixture
def sample_pauses():
    from datetime import datetime
    return [
        {
            "start_time": datetime(2024, 7, 15, 10, 0),
            "end_time": datetime(2024, 7, 15, 10, 15),
            "duration_minutes": 15.0,
            "location": {"lat": 47.301, "lon": 8.501},
        },
        {
            "start_time": datetime(2024, 7, 15, 12, 30),
            "end_time": datetime(2024, 7, 15, 12, 55),
            "duration_minutes": 25.0,
            "location": {"lat": 47.302, "lon": 8.502},
        },
    ]


@pytest.fixture
def sample_images():
    return [
        ImageData(
            path="data/images/photo_01.jpg",
            timestamp="2024-07-15T10:00:00",
            latitude=47.3005,
            longitude=8.5005,
        ),
        ImageData(
            path="data/images/photo_02.jpg",
            timestamp="2024-07-15T12:30:00",
            latitude=47.3015,
            longitude=8.5000,
        ),
    ]


class TestGenerateEnrichedMapHtml:
    @pytest.mark.unit
    def test_generates_html_file(self, tmp_path, sample_points, sample_pauses, sample_images):
        html_path = str(tmp_path / "enriched_map.html")
        generate_enriched_map_html(sample_points, sample_pauses, sample_images, html_path)

        assert os.path.exists(html_path)
        content = open(html_path).read()
        assert "folium" in content.lower() or "leaflet" in content.lower()

    @pytest.mark.unit
    def test_contains_pause_markers(self, tmp_path, sample_points, sample_pauses, sample_images):
        html_path = str(tmp_path / "enriched_map.html")
        generate_enriched_map_html(sample_points, sample_pauses, sample_images, html_path)

        content = open(html_path).read()
        assert "Pause: 15.0 min" in content
        assert "Pause: 25.0 min" in content

    @pytest.mark.unit
    def test_contains_image_markers(self, tmp_path, sample_points, sample_pauses, sample_images):
        html_path = str(tmp_path / "enriched_map.html")
        generate_enriched_map_html(sample_points, sample_pauses, sample_images, html_path)

        content = open(html_path).read()
        assert "Bild 1:" in content
        assert "Bild 2:" in content

    @pytest.mark.unit
    def test_handles_empty_pauses(self, tmp_path, sample_points, sample_images):
        html_path = str(tmp_path / "enriched_map.html")
        generate_enriched_map_html(sample_points, [], sample_images, html_path)

        assert os.path.exists(html_path)
        content = open(html_path).read()
        assert "Pause:" not in content  # keine Pausen-Marker

    @pytest.mark.unit
    def test_handles_empty_images(self, tmp_path, sample_points, sample_pauses):
        html_path = str(tmp_path / "enriched_map.html")
        generate_enriched_map_html(sample_points, sample_pauses, [], html_path)

        assert os.path.exists(html_path)
        content = open(html_path).read()
        assert "Bild" not in content  # keine Bild-Marker

    @pytest.mark.unit
    def test_handles_both_empty(self, tmp_path, sample_points):
        html_path = str(tmp_path / "enriched_map.html")
        generate_enriched_map_html(sample_points, [], [], html_path)

        assert os.path.exists(html_path)
        content = open(html_path).read()
        assert "folium" in content.lower() or "leaflet" in content.lower()

    @pytest.mark.unit
    def test_contains_route_polyline(self, tmp_path, sample_points):
        html_path = str(tmp_path / "enriched_map.html")
        generate_enriched_map_html(sample_points, [], [], html_path)

        content = open(html_path).read()
        assert "47.3" in content
        assert "47.302" in content
