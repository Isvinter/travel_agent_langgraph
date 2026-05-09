"""Tests for app/nodes/clustering_image_node.py"""
from app.nodes.clustering_image_node import clustering_image_node
from app.state import AppState, ImageData


class TestClusteringImageNode:
    def test_clusters_images_and_stores_in_state(self):
        images = [
            ImageData(path="a.jpg", latitude=47.3, longitude=8.5),
            ImageData(path="b.jpg", latitude=47.3, longitude=8.5),
        ]
        state = AppState(images=images)
        result = clustering_image_node(state)
        assert len(result.image_clusters) == 1  # Same location → same cluster
        assert len(result.image_clusters[0].images) == 2  # Beide im gleichen Cluster

    def test_far_apart_images_form_multiple_clusters(self):
        images = [
            ImageData(path="zurich.jpg", latitude=47.37, longitude=8.54),
            ImageData(path="bern.jpg", latitude=46.94, longitude=7.44),
            ImageData(path="basel.jpg", latitude=47.55, longitude=7.58),
        ]
        state = AppState(images=images)
        result = clustering_image_node(state)
        assert len(result.image_clusters) >= 3  # Alle weit auseinander → je eigener Cluster

    def test_empty_images_returns_unchanged(self):
        state = AppState(images=[])
        result = clustering_image_node(state)
        assert result.image_clusters == []

    def test_images_without_coordinates_are_skipped(self):
        images = [
            ImageData(path="no_gps.jpg", latitude=None, longitude=None),
            ImageData(path="with_gps.jpg", latitude=47.0, longitude=8.0),
        ]
        state = AppState(images=images)
        result = clustering_image_node(state)
        # Nur das Bild mit Koordinaten bildet einen Cluster (None-GPS wird ge-skippt)
        assert len(result.image_clusters) == 1
        assert len(result.image_clusters[0].images) == 1
        assert result.image_clusters[0].images[0] == "with_gps.jpg"
