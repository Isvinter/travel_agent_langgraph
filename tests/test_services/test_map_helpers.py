"""Tests for map helper functions in app/services/generate_mapimage.py"""
import pytest
from datetime import datetime
from app.services.generate_mapimage import _haversine_distance, _group_photos_by_location, _match_photos_to_pauses
from app.state import ImageData


class TestHaversineDistance:
    @pytest.mark.unit
    def test_same_point_zero(self):
        assert _haversine_distance(47.0, 8.0, 47.0, 8.0) == 0.0

    @pytest.mark.unit
    def test_one_degree_latitude(self):
        # 1 Grad Latitude ≈ 111 km
        dist = _haversine_distance(47.0, 8.0, 48.0, 8.0)
        assert 110000 < dist < 112000

    @pytest.mark.unit
    def test_small_distance_known(self):
        # ~11.1m (0.0001 Grad Latitude)
        dist = _haversine_distance(47.0, 8.0, 47.0001, 8.0)
        assert 10 < dist < 12

    @pytest.mark.unit
    def test_equator_large_distance(self):
        # ~157 km (Hamburg-Bremen grob)
        dist = _haversine_distance(53.55, 10.0, 53.08, 8.8)
        assert 90000 < dist < 120000


class TestGroupPhotosByLocation:
    @pytest.mark.unit
    def test_single_photo(self):
        images = [ImageData(path="a.jpg", latitude=47.0, longitude=8.0, timestamp="2024-01-01T10:00:00")]
        groups = _group_photos_by_location(images)
        assert groups == [[0]]

    @pytest.mark.unit
    def test_far_apart_photos_separate(self):
        images = [
            ImageData(path="a.jpg", latitude=47.0, longitude=8.0, timestamp="2024-01-01T10:00:00"),
            ImageData(path="b.jpg", latitude=47.1, longitude=8.0, timestamp="2024-01-01T11:00:00"),
        ]
        groups = _group_photos_by_location(images)
        assert len(groups) == 2
        assert 0 in groups[0] or 0 in groups[1]
        assert 1 in groups[0] or 1 in groups[1]

    @pytest.mark.unit
    def test_nearby_photos_grouped(self):
        images = [
            ImageData(path="a.jpg", latitude=47.0, longitude=8.0, timestamp="2024-01-01T10:00:00"),
            ImageData(path="b.jpg", latitude=47.0, longitude=8.00003, timestamp="2024-01-01T10:01:00"),
        ]
        groups = _group_photos_by_location(images, threshold_m=5.0)
        # ~3.3m auseinander -> eine Gruppe
        assert len(groups) == 1
        assert 0 in groups[0] and 1 in groups[0]

    @pytest.mark.unit
    def test_nearby_and_far_mixed(self):
        images = [
            ImageData(path="a.jpg", latitude=47.0, longitude=8.0, timestamp="T1"),
            ImageData(path="b.jpg", latitude=47.0, longitude=8.00001, timestamp="T2"),  # ~1.1m -> Gruppe mit a
            ImageData(path="c.jpg", latitude=47.1, longitude=8.0, timestamp="T3"),       # weit weg
        ]
        groups = _group_photos_by_location(images, threshold_m=5.0)
        assert len(groups) == 2
        group_sizes = sorted([len(g) for g in groups])
        assert group_sizes == [1, 2]

    @pytest.mark.unit
    def test_custom_threshold(self):
        images = [
            ImageData(path="a.jpg", latitude=47.0, longitude=8.0, timestamp="T1"),
            ImageData(path="b.jpg", latitude=47.0, longitude=8.0005, timestamp="T2"),  # ~55m
        ]
        # Mit 100m Threshold -> eine Gruppe
        groups_wide = _group_photos_by_location(images, threshold_m=100.0)
        assert len(groups_wide) == 1
        # Mit 5m Threshold -> zwei Gruppen
        groups_tight = _group_photos_by_location(images, threshold_m=5.0)
        assert len(groups_tight) == 2

    @pytest.mark.unit
    def test_skips_images_without_coordinates(self):
        images = [
            ImageData(path="a.jpg", latitude=47.0, longitude=8.0, timestamp="T1"),
            ImageData(path="b.jpg", latitude=None, longitude=None, timestamp="T2"),
            ImageData(path="c.jpg", latitude=47.0, longitude=8.00001, timestamp="T3"),
        ]
        groups = _group_photos_by_location(images, threshold_m=5.0)
        # b wird ignoriert, a und c sind nah -> eine Gruppe
        assert len(groups) == 1
        assert 0 in groups[0] and 2 in groups[0]

    @pytest.mark.unit
    def test_empty_images(self):
        assert _group_photos_by_location([]) == []


