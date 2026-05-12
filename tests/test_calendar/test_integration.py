"""Integrationstests für die Kalender-Pipeline (kein Ollama/Chrome nötig)."""
import pytest
from app.calendar.pipeline import run_calendar_pipeline
from app.calendar.models import CalendarConfig
from app.state import ImageData


@pytest.fixture
def many_images(tmp_path):
    """50 Test-Bilder für realistischere Szenarien."""
    from PIL import Image
    paths = []
    for i in range(50):
        p = tmp_path / f"photo_{i:03d}.jpg"
        img = Image.new("RGB", (400, 300), color=((i * 15) % 256, 120, 200))
        img.save(p, "JPEG")
        paths.append(str(p))
    return [ImageData(path=p) for p in paths]


@pytest.mark.integration
class TestCalendarIntegration:
    def test_full_pipeline_with_fallback(self, many_images):
        """Vollständiger Pipeline-Durchlauf mit Fallback (kein Ollama nötig)."""
        config = CalendarConfig(preset="mixed", year=2026)

        result = run_calendar_pipeline(
            images=many_images,
            config=config,
            base_url="http://localhost:99999",
        )

        assert len(result.pages) == 13
        assert result.html_content.startswith("<!DOCTYPE html>")
        assert "Januar" in result.html_content
        assert "Dezember" in result.html_content
        assert "Deckblatt" in result.html_content
        assert "day-grid" in result.html_content

    def test_html_is_valid(self, many_images):
        """HTML enthält keine offensichtlichen Fehler."""
        config = CalendarConfig(preset="mixed", year=2026)
        result = run_calendar_pipeline(
            images=many_images,
            config=config,
            base_url="http://localhost:99999",
        )

        html = result.html_content
        assert html.count('<div class="calendar-page') == 13
        assert html.count('<div class="day-grid"') == 12
        assert html.count('<div class="month-header"') == 12
        assert html.count("</body>") == 1
        assert html.count("</html>") == 1

    def test_different_presets_work(self, many_images):
        """Alle 4 Presets funktionieren."""
        for preset in ["mixed", "nature_landscape", "people", "culture"]:
            config = CalendarConfig(preset=preset, year=2026)
            result = run_calendar_pipeline(
                images=many_images,
                config=config,
                base_url="http://localhost:99999",
            )
            assert result.html_content != ""
            assert len(result.pages) == 13

    def test_custom_instructions_propagate(self, many_images):
        """Pipeline mit custom_instructions läuft ohne Fehler durch."""
        config = CalendarConfig(
            preset="nature_landscape",
            year=2026,
            custom_instructions="Bevorzuge Sonnenaufgänge und Nahaufnahmen",
        )
        result = run_calendar_pipeline(
            images=many_images,
            config=config,
            base_url="http://localhost:99999",
        )
        assert result.html_content != ""
        assert len(result.pages) == 13
