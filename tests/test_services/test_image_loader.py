"""Tests for app/services/image_loader.py"""
import pytest
from app.services.image_loader import load_images_from_directory
from app.state import ImageData


class TestLoadImagesFromDirectory:
    @pytest.mark.integration
    def test_load_images_from_fixtures_dir(self, fixtures_dir):
        images = load_images_from_directory(str(fixtures_dir / "images"))
        assert len(images) == 3
        assert all(isinstance(img, ImageData) for img in images)
        paths = [img.path for img in images]
        assert any("photo_a" in p for p in paths)
        assert any("photo_b" in p for p in paths)
        assert any("photo_c" in p for p in paths)

    @pytest.mark.unit
    def test_empty_directory_returns_empty_list(self, tmp_path):
        images = load_images_from_directory(str(tmp_path))
        assert images == []

    @pytest.mark.unit
    def test_non_image_files_are_ignored(self, tmp_path):
        (tmp_path / "readme.txt").write_text("hello")
        (tmp_path / "notes.md").write_text("notes")
        images = load_images_from_directory(str(tmp_path))
        assert images == []

    @pytest.mark.unit
    def test_nonexistent_directory_returns_empty_list(self):
        images = load_images_from_directory("/nonexistent/dir_12345")
        assert images == []
