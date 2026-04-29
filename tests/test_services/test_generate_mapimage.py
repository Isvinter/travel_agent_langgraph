"""Tests for app/services/generate_mapimage.py"""
import os
import shutil
from unittest.mock import MagicMock

import pytest
from app.services.generate_mapimage import generate_map_html, html_to_png
from app.services.gpx_analytics import TrackPoint


@pytest.fixture
def sample_points():
    return [
        TrackPoint(lat=47.3, lon=8.5, elevation=500.0, time=None),
        TrackPoint(lat=47.301, lon=8.501, elevation=510.0, time=None),
        TrackPoint(lat=47.302, lon=8.502, elevation=520.0, time=None),
    ]


class TestGenerateMapHtml:
    @pytest.mark.unit
    def test_generates_html_file(self, tmp_path, sample_points):
        html_path = str(tmp_path / "map.html")
        generate_map_html(sample_points, html_path)

        assert os.path.exists(html_path)
        content = open(html_path).read()
        assert "folium" in content.lower() or "leaflet" in content.lower()
        assert "47.3" in content


class TestHtmlToPng:
    @pytest.mark.unit
    def test_mocked_selenium_saves_png(self, tmp_path, sample_points, mocker):
        html_path = str(tmp_path / "map.html")
        generate_map_html(sample_points, html_path)

        mock_driver = MagicMock()
        mocker.patch("selenium.webdriver.Chrome", return_value=mock_driver)

        output_png = str(tmp_path / "map.png")
        html_to_png(html_path, output_png)

        mock_driver.save_screenshot.assert_called_once_with(output_png)
        mock_driver.quit.assert_called_once()

    @pytest.mark.integration
    def test_real_chrome_if_available(self, tmp_path, sample_points):
        if not (shutil.which("chromium") or shutil.which("google-chrome")):
            pytest.skip("Chrome/Chromium not installed")

        html_path = str(tmp_path / "map.html")
        generate_map_html(sample_points, html_path)

        output_png = str(tmp_path / "map.png")
        html_to_png(html_path, output_png)

        assert os.path.exists(output_png)
        assert os.path.getsize(output_png) > 0
