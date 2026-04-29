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
        assert len(result.image_clusters) >= 1

    def test_empty_images_returns_unchanged(self):
        state = AppState(images=[])
        result = clustering_image_node(state)
        assert result.image_clusters == []
