import pytest
from app.calendar.models import CalendarMonthPage, MonthSlot
from app.calendar.renderer import render_calendar


@pytest.fixture
def sample_data(tmp_path):
    """Erzeugt Test-Bilder und CalendarMonthPages."""
    from PIL import Image

    img_paths = []
    for i in range(3):
        p = tmp_path / f"test_{i}.jpg"
        img = Image.new("RGB", (200, 150), color=(i * 80, 100, 200))
        img.save(p, "JPEG")
        img_paths.append(str(p))

    pages = [
        CalendarMonthPage(
            month=0, month_name="Deckblatt", preset_id="cal_cover",
            slots=[MonthSlot(slot_id="cover_img", image_index=0)],
        ),
        CalendarMonthPage(
            month=1, month_name="Januar", preset_id="cal_single_full",
            slots=[MonthSlot(slot_id="img", image_index=1)],
        ),
        CalendarMonthPage(
            month=2, month_name="Februar", preset_id="cal_double_side",
            slots=[
                MonthSlot(slot_id="left", image_index=0),
                MonthSlot(slot_id="right", image_index=2),
            ],
        ),
    ]
    return pages, img_paths


class TestRenderCalendar:
    @pytest.mark.unit
    def test_output_contains_html_doctype(self, sample_data):
        pages, img_paths = sample_data
        html = render_calendar(pages, year=2026, image_paths=img_paths)
        assert "<!DOCTYPE html>" in html
        assert "</html>" in html

    @pytest.mark.unit
    def test_output_contains_cover_and_months(self, sample_data):
        pages, img_paths = sample_data
        html = render_calendar(pages, year=2026, image_paths=img_paths)
        assert "Deckblatt" in html
        assert "Januar" in html
        assert "Februar" in html

    @pytest.mark.unit
    def test_output_contains_day_grid(self, sample_data):
        pages, img_paths = sample_data
        html = render_calendar(pages, year=2026, image_paths=img_paths)
        assert "day-grid" in html

    @pytest.mark.unit
    def test_output_contains_images(self, sample_data):
        pages, img_paths = sample_data
        html = render_calendar(pages, year=2026, image_paths=img_paths)
        assert 'src="file:///' in html

    @pytest.mark.unit
    def test_pages_have_page_break(self, sample_data):
        pages, img_paths = sample_data
        html = render_calendar(pages, year=2026, image_paths=img_paths)
        assert "page-break-after: always" in html