class TestMatchPhotosToPauses:
    @pytest.mark.unit
    def test_both_criteria_met(self):
        images = [
            ImageData(path="a.jpg", latitude=47.0, longitude=8.0,
                      timestamp="2024-07-15T10:05:00"),
        ]
        pauses = [
            {
                "start_time": datetime(2024, 7, 15, 10, 0),
                "end_time": datetime(2024, 7, 15, 10, 15),
                "duration_minutes": 15.0,
                "location": {"lat": 47.0, "lon": 8.0},
            }
        ]
        result = _match_photos_to_pauses(images, pauses, distance_m=50.0)
        assert 0 in result
        assert result[0] == [0]

    @pytest.mark.unit
    def test_spatial_only_not_matched(self):
        # Foto räumlich nah, aber zeitlich ausserhalb -> keine Zuordnung
        images = [
            ImageData(path="a.jpg", latitude=47.0, longitude=8.0,
                      timestamp="2024-07-15T11:00:00"),  # ausserhalb 10:00-10:15
        ]
        pauses = [
            {
                "start_time": datetime(2024, 7, 15, 10, 0),
                "end_time": datetime(2024, 7, 15, 10, 15),
                "duration_minutes": 15.0,
                "location": {"lat": 47.0, "lon": 8.0},
            }
        ]
        result = _match_photos_to_pauses(images, pauses, distance_m=50.0)
        assert len(result) == 0

    @pytest.mark.unit
    def test_temporal_only_not_matched(self):
        # Foto zeitlich in Pause, aber räumlich weit weg -> keine Zuordnung
        images = [
            ImageData(path="a.jpg", latitude=47.1, longitude=8.0,  # >50m
                      timestamp="2024-07-15T10:05:00"),
        ]
        pauses = [
            {
                "start_time": datetime(2024, 7, 15, 10, 0),
                "end_time": datetime(2024, 7, 15, 10, 15),
                "duration_minutes": 15.0,
                "location": {"lat": 47.0, "lon": 8.0},
            }
        ]
        result = _match_photos_to_pauses(images, pauses, distance_m=50.0)
        assert len(result) == 0

    @pytest.mark.unit
    def test_multiple_photos_one_pause(self):
        images = [
            ImageData(path="a.jpg", latitude=47.0, longitude=8.0,
                      timestamp="2024-07-15T10:05:00"),
            ImageData(path="b.jpg", latitude=47.0, longitude=8.0002,  # ~22m
                      timestamp="2024-07-15T10:10:00"),
        ]
        pauses = [
            {
                "start_time": datetime(2024, 7, 15, 10, 0),
                "end_time": datetime(2024, 7, 15, 10, 15),
                "duration_minutes": 15.0,
                "location": {"lat": 47.0, "lon": 8.0},
            }
        ]
        result = _match_photos_to_pauses(images, pauses, distance_m=50.0)
        assert 0 in result
        assert sorted(result[0]) == [0, 1]

    @pytest.mark.unit
    def test_multiple_pauses(self):
        images = [
            ImageData(path="a.jpg", latitude=47.0, longitude=8.0,
                      timestamp="2024-07-15T10:05:00"),
            ImageData(path="b.jpg", latitude=47.1, longitude=8.1,
                      timestamp="2024-07-15T12:35:00"),
        ]
        pauses = [
            {
                "start_time": datetime(2024, 7, 15, 10, 0),
                "end_time": datetime(2024, 7, 15, 10, 15),
                "duration_minutes": 15.0,
                "location": {"lat": 47.0, "lon": 8.0},
            },
            {
                "start_time": datetime(2024, 7, 15, 12, 30),
                "end_time": datetime(2024, 7, 15, 12, 55),
                "duration_minutes": 25.0,
                "location": {"lat": 47.1, "lon": 8.1},
            },
        ]
        result = _match_photos_to_pauses(images, pauses, distance_m=50.0)
        assert result[0] == [0]
        assert result[1] == [1]

    @pytest.mark.unit
    def test_photo_matches_multiple_pauses(self):
        # Foto liegt zeitlich+räumlich in zwei Pausen -> beide bekommen es
        images = [
            ImageData(path="a.jpg", latitude=47.0, longitude=8.0,
                      timestamp="2024-07-15T10:05:00"),
        ]
        pauses = [
            {
                "start_time": datetime(2024, 7, 15, 10, 0),
                "end_time": datetime(2024, 7, 15, 10, 15),
                "duration_minutes": 15.0,
                "location": {"lat": 47.0, "lon": 8.0},
            },
            {
                "start_time": datetime(2024, 7, 15, 10, 0),
                "end_time": datetime(2024, 7, 15, 10, 30),
                "duration_minutes": 30.0,
                "location": {"lat": 47.0, "lon": 8.0},
            },
        ]
        result = _match_photos_to_pauses(images, pauses, distance_m=50.0)
        assert len(result) == 2  # Beide Pausen matchen
        assert result[0] == [0]
        assert result[1] == [0]

    @pytest.mark.unit
    def test_photo_without_timestamp_skipped(self):
        images = [
            ImageData(path="a.jpg", latitude=47.0, longitude=8.0, timestamp=None),
        ]
        pauses = [
            {
                "start_time": datetime(2024, 7, 15, 10, 0),
                "end_time": datetime(2024, 7, 15, 10, 15),
                "duration_minutes": 15.0,
                "location": {"lat": 47.0, "lon": 8.0},
            }
        ]
        result = _match_photos_to_pauses(images, pauses, distance_m=50.0)
        assert len(result) == 0

    @pytest.mark.unit
    def test_photo_without_coordinates_skipped(self):
        images = [
            ImageData(path="a.jpg", latitude=None, longitude=None,
                      timestamp="2024-07-15T10:05:00"),
        ]
        pauses = [
            {
                "start_time": datetime(2024, 7, 15, 10, 0),
                "end_time": datetime(2024, 7, 15, 10, 15),
                "duration_minutes": 15.0,
                "location": {"lat": 47.0, "lon": 8.0},
            }
        ]
        result = _match_photos_to_pauses(images, pauses, distance_m=50.0)
        assert len(result) == 0

    @pytest.mark.unit
    def test_exif_timestamp_format(self):
        """EXIF-Format '2024:07:15 10:05:00' wird korrekt normalisiert."""
        images = [
            ImageData(path="a.jpg", latitude=47.0, longitude=8.0,
                      timestamp="2024:07:15 10:05:00"),
        ]
        pauses = [
            {
                "start_time": datetime(2024, 7, 15, 10, 0),
                "end_time": datetime(2024, 7, 15, 10, 15),
                "duration_minutes": 15.0,
                "location": {"lat": 47.0, "lon": 8.0},
            }
        ]
        result = _match_photos_to_pauses(images, pauses, distance_m=50.0)
        assert 0 in result
        assert result[0] == [0]

    @pytest.mark.unit
    def test_empty_inputs(self):
        assert _match_photos_to_pauses([], [], 50.0) == {}
        assert _match_photos_to_pauses([], [{"location": {"lat": 47.0, "lon": 8.0}}], 50.0) == {}
