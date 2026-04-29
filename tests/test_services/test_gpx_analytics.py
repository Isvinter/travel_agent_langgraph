"""Tests for app/services/gpx_analytics.py"""
import pytest
from app.services.gpx_analytics import (
    parse_gpx,
    compute_gpx_stats,
    detect_pauses,
    analyze_track,
    TrackPoint,
    GPXStats,
)


class TestParseGpx:
    @pytest.mark.unit
    def test_parse_valid_gpx_returns_trackpoints(self, sample_gpx_path):
        points = parse_gpx(sample_gpx_path)
        assert len(points) == 15
        assert all(isinstance(p, TrackPoint) for p in points)
        assert points[0].lat == pytest.approx(47.0)
        assert points[0].lon == pytest.approx(8.0)
        assert points[0].elevation == pytest.approx(500.0)
        assert points[0].time is not None

    @pytest.mark.unit
    def test_parse_nonexistent_file_raises(self):
        with pytest.raises(FileNotFoundError):
            parse_gpx("/nonexistent/path.gpx")


class TestComputeGpxStats:
    @pytest.mark.unit
    def test_compute_stats_returns_nonzero_distance(self, sample_gpx_path):
        points = parse_gpx(sample_gpx_path)
        stats = compute_gpx_stats(points)
        assert isinstance(stats, GPXStats)
        assert stats.total_distance_m > 0
        assert len(stats.points) == 15
        assert stats.elevation_gain_m > 0

    @pytest.mark.unit
    def test_compute_stats_single_point_returns_zero_stats(self):
        single = [TrackPoint(lat=47.0, lon=8.0, elevation=500.0, time=None)]
        stats = compute_gpx_stats(single)
        assert stats.total_distance_m == 0.0
        assert stats.avg_speed_kmh == 0.0


class TestDetectPauses:
    @pytest.mark.unit
    def test_detect_pause_on_stationary_points(self, sample_gpx_path):
        points = parse_gpx(sample_gpx_path)
        pauses = detect_pauses(points, min_pause_minutes=10.0)
        assert len(pauses) >= 1
        pause = pauses[0]
        assert "duration_minutes" in pause
        assert pause["duration_minutes"] >= 10.0

    @pytest.mark.unit
    def test_no_pauses_on_continuous_track(self):
        points = [
            TrackPoint(lat=47.0, lon=8.0, elevation=500.0, time=None),
            TrackPoint(lat=47.001, lon=8.001, elevation=510.0, time=None),
        ]
        pauses = detect_pauses(points, min_pause_minutes=10.0)
        assert len(pauses) == 0


class TestAnalyzeTrack:
    @pytest.mark.integration
    def test_analyze_track_returns_stats_and_pauses(self, sample_gpx_path):
        stats, pauses = analyze_track(sample_gpx_path)
        assert isinstance(stats, GPXStats)
        assert isinstance(pauses, list)
