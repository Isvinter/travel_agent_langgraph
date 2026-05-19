import os
from pathlib import Path

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


class TestCalendarPageCss:
    """Layer 1: CSS-Stabilitätsfix."""

    @pytest.mark.unit
    def test_calendar_page_has_fixed_height(self):
        """.calendar-page hat height: 210mm (nicht min-height)."""
        css_path = os.path.join(
            os.path.dirname(__file__), "..", "..",
            "app", "calendar", "styles.css",
        )
        css = Path(css_path).read_text()
        assert "height: 210mm" in css
        assert "min-height: 210mm" not in css

    @pytest.mark.unit
    def test_grid_items_have_min_height_zero(self):
        """.image-area img und .slot-placeholder haben min-height: 0."""
        css_path = os.path.join(
            os.path.dirname(__file__), "..", "..",
            "app", "calendar", "styles.css",
        )
        css = Path(css_path).read_text()
        img_block_start = css.index(".image-area img,")
        img_block_end = css.index("}", css.index("{", img_block_start) + 1)
        img_block = css[img_block_start:img_block_end]
        assert "min-height: 0" in img_block
        assert "min-width: 0" in img_block


class TestObjectPositionInHtml:
    @pytest.mark.unit
    def test_renderer_accepts_orientations(self, sample_data):
        """Renderer akzeptiert und verarbeitet image_orientations."""
        pages, img_paths = sample_data
        html = render_calendar(
            pages, year=2026, image_paths=img_paths,
            image_orientations=["landscape", "portrait", "square"],
        )
        assert "<!DOCTYPE html>" in html

    @pytest.mark.unit
    def test_object_position_in_output_for_mismatch(self, tmp_path):
        """Bei Orientation-Fehlpassung erscheint object-position im HTML."""
        from PIL import Image
        from app.calendar.models import CalendarMonthPage, MonthSlot

        p = tmp_path / "portrait.jpg"
        img = Image.new("RGB", (600, 800))
        img.save(p, "JPEG")
        img_paths = [str(p)]

        page = CalendarMonthPage(
            month=6, month_name="Juni", preset_id="cal_double_stacked",
            slots=[
                MonthSlot(slot_id="top", image_index=0),
                MonthSlot(slot_id="bottom", image_index=0),
            ],
        )

        html = render_calendar(
            [page], year=2026, image_paths=img_paths,
            image_orientations=["portrait"],
        )
        assert "object-position: center 30%" in html

    @pytest.mark.unit
    def test_no_object_position_for_good_match(self, tmp_path):
        """Bei guter Passung (Landscape in Breitslot) kein object-position."""
        from PIL import Image
        from app.calendar.models import CalendarMonthPage, MonthSlot

        p = tmp_path / "landscape.jpg"
        img = Image.new("RGB", (800, 600))
        img.save(p, "JPEG")
        img_paths = [str(p)]

        page = CalendarMonthPage(
            month=6, month_name="Juni", preset_id="cal_double_stacked",
            slots=[MonthSlot(slot_id="top", image_index=0)],
        )

        html = render_calendar(
            [page], year=2026, image_paths=img_paths,
            image_orientations=["landscape"],
        )
        assert "object-position" not in html
