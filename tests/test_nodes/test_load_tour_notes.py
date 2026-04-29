"""Tests for app/nodes/load_tour_notes_node.py"""
from unittest.mock import patch
from app.nodes.load_tour_notes_node import load_tour_notes_node
from app.state import AppState


class TestLoadTourNotesNode:
    def test_loads_notes_into_state(self):
        state = AppState(notes=None)
        with patch("app.nodes.load_tour_notes_node.load_tour_notes", return_value="Sample notes"):
            result = load_tour_notes_node(state)
            assert result.notes == "Sample notes"

    def test_empty_notes_set_to_none(self):
        state = AppState(notes=None)
        with patch("app.nodes.load_tour_notes_node.load_tour_notes", return_value=""):
            result = load_tour_notes_node(state)
            assert result.notes is None
