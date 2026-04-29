"""Tests for app/services/metadata_extractor.py"""
import pytest
from app.services.metadata_extractor import (
    extract_metadata,
    convert_to_decimal_degrees,
)


class TestConvertToDecimalDegrees:
    def test_convert_north_positive(self):
        result = convert_to_decimal_degrees((47.0, 20.0, 12.0), "N")
        assert result == pytest.approx(47.336666666666666)

    def test_convert_south_negative(self):
        result = convert_to_decimal_degrees((47.0, 20.0, 12.0), "S")
        assert result == pytest.approx(-47.336666666666666)

    def test_convert_west_negative(self):
        result = convert_to_decimal_degrees((8.0, 30.0, 0.0), "W")
        assert result == pytest.approx(-8.5)


class TestExtractMetadata:
    @pytest.mark.integration
    def test_extract_from_jpeg_with_exif(self, fixtures_dir):
        path = str(fixtures_dir / "images" / "photo_a.jpg")
        meta = extract_metadata(path)
        assert meta["latitude"] is not None
        assert meta["longitude"] is not None
        assert meta["timestamp"] is not None

    @pytest.mark.integration
    def test_extract_from_jpeg_without_exif(self, tmp_path):
        from PIL import Image
        path = str(tmp_path / "no_exif.jpg")
        img = Image.new("RGB", (100, 100), color="red")
        img.save(path)
        meta = extract_metadata(path)
        assert meta["latitude"] is None
        assert meta["longitude"] is None

    @pytest.mark.integration
    def test_extract_from_nonexistent_file(self):
        with pytest.raises(FileNotFoundError):
            extract_metadata("/nonexistent/file.jpg")
