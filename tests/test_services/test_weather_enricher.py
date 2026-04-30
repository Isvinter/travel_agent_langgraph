"""Tests for app/services/weather_enricher.py"""
import json
from unittest.mock import patch, Mock
from datetime import datetime

import pytest

from app.services.weather_enricher import (
    fetch_historical_weather,
    _build_openmeteo_url,
    _estimate_freezing_level,
    _aggregate_weather_results,
)
from app.services.gpx_analytics import TrackPoint
from app.state import DailyWeather, WeatherInfo


class TestBuildOpenMeteoUrl:
    @pytest.mark.unit
    def test_builds_correct_url(self):
        url = _build_openmeteo_url(
            latitude=47.3,
            longitude=11.4,
            start_date="2025-06-01",
            end_date="2025-06-03",
        )
        assert "archive-api.open-meteo.com" in url
        assert "latitude=47.3" in url
        assert "longitude=11.4" in url
        assert "start_date=2025-06-01" in url
        assert "end_date=2025-06-03" in url
        assert "precipitation_hours" in url
        assert "temperature_2m_min" in url


class TestEstimateFreezingLevel:
    @pytest.mark.unit
    def test_estimates_from_elevation_and_temp(self):
        # Track median elevation 1000m, min temp 5°C
        # freezing_level ≈ 1000 + 5/0.0065 ≈ 1769m
        result = _estimate_freezing_level(median_elevation=1000.0, temperature_min=5.0)
        assert result is not None
        assert 1500 < result < 2000

    @pytest.mark.unit
    def test_returns_none_without_elevation(self):
        result = _estimate_freezing_level(median_elevation=None, temperature_min=5.0)
        assert result is None

    @pytest.mark.unit
    def test_clamps_to_sensible_range(self):
        # Very hot day: clamped to 0 minimum
        result = _estimate_freezing_level(median_elevation=100.0, temperature_min=35.0)
        assert result is not None
        assert result <= 10000  # Should not be absurd


class TestAggregateWeatherResults:
    @pytest.mark.unit
    def test_aggregates_two_locations(self):
        daily_a = {"temperature_2m_max": [20, 22], "temperature_2m_min": [10, 12],
                    "precipitation_sum": [0, 5], "precipitation_hours": [0, 2],
                    "weather_code": [1, 2], "wind_speed_10m_max": [10, 15],
                    "cloud_cover_mean": [30, 60]}
        daily_b = {"temperature_2m_max": [22, 24], "temperature_2m_min": [12, 14],
                    "precipitation_sum": [0, 3], "precipitation_hours": [0, 1],
                    "weather_code": [1, 3], "wind_speed_10m_max": [12, 18],
                    "cloud_cover_mean": [40, 70]}
        dates = ["2025-06-01", "2025-06-02"]
        result = _aggregate_weather_results(
            [daily_a, daily_b], dates, median_elevation=800.0
        )
        assert isinstance(result, WeatherInfo)
        assert len(result.daily) == 2
        # Day 1: median temp max of [20, 22, 22, 24] = 22
        assert result.daily[0].temperature_max == 22.0
        # Day 2 has precipitation: max of 5 and 3 = 5
        assert result.daily[1].precipitation_mm == 5.0


class TestFetchHistoricalWeather:
    @pytest.fixture
    def track_points(self):
        return [
            TrackPoint(lat=47.3, lon=11.4, elevation=800.0,
                       time=datetime(2025, 6, 1, 10, 0)),
            TrackPoint(lat=47.31, lon=11.41, elevation=850.0,
                       time=datetime(2025, 6, 3, 16, 0)),
        ]

    @pytest.fixture
    def openmeteo_response(self):
        return {
            "daily": {
                "time": ["2025-06-01", "2025-06-02", "2025-06-03"],
                "temperature_2m_max": [20.0, 22.0, 21.0],
                "temperature_2m_min": [10.0, 12.0, 11.0],
                "precipitation_sum": [0.0, 5.0, 0.0],
                "precipitation_hours": [0.0, 2.0, 0.0],
                "weather_code": [1, 2, 1],
                "wind_speed_10m_max": [10.0, 15.0, 12.0],
                "cloud_cover_mean": [30.0, 60.0, 40.0],
            }
        }

    @pytest.mark.unit
    def test_returns_weather_info(self, track_points, openmeteo_response):
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = openmeteo_response

        with patch("app.services.weather_enricher.requests.get", return_value=mock_resp):
            result = fetch_historical_weather(
                track_points=track_points,
                pauses=[],
            )
        assert isinstance(result, WeatherInfo)
        assert len(result.daily) == 3
        assert result.source == "open-meteo"
        # freezing level should be estimated
        assert result.daily[0].freezing_level_m is not None

    @pytest.mark.unit
    def test_handles_api_failure_gracefully(self, track_points):
        with patch("app.services.weather_enricher.requests.get",
                   side_effect=Exception("Connection refused")):
            result = fetch_historical_weather(
                track_points=track_points,
                pauses=[],
            )
        assert result is None

    @pytest.mark.unit
    def test_handles_non_200_response(self, track_points):
        mock_resp = Mock()
        mock_resp.status_code = 500
        with patch("app.services.weather_enricher.requests.get", return_value=mock_resp):
            result = fetch_historical_weather(
                track_points=track_points,
                pauses=[],
            )
        assert result is None

    @pytest.mark.unit
    def test_includes_pause_locations(self, track_points, openmeteo_response):
        pauses = [
            {"location": {"lat": 47.305, "lon": 11.405},
             "start_time": datetime(2025, 6, 2, 12, 0),
             "end_time": datetime(2025, 6, 2, 12, 30)}
        ]
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = openmeteo_response
        with patch("app.services.weather_enricher.requests.get", return_value=mock_resp):
            result = fetch_historical_weather(
                track_points=track_points,
                pauses=pauses,
            )
        assert isinstance(result, WeatherInfo)

    @pytest.mark.unit
    def test_returns_none_without_coordinates(self):
        result = fetch_historical_weather(
            track_points=[],
            pauses=[],
        )
        assert result is None
