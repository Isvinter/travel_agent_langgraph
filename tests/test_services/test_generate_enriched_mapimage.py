"""Tests for generate_enriched_map_html in app/services/generate_mapimage.py"""
import os
import pytest
from app.services.generate_mapimage import generate_enriched_map_html
from app.services.gpx_analytics import TrackPoint
from app.state import ImageData
from datetime import datetime


@pytest.fixture
def sample_points():
    return [
        TrackPoint(lat=47.3, lon=8.5, elevation=500.0, time=None),
        TrackPoint(lat=47.301, lon=8.501, elevation=510.0, time=None),
        TrackPoint(lat=47.302, lon=8.502, elevation=520.0, time=None),
    ]


@pytest.fixture
def sample_pauses():
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
    def test_contains_divicon_foto_labels(self, tmp_path, sample_points, sample_pauses, sample_images):
        html_path = str(tmp_path / "enriched_map.html")
        generate_enriched_map_html(sample_points, sample_pauses, sample_images, html_path)

        content = open(html_path).read()
        assert "Foto 1" in content
        assert "Foto 2" in content

    @pytest.mark.unit
    def test_no_tooltips_on_foto_markers(self, tmp_path, sample_points, sample_images):
        """Foto-Marker sollen keine Tooltips mehr haben."""
        html_path = str(tmp_path / "enriched_map.html")
        generate_enriched_map_html(sample_points, [], sample_images, html_path)

        content = open(html_path).read()
        assert "Bild 1:" not in content
        assert "Bild 2:" not in content

    @pytest.mark.unit
    def test_no_tooltips_on_pause_markers(self, tmp_path, sample_points, sample_pauses):
        """Pause-Marker sollen keine Tooltips mehr haben."""
        html_path = str(tmp_path / "enriched_map.html")
        generate_enriched_map_html(sample_points, sample_pauses, [], html_path)

        content = open(html_path).read()
        assert "Pause: 15.0 min" not in content
        assert "Pause: 25.0 min" not in content

    @pytest.mark.unit
    def test_pause_markers_use_divicon(self, tmp_path, sample_points, sample_pauses):
        html_path = str(tmp_path / "enriched_map.html")
        generate_enriched_map_html(sample_points, sample_pauses, [], html_path)

        content = open(html_path).read()
        assert "15min" in content or "15.0min" in content or "15 min" in content
        assert "25min" in content or "25.0min" in content or "25 min" in content

    @pytest.mark.unit
    def test_pause_with_matched_photos_shows_foto_labels(self, tmp_path, sample_points, sample_pauses):
        """Fotos die räumlich+zeitlich zur Pause passen -> Labels erscheinen beim Pause-Marker."""
        images_matching_pause1 = [
            ImageData(
                path="data/images/pause_photo.jpg",
                timestamp="2024-07-15T10:05:00",
                latitude=47.301,
                longitude=8.501,
            ),
        ]
        html_path = str(tmp_path / "enriched_map.html")
        generate_enriched_map_html(sample_points, sample_pauses, images_matching_pause1, html_path)

        content = open(html_path).read()
        assert "Foto 1" in content  # singular for single matched photo at pause

    @pytest.mark.unit
    def test_handles_empty_pauses(self, tmp_path, sample_points, sample_images):
        html_path = str(tmp_path / "enriched_map.html")
        generate_enriched_map_html(sample_points, [], sample_images, html_path)

        assert os.path.exists(html_path)
        content = open(html_path).read()
        assert "Foto 1" in content

    @pytest.mark.unit
    def test_handles_empty_images(self, tmp_path, sample_points, sample_pauses):
        html_path = str(tmp_path / "enriched_map.html")
        generate_enriched_map_html(sample_points, sample_pauses, [], html_path)

        assert os.path.exists(html_path)
        content = open(html_path).read()
        assert "Foto" not in content

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

    @pytest.mark.unit
    def test_start_end_no_tooltips(self, tmp_path, sample_points):
        """Start/End-Marker sollen keine Tooltips mehr haben."""
        html_path = str(tmp_path / "enriched_map.html")
        generate_enriched_map_html(sample_points, [], [], html_path)

        content = open(html_path).read()
        assert '"Start"' not in content
        assert '"Ende"' not in content

    @pytest.mark.unit
    def test_groups_nearby_photos(self, tmp_path, sample_points):
        """Fotos an gleicher Position werden gruppiert."""
        images = [
            ImageData(
                path="data/images/a.jpg",
                timestamp="2024-07-15T10:00:00",
                latitude=47.3005,
                longitude=8.5005,
            ),
            ImageData(
                path="data/images/b.jpg",
                timestamp="2024-07-15T10:01:00",
                latitude=47.3005,
                longitude=8.5005,
            ),
        ]
        html_path = str(tmp_path / "enriched_map.html")
        generate_enriched_map_html(sample_points, [], images, html_path)

        content = open(html_path).read()
        assert "Fotos 1, 2" in content
        assert "<b>Foto 1</b>" not in content
        assert "<b>Foto 2</b>" not in content
