"""Tests for app/nodes/review_content_node.py"""
from unittest.mock import patch
from app.nodes.review_content_node import review_content_node
from app.state import AppState, ImageData, DailyWeather, WeatherInfo
from app.services.gpx_analytics import TrackPoint, GPXStats


class TestReviewContentNode:
    def test_reviews_with_all_data(self):
        weather = WeatherInfo(
            daily=[
                DailyWeather(
                    date="2025-06-01", temperature_max=20.0, temperature_min=10.0,
                    precipitation_mm=0.0, precipitation_hours=0.0,
                    weather_code=1, wind_speed_kmh=10.0, cloud_cover_pct=30.0,
                )
            ],
            summary="Sunny and mild",
        )
        points = [TrackPoint(lat=47.3, lon=11.4, elevation=800.0, time=None)]
        stats = GPXStats(
            total_distance_m=5000, elevation_gain_m=200, elevation_loss_m=100,
            avg_speed_kmh=4.0, max_speed_kmh=8.0, points=points,
        )
        images = [ImageData(path="img1.jpg")]
        state = AppState(
            weather=weather,
            poi_list=[{"name": "Berggipfel", "type": "peak", "distance_km": 1.0}],
            selected_images=images,
            gpx_stats=stats,
            notes="Great hike!",
            model="gemma4:26b-ctx128k",
        )

        mock_context = {
            "kept_pois": [{"name": "Berggipfel", "action": "KEEP"}],
            "weather_summary": "Mild and sunny",
            "discarded_weather_fields": ["freezing_level_m"],
            "image_ratings": {"img1.jpg": 4},
            "coherence_score": 8,
            "flags": [],
        }
        with patch(
            "app.nodes.review_content_node.review_enrichment",
            return_value=mock_context,
        ):
            result = review_content_node(state)
            assert result.enrichment_context == mock_context
            assert result.enrichment_context["coherence_score"] == 8

    def test_works_with_minimal_data(self):
        state = AppState(
            weather=None,
            poi_list=[],
            selected_images=[],
            gpx_stats=None,
            model="gemma4:26b-ctx128k",
        )
        mock_context = {
            "kept_pois": [],
            "weather_summary": "",
            "discarded_weather_fields": [],
            "image_ratings": {},
            "coherence_score": 0,
            "flags": ["review_unavailable"],
        }
        with patch(
            "app.nodes.review_content_node.review_enrichment",
            return_value=mock_context,
        ):
            result = review_content_node(state)
            assert result.enrichment_context == mock_context
