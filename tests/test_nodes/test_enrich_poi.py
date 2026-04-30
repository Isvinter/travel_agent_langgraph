"""Tests for app/nodes/enrich_poi_node.py"""
from unittest.mock import patch
from app.nodes.enrich_poi_node import enrich_poi_node
from app.state import AppState


class TestEnrichPoiNode:
    def test_skips_when_no_gpx_pauses(self):
        state = AppState(gpx_pauses=[], gpx_stats=None)
        result = enrich_poi_node(state)
        assert result.poi_list == []

    def test_enriches_pois_from_pauses(self):
        from app.services.gpx_analytics import TrackPoint, GPXStats

        points = [TrackPoint(lat=47.3, lon=11.4, elevation=800.0, time=None)]
        stats = GPXStats(
            total_distance_m=5000, elevation_gain_m=200, elevation_loss_m=100,
            avg_speed_kmh=4.0, max_speed_kmh=8.0, points=points,
        )
        pauses = [{"location": {"lat": 47.3, "lon": 11.4}}]
        state = AppState(gpx_stats=stats, gpx_pauses=pauses)

        mock_pois = [
            {"name": "Berggipfel", "type": "peak", "lat": 47.302, "lon": 11.402,
             "distance_km": 0.5, "wiki_extract": "A beautiful peak"},
        ]
        with patch("app.nodes.enrich_poi_node.fetch_pois", return_value=mock_pois):
            result = enrich_poi_node(state)
            assert len(result.poi_list) == 1
            assert result.poi_list[0]["name"] == "Berggipfel"
            assert result.poi_list[0]["wiki_extract"] == "A beautiful peak"
