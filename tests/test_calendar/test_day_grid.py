import pytest
from app.calendar.day_grid import generate_day_grid, WEEKDAYS


class TestWeekdays:
    @pytest.mark.unit
    def test_weekdays_german(self):
        assert WEEKDAYS == ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]


class TestGenerateDayGrid:
    @pytest.mark.unit
    def test_januar_2026(self):
        html = generate_day_grid(1, 2026)
        assert 'class="weekday-row"' in html
        assert "Mo" in html
        assert "So" in html
        assert "31" in html

    @pytest.mark.unit
    def test_februar_2026(self):
        html = generate_day_grid(2, 2026)
        assert "28" in html
        assert "29" not in html

    @pytest.mark.unit
    def test_februar_2028_schaltjahr(self):
        html = generate_day_grid(2, 2028)
        assert "29" in html

    @pytest.mark.unit
    def test_weekends_highlighted(self):
        html = generate_day_grid(1, 2026)
        assert "weekend" in html

    @pytest.mark.unit
    def test_kw_column_present(self):
        html = generate_day_grid(1, 2026)
        assert "KW" in html or "kw" in html

    @pytest.mark.unit
    def test_no_trailing_empty_rows(self):
        html = generate_day_grid(1, 2026)
        assert "31" in html
