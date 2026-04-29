"""Tests for app/services/generate_elevation_profile.py"""
import os

import pytest
from app.services.generate_elevation_profile import generate_elevation_profile
from app.services.gpx_analytics import TrackPoint


class TestGenerateElevationProfile:
    @pytest.mark.integration
    def test_generates_png_file(self, tmp_path):
        points = [
            TrackPoint(lat=47.0, lon=8.0, elevation=500.0, time=None),
            TrackPoint(lat=47.001, lon=8.001, elevation=510.0, time=None),
            TrackPoint(lat=47.002, lon=8.002, elevation=520.0, time=None),
        ]
        output = str(tmp_path / "profile.png")
        generate_elevation_profile(points, output)

        assert os.path.exists(output)
        assert os.path.getsize(output) > 0

    @pytest.mark.unit
    def test_skips_points_without_elevation(self, tmp_path):
        points = [
            TrackPoint(lat=47.0, lon=8.0, elevation=None, time=None),
            TrackPoint(lat=47.001, lon=8.001, elevation=510.0, time=None),
        ]
        output = str(tmp_path / "profile.png")
        generate_elevation_profile(points, output)
        assert os.path.exists(output)
