"""Tests for app/nodes/enrich_weather_node.py"""
from unittest.mock import patch
from app.nodes.enrich_weather_node import enrich_weather_node
from app.state import AppState, DailyWeather, WeatherInfo


class TestEnrichWeatherNode:
    def test_skips_when_no_gpx_stats(self):
        state = AppState(gpx_stats=None)
        result = enrich_weather_node(state)
        assert result.weather is None

    def test_enriches_weather_from_gpx_stats(self):
        from app.services.gpx_analytics import TrackPoint, GPXStats
        from datetime import datetime

        points = [
            TrackPoint(lat=47.3, lon=11.4, elevation=800.0,
                       time=datetime(2025, 6, 1, 10, 0)),
        ]
        stats = GPXStats(
            total_distance_m=5000, elevation_gain_m=200, elevation_loss_m=100,
            avg_speed_kmh=4.0, max_speed_kmh=8.0, points=points,
        )
        state = AppState(gpx_stats=stats, gpx_pauses=[])

        mock_weather = WeatherInfo(
            daily=[
                DailyWeather(
                    date="2025-06-01", temperature_max=20.0, temperature_min=10.0,
                    precipitation_mm=0.0, precipitation_hours=0.0,
                    freezing_level_m=2500.0, weather_code=1, wind_speed_kmh=10.0,
                    cloud_cover_pct=30.0,
                )
            ],
            source="open-meteo",
        )

        with patch(
            "app.nodes.enrich_weather_node.fetch_historical_weather",
            return_value=mock_weather,
        ):
            result = enrich_weather_node(state)
            assert result.weather is not None
            assert result.weather.source == "open-meteo"
            assert len(result.weather.daily) == 1
            assert result.weather.daily[0].temperature_max == 20.0
