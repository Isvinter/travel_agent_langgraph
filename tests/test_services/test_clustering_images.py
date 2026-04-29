"""Tests for app/services/clustering_images.py"""
import pytest
from app.services.clustering_images import cluster_images
from app.state import ImageData


class TestClusterImages:
    @pytest.mark.unit
    def test_two_close_one_far_creates_two_clusters(self):
        images = [
            ImageData(path="a.jpg", latitude=47.3, longitude=8.5),
            ImageData(path="b.jpg", latitude=47.3001, longitude=8.5001),
            ImageData(path="c.jpg", latitude=47.5, longitude=9.0),
        ]
        clusters = cluster_images(images, radius_m=20)
        assert len(clusters) == 2

    @pytest.mark.unit
    def test_single_image_creates_one_cluster(self):
        images = [ImageData(path="a.jpg", latitude=47.0, longitude=8.0)]
        clusters = cluster_images(images, radius_m=20)
        assert len(clusters) == 1
        assert len(clusters[0]["images"]) == 1

    @pytest.mark.unit
    def test_empty_list_returns_empty(self):
        clusters = cluster_images([], radius_m=20)
        assert clusters == []

    @pytest.mark.unit
    def test_cluster_centroid_is_mean_of_members(self):
        images = [
            ImageData(path="a.jpg", latitude=47.300, longitude=8.500),
            ImageData(path="b.jpg", latitude=47.302, longitude=8.502),
        ]
        clusters = cluster_images(images, radius_m=1000)
        assert len(clusters) == 1
        c = clusters[0]
        assert c["center_lat"] == pytest.approx(47.301)
        assert c["center_lon"] == pytest.approx(8.501)

    @pytest.mark.unit
    def test_images_with_none_coordinates_raises(self):
        images = [
            ImageData(path="a.jpg", latitude=47.0, longitude=8.0),
            ImageData(path="b.jpg", latitude=None, longitude=None),
        ]
        with pytest.raises(TypeError):
            cluster_images(images, radius_m=20)
