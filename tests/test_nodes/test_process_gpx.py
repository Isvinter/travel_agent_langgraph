"""Tests for app/nodes/process_gpx.py"""
import pytest
from app.nodes.process_gpx import process_gpx_node
from app.state import AppState


class TestProcessGpxNode:
    def test_processes_fixture_gpx(self, sample_gpx_path):
        state = AppState(gpx_file=sample_gpx_path)
        result = process_gpx_node(state)

        assert result.gpx_stats is not None
        assert result.gpx_stats.total_distance_m > 0
        assert "distance_km" in result.metadata

    def test_no_gpx_file_returns_unchanged(self):
        state = AppState(gpx_file="")
        result = process_gpx_node(state)
        assert result.gpx_stats is None
        assert result.metadata == {}

    def test_handles_nonexistent_file(self):
        state = AppState(gpx_file="/nonexistent/tour.gpx")
        with pytest.raises(FileNotFoundError):
            process_gpx_node(state)
