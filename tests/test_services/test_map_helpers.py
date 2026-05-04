"""Tests for map helper functions in app/services/generate_mapimage.py"""
import pytest
from datetime import datetime, timezone, timedelta
from app.services.generate_mapimage import _match_photos_to_pauses
from app.state import ImageData


class TestMatchPhotosToPauses:
    @pytest.mark.unit
    def test_timezone_aware_pause_times(self):
        """GPX-Pausen mit Zeitzonen-Offset sollen korrekt mit naiven EXIF-Zeiten verglichen werden."""
        tz = timezone(timedelta(hours=2))
        images = [
            ImageData(path="a.jpg", latitude=47.0, longitude=8.0,
                      timestamp="2024-07-15T10:05:00"),
        ]
        pauses = [
            {
                "start_time": datetime(2024, 7, 15, 10, 0, tzinfo=tz),
                "end_time": datetime(2024, 7, 15, 10, 15, tzinfo=tz),
                "duration_minutes": 15.0,
                "location": {"lat": 47.0, "lon": 8.0},
            }
        ]
        result = _match_photos_to_pauses(images, pauses, distance_m=50.0)
        assert 0 in result
        assert result[0] == [0]
