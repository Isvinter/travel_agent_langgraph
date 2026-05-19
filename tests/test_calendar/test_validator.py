"""Layer 5: HTML-Strukturvalidierung."""
import pytest
from app.calendar.validator import validate_calendar_html
from app.calendar.renderer import render_calendar
from app.calendar.models import CalendarMonthPage, MonthSlot


class TestValidateCalendarHtml:
    @pytest.mark.unit
    def test_valid_html_passes(self, tmp_path):
        """Korrektes HTML: keine Fehler."""
        from PIL import Image

        img_paths = []
        for i in range(35):
            p = tmp_path / f"img_{i}.jpg"
            img = Image.new("RGB", (200, 150))
            img.save(p, "JPEG")
            img_paths.append(str(p))

        pages = []
        for i in range(13):
            month = i
            month_name = "Deckblatt" if i == 0 else f"Monat {i}"
            preset_id = "cal_cover" if i == 0 else "cal_single_full"
            pages.append(CalendarMonthPage(
                month=month, month_name=month_name, preset_id=preset_id,
                slots=[MonthSlot(slot_id="cover_img" if i == 0 else "img", image_index=i)],
            ))

        html = render_calendar(pages, year=2026, image_paths=img_paths)
        issues = validate_calendar_html(html)
        assert len(issues) == 0, f"Unerwartete Issues: {issues}"

    @pytest.mark.unit
    def test_missing_pages_detected(self):
        """Weniger als 13 Seiten → Fehler."""
        html = """<!DOCTYPE html><html><body>
        <div class="calendar-page"></div>
        </body></html>"""
        issues = validate_calendar_html(html)
        assert any("13 Seiten" in i or "page" in i.lower() for i in issues)

    @pytest.mark.unit
    def test_slot_placeholder_detected(self):
        """slot-placeholder divs → Warnung."""
        html = """<!DOCTYPE html><html><body>
        <div class="calendar-page"><div class="slot-placeholder"></div></div>
        </body></html>"""
        issues = validate_calendar_html(html)
        assert any("placeholder" in i.lower() for i in issues), f"Issues: {issues}"

    @pytest.mark.unit
    def test_empty_html_returns_error(self):
        """Leeres HTML → Fehler."""
        issues = validate_calendar_html("")
        assert len(issues) > 0

    @pytest.mark.unit
    def test_duplicate_images_detected(self):
        """Doppelte Bilder auf einer Seite → Warnung."""
        html = """<!DOCTYPE html><html><body>
        <div class="calendar-page">
          <div class="image-area cal-double-side">
            <img class="slot-image" style="grid-area: left" src="file:///tmp/1.jpg">
            <img class="slot-image" style="grid-area: right" src="file:///tmp/1.jpg">
          </div>
        </div>
        </body></html>"""
        issues = validate_calendar_html(html)
        assert any("doppelt" in i.lower() or "duplicate" in i.lower()
                   for i in issues), f"Issues: {issues}"
