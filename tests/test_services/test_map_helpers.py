"""Tests for map helper functions in app/services/generate_mapimage.py"""
import pytest
from app.services.generate_mapimage import _haversine_distance, _group_photos_by_location
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
