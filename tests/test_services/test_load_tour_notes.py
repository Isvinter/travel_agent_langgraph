"""Tests for app/services/load_tour_notes.py"""
import pytest
from app.services.load_tour_notes import load_tour_notes


class TestLoadTourNotes:
    @pytest.mark.integration
    def test_loads_notes_from_fixtures(self, notes_dir_path):
        result = load_tour_notes(notes_dir_path)
        assert "Abschnitt 1" in result
        assert "Grandiose Aussicht" in result

    @pytest.mark.unit
    def test_returns_empty_for_nonexistent_dir(self):
        result = load_tour_notes("/nonexistent/dir_12345")
        assert result == ""

    @pytest.mark.unit
    def test_returns_empty_for_empty_dir(self, tmp_path):
        result = load_tour_notes(str(tmp_path))
        assert result == ""

    @pytest.mark.unit
    def test_ignores_non_txt_files(self, tmp_path):
        (tmp_path / "readme.md").write_text("markdown content")
        result = load_tour_notes(str(tmp_path))
        assert result == ""
