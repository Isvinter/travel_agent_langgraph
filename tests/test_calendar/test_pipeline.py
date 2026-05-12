import pytest
from app.calendar.models import CalendarConfig
from app.calendar.pipeline import run_calendar_pipeline
from app.state import ImageData


@pytest.fixture
def sample_images(tmp_path):
    from PIL import Image
    paths = []
    for i in range(40):
        p = tmp_path / f"img_{i}.jpg"
        img = Image.new("RGB", (200, 150), color=((i * 20) % 256, 100, 200))
        img.save(p, "JPEG")
        paths.append(str(p))
    return [ImageData(path=p) for p in paths]


class TestCalendarPipeline:
    @pytest.mark.unit
    def test_pipeline_returns_html(self, sample_images):
        config = CalendarConfig(preset="mixed", year=2026)
        result = run_calendar_pipeline(
            images=sample_images,
            config=config,
            base_url="http://localhost:99999",
        )
        assert result.html_content != ""
        assert "<!DOCTYPE html>" in result.html_content
        assert result.selected_image_count > 0
        assert len(result.pages) == 13

    @pytest.mark.unit
    def test_pipeline_with_few_images(self, tmp_path):
        from PIL import Image
        paths = []
        for i in range(5):
            p = tmp_path / f"img_{i}.jpg"
            img = Image.new("RGB", (100, 100), color=(i * 50, 100, 200))
            img.save(p, "JPEG")
            paths.append(str(p))

        images = [ImageData(path=p) for p in paths]
        config = CalendarConfig(preset="mixed", year=2026)
        result = run_calendar_pipeline(
            images=images,
            config=config,
            base_url="http://localhost:99999",
        )
        assert result.html_content != ""
        assert len(result.pages) == 13

    @pytest.mark.unit
    def test_pipeline_empty_images_handled(self):
        result = run_calendar_pipeline(
            images=[],
            config=CalendarConfig(preset="mixed", year=2026),
        )
        assert result.html_content != ""

    @pytest.mark.unit
    def test_pipeline_custom_instructions_passed(self, mocker, sample_images):
        select_mock = mocker.patch("app.calendar.pipeline.select_images")
        select_mock.return_value = sample_images[:35]
        mocker.patch("app.calendar.pipeline.assign_photos_to_months", return_value=[])
        mocker.patch("app.calendar.pipeline.render_calendar", return_value="")

        config = CalendarConfig(
            preset="nature_landscape",
            year=2026,
            custom_instructions="Nur Sonnenaufgänge",
        )
        run_calendar_pipeline(images=sample_images, config=config)

        call_kwargs = select_mock.call_args[1]
        assert call_kwargs["custom_instructions"] == "Nur Sonnenaufgänge"
        assert "landschaft" in call_kwargs["criteria"].lower()
