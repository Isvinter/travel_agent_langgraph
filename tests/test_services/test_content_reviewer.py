"""Tests for app/services/content_reviewer.py"""
import json
from unittest.mock import patch, Mock

import pytest

from app.services.content_reviewer import (
    review_enrichment,
    _build_review_prompt,
    _parse_review_response,
)
from app.state import DailyWeather, WeatherInfo, ImageData


class TestBuildReviewPrompt:
    def test_includes_all_sections(self):
        weather = WeatherInfo(
            daily=[
                DailyWeather(
                    date="2025-06-01", temperature_max=20.0, temperature_min=10.0,
                    precipitation_mm=0.0, precipitation_hours=0.0,
                    freezing_level_m=2800.0, weather_code=1, wind_speed_kmh=10.0,
                    cloud_cover_pct=30.0,
                )
            ],
            summary="Sunny and mild",
        )
        pois = [{"name": "Berggipfel", "type": "peak", "distance_km": 1.0}]
        images = [ImageData(path="img1.jpg", timestamp="2025-06-01T10:00:00",
                            latitude=47.3, longitude=11.4)]

        prompt = _build_review_prompt(
            weather=weather,
            poi_list=pois,
            selected_images=images,
            gpx_stats_d=None,
            notes=None,
        )
        assert "Sunny and mild" in prompt
        assert "Berggipfel" in prompt
        assert "img1.jpg" in prompt
        assert "discard" in prompt.lower()

    def test_handles_none_weather(self):
        prompt = _build_review_prompt(
            weather=None,
            poi_list=[],
            selected_images=[],
            gpx_stats_d=None,
            notes=None,
        )
        assert "Keine Wetterdaten" in prompt
        assert "Keine POIs" in prompt
        assert "Keine Bilder" in prompt


class TestParseReviewResponse:
    def test_parses_valid_json(self):
        response = json.dumps({
            "pois": [{"name": "A", "action": "KEEP", "reason": "great view"}],
            "weather_summary": "Mild and sunny with alpine chill.",
            "discarded_weather_fields": ["freezing_level_m"],
            "image_ratings": {"img1.jpg": 4, "img2.jpg": 3},
            "coherence_score": 8,
            "flags": [],
        })
        result = _parse_review_response(response)
        assert result["kept_pois"] == [{"name": "A", "action": "KEEP", "reason": "great view"}]
        assert result["weather_summary"] == "Mild and sunny with alpine chill."
        assert result["discarded_weather_fields"] == ["freezing_level_m"]
        assert result["coherence_score"] == 8

    def test_fallback_for_invalid_json(self):
        response = "Here is my analysis: the weather was nice. KEEP Berggipfel."
        result = _parse_review_response(response)
        assert "weather_summary" in result
        assert result["weather_summary"] != ""

    def test_fallback_for_none(self):
        result = _parse_review_response(None)
        assert result["weather_summary"] == ""
        assert result["kept_pois"] == []
        assert result["coherence_score"] == 0


class TestReviewEnrichment:
    def test_returns_curated_context(self):
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
        pois = [{"name": "Berggipfel", "type": "peak", "distance_km": 1.0,
                 "wiki_extract": "A known peak"}]
        images = [ImageData(path="img1.jpg", timestamp="2025-06-01T10:00:00",
                            latitude=47.3, longitude=11.4)]

        review_json = json.dumps({
            "pois": [{"name": "Berggipfel", "action": "KEEP",
                      "reason": "relevant alpine POI"}],
            "weather_summary": "Mild with alpine clarity.",
            "discarded_weather_fields": ["freezing_level_m"],
            "image_ratings": {"img1.jpg": 4},
            "coherence_score": 7,
            "flags": [],
        })
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "message": {"content": review_json},
        }

        with patch("app.services.content_reviewer.requests.post",
                   return_value=mock_resp):
            result = review_enrichment(
                weather=weather,
                poi_list=pois,
                selected_images=images,
                gpx_stats=None,
                notes=None,
                model="gemma4:26b-ctx128k",
            )
        assert isinstance(result, dict)
        assert result.get("kept_pois") or result.get("weather_summary")

    def test_fallback_when_ollama_unavailable(self):
        weather = WeatherInfo(
            daily=[
                DailyWeather(
                    date="2025-06-01", temperature_max=20.0, temperature_min=10.0,
                    precipitation_mm=0.0, precipitation_hours=0.0,
                    weather_code=1, wind_speed_kmh=10.0, cloud_cover_pct=30.0,
                )
            ],
            summary="Sunny",
        )
        images = [ImageData(path="img1.jpg")]

        with patch("app.services.content_reviewer.requests.post",
                   side_effect=Exception("Connection refused")):
            result = review_enrichment(
                weather=weather,
                poi_list=[],
                selected_images=images,
                gpx_stats=None,
                notes=None,
                model="gemma4:26b-ctx128k",
            )
        assert isinstance(result, dict)
        assert "weather_summary" in result
        assert "kept_pois" in result
