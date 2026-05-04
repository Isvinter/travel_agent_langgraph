"""Tests for app/services/poi_enricher.py"""
from unittest.mock import patch, Mock

import pytest

from app.services.poi_enricher import (
    fetch_pois,
    _build_overpass_query,
    _parse_overpass_response,
    _deduplicate_pois_by_name_and_proximity,
    _enrich_with_wikipedia,
)


class TestBuildOverpassQuery:
    def test_builds_query_for_single_location(self):
        query = _build_overpass_query(47.3, 11.4, radius=2000)
        assert "[out:json]" in query
        assert "around:2000" in query
        assert 'tourism' in query
        assert 'natural' in query
        assert 'historic' in query
        assert "out 15;" in query

    def test_respects_custom_radius(self):
        query = _build_overpass_query(47.3, 11.4, radius=5000)
        assert "around:5000" in query

    def test_builds_query_from_all_categories(self):
        query = _build_overpass_query(47.3, 11.4, radius=3000)
        assert "[out:json]" in query
        assert "around:3000" in query
        # Alle Kategorien prüfen
        assert 'natural"~"peak|volcano' in query
        assert 'tourism"~"alpine_hut|wilderness_hut' in query
        assert 'historic"~"castle|ruins' in query
        assert 'amenity"~"shelter|drinking_water' in query
        assert "out 15;" in query  # MAX_POIS_PER_LOCATION

    def test_way_elements_queried(self):
        query = _build_overpass_query(47.3, 11.4)
        assert "way[" in query

    def test_empty_categories_handled(self):
        query = _build_overpass_query(47.3, 11.4)
        assert ";" in query
        assert "(" in query


class TestParseOverpassResponse:
    def test_parses_valid_overpass_json(self):
        raw = {
            "elements": [
                {
                    "id": 123,
                    "type": "node",
                    "lat": 47.3,
                    "lon": 11.4,
                    "tags": {
                        "name": "Aussichtspunkt Alpenblick",
                        "tourism": "viewpoint",
                    }
                },
                {
                    "id": 456,
                    "type": "node",
                    "lat": 47.31,
                    "lon": 11.41,
                    "tags": {
                        "name": "Berggipfel",
                        "natural": "peak",
                        "wikipedia": "de:Berggipfel",
                    }
                },
            ]
        }
        results = _parse_overpass_response(raw, ref_lat=47.305, ref_lon=11.405)
        assert len(results) == 2
        assert results[0]["name"] == "Aussichtspunkt Alpenblick"
        assert results[0]["type"] == "viewpoint"
        assert "distance_km" in results[0]
        assert results[1]["wiki_tag"] == "de:Berggipfel"

    def test_handles_empty_response(self):
        results = _parse_overpass_response({"elements": []}, ref_lat=47.3, ref_lon=11.4)
        assert results == []

    def test_handles_missing_name_tag(self):
        raw = {
            "elements": [{
                "id": 789,
                "type": "node",
                "lat": 47.3,
                "lon": 11.4,
                "tags": {"tourism": "viewpoint"},
            }]
        }
        results = _parse_overpass_response(raw, ref_lat=47.3, ref_lon=11.4)
        assert len(results) == 1
        assert "viewpoint" in results[0]["name"]


class TestDeduplicatePois:
    def test_dedup_by_same_name(self):
        pois = [
            {"name": "Alpenblick", "lat": 47.3, "lon": 11.4},
            {"name": "Alpenblick", "lat": 47.31, "lon": 11.41},
            {"name": "Anderer Ort", "lat": 47.5, "lon": 11.6},
        ]
        result = _deduplicate_pois_by_name_and_proximity(pois)
        assert len(result) == 2
        names = {p["name"] for p in result}
        assert "Alpenblick" in names
        assert "Anderer Ort" in names

    def test_dedup_by_proximity(self):
        pois = [
            {"name": "A", "lat": 47.3000, "lon": 11.4000},
            {"name": "B", "lat": 47.3005, "lon": 11.4005},
        ]
        result = _deduplicate_pois_by_name_and_proximity(pois)
        assert len(result) == 1


class TestEnrichWithWikipedia:
    def test_skips_without_wiki_tag(self):
        poi = {"name": "Some Place", "lat": 47.3, "lon": 11.4}
        result = _enrich_with_wikipedia(poi)
        assert result is poi
        assert "wiki_extract" not in result

    def test_fetches_wikipedia_extract(self):
        poi = {"name": "Some Place", "lat": 47.3, "lon": 11.4,
               "wiki_tag": "de:Berggipfel"}
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "extract": "Der Berggipfel ist ein bekannter Aussichtsberg...",
            "title": "Berggipfel",
        }
        with patch("app.services.poi_enricher.requests.get", return_value=mock_resp):
            result = _enrich_with_wikipedia(poi)
            assert result is not poi  # new dict returned
            assert "wiki_extract" in result
            assert "Berggipfel" in result["wiki_extract"]

    def test_handles_wikipedia_failure(self):
        poi = {"name": "Some Place", "lat": 47.3, "lon": 11.4,
               "wiki_tag": "de:Berggipfel"}
        with patch("app.services.poi_enricher.requests.get",
                   side_effect=Exception("Timeout")):
            result = _enrich_with_wikipedia(poi)
            assert "wiki_extract" not in result


class TestCategories:
    def test_categories_dict_is_well_formed(self):
        from app.services.poi_enricher import OVERPASS_POI_CATEGORIES
        assert isinstance(OVERPASS_POI_CATEGORIES, dict)
        assert len(OVERPASS_POI_CATEGORIES) >= 5
        for key, values in OVERPASS_POI_CATEGORIES.items():
            assert isinstance(values, list)
            assert len(values) > 0
            for v in values:
                assert isinstance(v, str)
                assert " " not in v  # OSM-Tags haben keine Leerzeichen


class TestFetchPois:
    def test_returns_empty_without_pauses(self):
        result = fetch_pois(pauses=[])
        assert result == []

    def test_fetches_pois_with_mocked_overpass(self):
        from datetime import datetime
        pauses = [{
            "location": {"lat": 47.3, "lon": 11.4},
            "start_time": datetime(2025, 6, 1, 12, 0),
            "end_time": datetime(2025, 6, 1, 12, 30),
        }]

        mock_overpass_resp = Mock()
        mock_overpass_resp.status_code = 200
        mock_overpass_resp.json.return_value = {
            "elements": [{
                "id": 1, "type": "node", "lat": 47.302, "lon": 11.402,
                "tags": {"name": "Berggipfel", "natural": "peak"},
            }]
        }

        with patch("app.services.poi_enricher.requests.post",
                   return_value=mock_overpass_resp):
            result = fetch_pois(pauses=pauses)
            assert len(result) >= 1
            assert result[0]["name"] == "Berggipfel"

    def test_handles_overpass_failure(self):
        from datetime import datetime
        pauses = [{
            "location": {"lat": 47.3, "lon": 11.4},
        }]
        with patch("app.services.poi_enricher.requests.post",
                   side_effect=Exception("Connection refused")):
            result = fetch_pois(pauses=pauses)
            assert result == []
