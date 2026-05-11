"""Tests fuer den Tour-Summary-Service."""
import pytest
from unittest.mock import patch
from app.services.summarize_context import summarize_context


class TestSummarizeContext:
    def test_returns_summary_when_llm_succeeds(self):
        with patch("app.services.summarize_context.call_ollama") as mock_call:
            mock_call.return_value = "Eine 14km Wanderung im Allgäu im Herbst. Familienausflug."
            result = summarize_context(
                notes="Schöne Herbsttour mit der Familie.",
                gpx_distance_km=14.3,
                gpx_elevation_m=520,
                preset="nature_outdoor",
                model="test-model",
            )
            assert result is not None
            assert "14" in result or "Wanderung" in result
            assert mock_call.called

    def test_fallback_when_llm_fails(self):
        with patch("app.services.summarize_context.call_ollama", return_value=None):
            result = summarize_context(
                notes="Beliebiger Text.",
                gpx_distance_km=14.3,
                gpx_elevation_m=520,
                preset="nature_outdoor",
                model="test-model",
            )
            assert result is not None
            assert "14.3" in result
            assert "km" in result

    def test_fallback_when_no_notes_no_gpx(self):
        result = summarize_context(
            notes=None,
            gpx_distance_km=None,
            gpx_elevation_m=None,
            preset="mixed",
            model="test-model",
        )
        assert result is not None
        # Minimal-Summary soll trotzdem nicht leer sein
        assert len(result) > 0

    def test_prompt_includes_tour_data(self):
        with patch("app.services.summarize_context.call_ollama") as mock_call:
            mock_call.return_value = "Test-Summary"
            summarize_context(
                notes="Lange Tour durch die Berge.",
                gpx_distance_km=25.0,
                gpx_elevation_m=1200,
                preset="nature_outdoor",
                model="test-model",
            )
            prompt = mock_call.call_args[0][0]
            assert "25.0" in prompt
            assert "1200" in prompt
            assert "Lange Tour" in prompt or "Berge" in prompt

    def test_prompt_handles_none_notes(self):
        with patch("app.services.summarize_context.call_ollama") as mock_call:
            mock_call.return_value = "Test-Summary"
            summarize_context(
                notes=None,
                gpx_distance_km=5.0,
                gpx_elevation_m=200,
                preset="nature_outdoor",
                model="test-model",
            )
            prompt = mock_call.call_args[0][0]
            assert "5.0" in prompt
            assert "200" in prompt
