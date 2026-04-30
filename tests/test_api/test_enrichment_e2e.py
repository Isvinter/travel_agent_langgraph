"""End-to-end test for enrichment pipeline with mocked network."""
import json
from unittest.mock import patch, Mock

from app.graph import build_graph
from app.state import AppState, ImageData
from app.services.gpx_analytics import TrackPoint, GPXStats
from datetime import datetime


def build_valid_state():
    """Hilfsfunktion: Baut einen AppState mit GPX-Daten und Bildern."""
    points = [
        TrackPoint(lat=47.3, lon=11.4, elevation=800.0,
                   time=datetime(2025, 6, 1, 10, 0)),
        TrackPoint(lat=47.31, lon=11.41, elevation=900.0,
                   time=datetime(2025, 6, 1, 14, 0)),
    ]
    stats = GPXStats(
        total_distance_m=5000, elevation_gain_m=300, elevation_loss_m=200,
        avg_speed_kmh=3.5, max_speed_kmh=7.0, points=points,
    )
    return AppState(
        gpx_stats=stats,
        gpx_pauses=[{
            "start_time": datetime(2025, 6, 1, 12, 0),
            "end_time": datetime(2025, 6, 1, 12, 30),
            "duration_minutes": 30.0,
            "location": {"lat": 47.305, "lon": 11.405},
        }],
        images=[ImageData(path=f"img{i}.jpg") for i in range(5)],
        notes="A great day out.",
        model="gemma4:26b-ctx128k",
    )


class TestEnrichmentE2E:
    def test_full_pipeline_with_mocked_network(self):
        """End-to-end test: pipeline läuft mit allen 11 Knoten durch."""
        state = build_valid_state()

        # Mock: Open-Meteo weather response
        mock_weather_resp = Mock()
        mock_weather_resp.status_code = 200
        mock_weather_resp.json.return_value = {
            "daily": {
                "time": ["2025-06-01"],
                "temperature_2m_max": [21.0],
                "temperature_2m_min": [11.0],
                "precipitation_sum": [0.0],
                "precipitation_hours": [0.0],
                "weather_code": [1],
                "wind_speed_10m_max": [12.0],
                "cloud_cover_mean": [25.0],
            }
        }

        # Mock: Overpass POI response
        mock_overpass_resp = Mock()
        mock_overpass_resp.status_code = 200
        mock_overpass_resp.json.return_value = {
            "elements": []
        }

        # Mock: Ollama review response
        mock_review_resp = Mock()
        mock_review_resp.status_code = 200
        mock_review_resp.json.return_value = {
            "message": {"content": json.dumps({
                "pois": [],
                "weather_summary": "A beautiful sunny day in the Alps.",
                "discarded_weather_fields": [],
                "image_ratings": {f"img{i}.jpg": 4 for i in range(5)},
                "coherence_score": 8,
                "flags": [],
            })},
        }

        with patch("app.nodes.extract_metadata.enrich_images_with_metadata"), \
             patch("app.nodes.clustering_image_node.cluster_images", return_value=[]), \
             patch("app.nodes.generate_map.generate_map_html"), \
             patch("app.nodes.generate_map.html_to_png"), \
             patch("app.nodes.select_images_node.select_images_for_blog",
                   return_value=[]), \
             patch("app.services.weather_enricher.requests.get",
                   return_value=mock_weather_resp), \
             patch("app.services.poi_enricher.requests.post",
                   return_value=mock_overpass_resp), \
             patch("app.services.content_reviewer.requests.post",
                   return_value=mock_review_resp), \
             patch("app.services.blog_generator.call_ollama_multimodal",
                   return_value="# Test Blog\n\nThis is a test blog post."):
            graph = build_graph()
            result = graph.invoke(state)

        # Verify state was enriched
        assert result["weather"] is not None
        assert result["enrichment_context"].get("weather_summary") == "A beautiful sunny day in the Alps."
        assert result["enrichment_context"].get("coherence_score") == 8
        # Blog generation should have run
        assert result["blog_post"] is not None

    def test_pipeline_survives_weather_failure(self):
        """Pipeline sollte weiterlaufen, auch wenn der Wetterdienst ausfällt."""
        state = build_valid_state()

        mock_overpass_resp = Mock()
        mock_overpass_resp.status_code = 200
        mock_overpass_resp.json.return_value = {"elements": []}

        mock_review_resp = Mock()
        mock_review_resp.status_code = 200
        mock_review_resp.json.return_value = {
            "message": {"content": json.dumps({
                "pois": [],
                "weather_summary": "No weather data available.",
                "discarded_weather_fields": [],
                "image_ratings": {},
                "coherence_score": 5,
                "flags": [],
            })},
        }

        with patch("app.nodes.extract_metadata.enrich_images_with_metadata"), \
             patch("app.nodes.clustering_image_node.cluster_images", return_value=[]), \
             patch("app.nodes.generate_map.generate_map_html"), \
             patch("app.nodes.generate_map.html_to_png"), \
             patch("app.nodes.select_images_node.select_images_for_blog",
                   return_value=[]), \
             patch("app.services.weather_enricher.requests.get",
                   side_effect=Exception("Connection refused")), \
             patch("app.services.poi_enricher.requests.post",
                   return_value=mock_overpass_resp), \
             patch("app.services.content_reviewer.requests.post",
                   return_value=mock_review_resp), \
             patch("app.services.blog_generator.call_ollama_multimodal",
                   return_value="# Test Blog\n\nWeather was unavailable."):
            graph = build_graph()
            result = graph.invoke(state)

        # Weather should be None (failed), but pipeline continues
        assert result["weather"] is None
        # Blog post should still be generated
        assert result["blog_post"] is not None
