"""Tests for app/state.py weather and enrichment models."""
import pytest
from pydantic import ValidationError
from app.state import DailyWeather, WeatherInfo, AppState


class TestDailyWeather:
    def test_creates_with_required_fields(self):
        dw = DailyWeather(
            date="2025-06-15",
            temperature_max=22.5,
            temperature_min=14.0,
            precipitation_mm=3.2,
            precipitation_hours=1.5,
            weather_code=2,
            wind_speed_kmh=15.0,
            cloud_cover_pct=60.0,
        )
        assert dw.freezing_level_m is None
        assert dw.temperature_max == 22.5

    def test_freezing_level_optional(self):
        dw = DailyWeather(
            date="2025-06-15",
            temperature_max=22.5,
            temperature_min=14.0,
            precipitation_mm=0.0,
            precipitation_hours=0.0,
            freezing_level_m=2800.0,
            weather_code=1,
            wind_speed_kmh=10.0,
            cloud_cover_pct=30.0,
        )
        assert dw.freezing_level_m == 2800.0

    def test_missing_required_raises(self):
        with pytest.raises(ValidationError):
            DailyWeather(date="2025-06-15")


class TestWeatherInfo:
    def test_defaults(self):
        wi = WeatherInfo(daily=[])
        assert wi.source == "open-meteo"
        assert wi.summary == ""


class TestAppStateEnrichment:
    def test_new_fields_have_defaults(self):
        state = AppState()
        assert state.weather is None
        assert state.poi_list == []
        assert state.enrichment_context == {}
