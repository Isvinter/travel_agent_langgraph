"""Tests for app/services/image_selector.py"""
import pytest
from app.services.image_selector import _parse_selection, select_images_for_blog


class TestParseSelection:
    def test_parses_comma_separated_indices(self):
        result = _parse_selection("0, 2, 5", max_index=10)
        assert result == [0, 2, 5]

    def test_deduplicates(self):
        result = _parse_selection("1,1,3,3", max_index=10)
        assert result == [1, 3]

    def test_filters_out_of_range(self):
        result = _parse_selection("0, 15, 20", max_index=10)
        assert result == [0]

    def test_handles_newlines_and_spaces(self):
        result = _parse_selection("0\n 1 , 2", max_index=5)
        assert result == [0, 1, 2]

    def test_returns_empty_for_non_numeric(self):
        result = _parse_selection("abc, def", max_index=10)
        assert result == []


class TestSelectImagesForBlog:
    def test_returns_all_when_fewer_than_target(self):
        images = [{"path": "a.jpg"}, {"path": "b.jpg"}]
        result = select_images_for_blog(images, target_count=8)
        assert len(result) == 2

    def test_fallback_when_no_ollama_available(self):
        images = [{"path": f"img{i}.jpg"} for i in range(20)]
        result = select_images_for_blog(
            images,
            target_count=8,
            model="gemma4:26b-ctx128k",
            base_url="http://localhost:99999",
        )
        assert len(result) <= 8
        assert len(result) >= 1
