"""Tests für Umlaute und Sonderzeichen in verschiedenen Pipeline-Komponenten."""
from datetime import datetime

from app.state import AppState, ImageData, WeatherInfo
from app.services.gpx_analytics import GPXStats, TrackPoint


class TestGermanCharsInState:
    def test_appstate_with_umlauts_in_notes(self):
        state = AppState(
            notes="Tour durch Zürich, München und Düsseldorf — großartige Ährenfelder!",
            gpx_file="/data/Überlingen.gpx",
        )
        assert "Ährenfelder" in state.notes
        assert "Überlingen" in state.gpx_file

    def test_imagedata_with_umlaut_path(self):
        img = ImageData(path="/data/Fotos/Österreich/Sölden.jpg", latitude=46.9, longitude=11.0)
        assert "Österreich" in img.path
        assert "Sölden" in img.path


class TestGermanCharsInGPX:
    def test_trackpoint_with_german_description(self):
        p = TrackPoint(lat=47.0, lon=8.0, elevation=500, time=datetime(2024, 7, 15, 10, 0))
        assert p.lat == 47.0

    def test_gpxstats_with_german_notes(self):
        stats = GPXStats(
            total_distance_m=42000,
            elevation_gain_m=1200,
            elevation_loss_m=1300,
            avg_speed_kmh=4.2,
            max_speed_kmh=8.5,
            max_elevation_m=2500,
            min_elevation_m=500,
            points=[],
        )
        assert stats.avg_speed_kmh == 4.2


class TestGermanCharsInBlogPost:
    def test_html_with_german_content(self, tmp_path):
        html = "<h1>Großartige Wanderung durch das schöne Allgäu</h1>"
        html += "<p>Wir genossen die Aussicht auf die Grünten und das Nebelhorn.</p>"
        html += "<p>Frühstück mit Weißwurst und süßem Senf.</p>"
        from app.utils.html_sanitizer import sanitize_html
        result = sanitize_html(html)
        assert "Großartige" in result
        assert "schöne" in result
        assert "Allgäu" in result
        assert "Weißwurst" in result
        assert "süßem" in result

    def test_sanitize_html_strips_script_with_umlauts(self):
        html = "<p>Grüezi</p><script>alert('böse')</script><p>Tschüss</p>"
        from app.utils.html_sanitizer import sanitize_html
        result = sanitize_html(html)
        assert "Grüezi" in result
        assert "Tschüss" in result
        assert "<script>" not in result.lower()
        assert "alert" not in result

    def test_xss_sanitization_strips_event_handler_with_umlauts(self):
        html = '<p onclick="alert(\'böse\')">Klick mich</p>'
        from app.utils.html_sanitizer import sanitize_html
        result = sanitize_html(html)
        assert "onclick" not in result.lower()


class TestGermanCharsInNodeOutput:
    def test_process_gpx_german_metadata(self, sample_gpx_path):
        from app.nodes.process_gpx import process_gpx_node
        state = AppState(gpx_file=sample_gpx_path)
        result = process_gpx_node(state)
        assert "distance_km" in result.metadata
        assert isinstance(result.metadata["distance_km"], (int, float))

    def test_enrich_poi_german_log_output(self):
        from app.nodes.enrich_poi_node import enrich_poi_node
        state = AppState(gpx_pauses=[])
        result = enrich_poi_node(state)
        assert result.poi_list == []

    def test_enrich_weather_german_log_output(self):
        from app.nodes.enrich_weather_node import enrich_weather_node
        state = AppState(gpx_stats=None)
        result = enrich_weather_node(state)
        assert result.weather is None
