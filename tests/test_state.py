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
        assert state.enrichment_context.weather_summary == ""
        assert state.enrichment_context.kept_pois == []


class TestOutputConfig:
    def test_pdf_export_defaults_to_false(self):
        from app.state import OutputConfig
        config = OutputConfig()
        assert config.pdf_export is False

    def test_pdf_export_can_be_true(self):
        from app.state import OutputConfig
        config = OutputConfig(pdf_export=True)
        assert config.pdf_export is True


class TestPhotobookConfig:
    def test_defaults(self):
        """PhotobookConfig standardmässig mit photo_count=20."""
        from app.state import PhotobookConfig
        config = PhotobookConfig()
        assert config.photo_count == 20

    def test_min_boundary(self):
        """photo_count=5 erlaubt (Minimum)."""
        from app.state import PhotobookConfig
        config = PhotobookConfig(photo_count=5)
        assert config.photo_count == 5

    def test_max_boundary(self):
        """photo_count=30 erlaubt (Maximum)."""
        from app.state import PhotobookConfig
        config = PhotobookConfig(photo_count=30)
        assert config.photo_count == 30

    def test_below_min_raises(self):
        """photo_count=4 wirft ValidationError."""
        from app.state import PhotobookConfig
        with pytest.raises(ValidationError):
            PhotobookConfig(photo_count=4)

    def test_above_max_raises(self):
        """photo_count=31 wirft ValidationError."""
        from app.state import PhotobookConfig
        with pytest.raises(ValidationError):
            PhotobookConfig(photo_count=31)

    def test_size_field_defaults_to_normal(self):
        """size ist standardmässig 'normal'."""
        from app.state import PhotobookConfig
        config = PhotobookConfig()
        assert config.size == "normal"

    def test_page_range_default(self):
        """page_range ist standardmässig '14-18'."""
        from app.state import PhotobookConfig
        config = PhotobookConfig()
        assert config.page_range == "14-18"

    def test_size_short(self):
        """size='short' ist erlaubt."""
        from app.state import PhotobookConfig
        config = PhotobookConfig(size="short", page_range="8-12", photo_count=14)
        assert config.size == "short"
        assert config.page_range == "8-12"


class TestApplyPhotobookSize:
    def test_short_maps_correctly(self):
        from app.state import apply_photobook_size
        config = apply_photobook_size("short")
        assert config.photo_count == 12
        assert config.page_range == "8-12"
        assert config.size == "short"

    def test_normal_maps_correctly(self):
        from app.state import apply_photobook_size
        config = apply_photobook_size("normal")
        assert config.photo_count == 16
        assert config.page_range == "14-18"
        assert config.size == "normal"

    def test_detailed_maps_correctly(self):
        from app.state import apply_photobook_size
        config = apply_photobook_size("detailed")
        assert config.photo_count == 20
        assert config.page_range == "20-24"
        assert config.size == "detailed"

    def test_unknown_size_falls_back_to_normal(self):
        from app.state import apply_photobook_size
        config = apply_photobook_size("invalid")
        assert config.photo_count == 16
        assert config.size == "normal"


class TestOutputConfigMode:
    def test_mode_defaults_to_blog(self):
        """mode ist standardmäßig 'blog'."""
        from app.state import OutputConfig
        config = OutputConfig()
        assert config.mode == "blog"

    def test_mode_can_be_photobook(self):
        """mode='photobook' ist erlaubt."""
        from app.state import OutputConfig
        config = OutputConfig(mode="photobook")
        assert config.mode == "photobook"

    def test_photobook_config_default(self):
        """photobook hat default PhotobookConfig."""
        from app.state import OutputConfig
        config = OutputConfig()
        assert config.photobook.photo_count == 20


class TestPageDescription:
    def test_minimal_creation(self):
        """PageDescription mit minimalen Feldern."""
        from app.state import PageDescription
        pd = PageDescription(template_id="cover_hero", page_type="single")
        assert pd.template_id == "cover_hero"
        assert pd.page_type == "single"
        assert pd.slots == []

    def test_with_slots(self):
        """PageDescription mit gefüllten Slots."""
        from app.state import PageDescription
        pd = PageDescription(
            template_id="double_stacked",
            page_type="spread",
            slots=[{"slot_id": "main", "image_index": 0}],
        )
        assert len(pd.slots) == 1
        assert pd.slots[0].slot_id == "main"


class TestAppStatePhotobook:
    def test_photobook_fields_have_defaults(self):
        """Photobook-Felder im AppState haben korrekte Defaults."""
        state = AppState()
        assert state.photobook_images == []
        assert state.photobook_plan is None
        assert state.photobook_pages == []
        assert state.photobook_html is None
        assert state.photobook_pdf_path is None
