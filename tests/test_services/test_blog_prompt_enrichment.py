"""Tests for enrichment integration in blog prompt builder."""
from app.services.blog_generator import construct_blog_post_prompt


class TestBlogPromptEnrichment:
    def test_includes_enrichment_context_when_provided(self):
        enrichment = {
            "kept_pois": [
                {"name": "Berggipfel", "type": "peak", "distance_km": 1.0,
                 "wiki_extract": "A majestic peak in the Alps."},
            ],
            "weather_summary": "Mild alpine weather with clear skies.",
            "discarded_weather_fields": ["freezing_level_m"],
        }
        images = [{"path": "img1.jpg", "timestamp": "2025-06-01T10:00:00",
                   "latitude": 47.3, "longitude": 11.4}]

        prompt, img_data = construct_blog_post_prompt(
            images=images,
            enrichment_context=enrichment,
        )
        assert "Mild alpine weather" in prompt
        assert "Berggipfel" in prompt
        assert "A majestic peak" in prompt

    def test_falls_back_to_raw_weather_when_no_enrichment_context(self):
        from app.state import DailyWeather, WeatherInfo

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
        images = [{"path": "img1.jpg"}]

        prompt, img_data = construct_blog_post_prompt(
            images=images,
            enrichment_context={},
            weather=weather,
            poi_list=[{"name": "Test Peak", "type": "peak", "distance_km": 0.5}],
        )
        assert "Test Peak" in prompt

    def test_no_enrichment_section_when_no_data(self):
        images = [{"path": "img1.jpg"}]
        prompt, img_data = construct_blog_post_prompt(
            images=images,
            enrichment_context=None,
            weather=None,
            poi_list=[],
        )
        assert isinstance(prompt, str)
        # Should contain the blog prompt but not enrichment headers
        # when no enrichment data is provided
