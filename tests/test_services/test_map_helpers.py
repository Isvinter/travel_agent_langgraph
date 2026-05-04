"""Tests for map helper functions in app/services/generate_mapimage.py"""
import pytest
from app.services.generate_mapimage import _haversine_distance


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
