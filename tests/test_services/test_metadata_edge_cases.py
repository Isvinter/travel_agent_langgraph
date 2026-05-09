"""Edge-Case-Tests für den Metadata Extractor."""
import io

import pytest
from PIL import Image

from app.services.metadata_extractor import extract_metadata, convert_to_decimal_degrees


class TestConvertToDecimalDegrees:
    def test_north_positive(self):
        # EXIF: (40, 26, 46) N
        result = convert_to_decimal_degrees((40.0, 26.0, 46.0), "N")
        assert round(result, 4) == 40.4461

    def test_south_negative(self):
        result = convert_to_decimal_degrees((40.0, 26.0, 46.0), "S")
        assert round(result, 4) == -40.4461

    def test_east_positive(self):
        result = convert_to_decimal_degrees((79.0, 58.0, 56.0), "E")
        assert round(result, 4) == 79.9822

    def test_west_negative(self):
        result = convert_to_decimal_degrees((79.0, 58.0, 56.0), "W")
        assert round(result, 4) == -79.9822

    def test_invalid_ref_returns_value_unchanged(self):
        result = convert_to_decimal_degrees((40.0, 0.0, 0.0), "X")
        assert result == 40.0  # Unbekannte ref → kein Vorzeichenwechsel

    def test_invalid_value_raises_runtime_error(self):
        with pytest.raises(Exception):
            convert_to_decimal_degrees("not-a-tuple", "N")


class TestExtractMetadataEdgeCases:
    def test_image_without_exif(self, tmp_path):
        img_path = tmp_path / "no_exif.jpg"
        Image.new("RGB", (10, 10)).save(img_path, "JPEG")
        result = extract_metadata(str(img_path))
        assert result["timestamp"] is None
        assert result["latitude"] is None
        assert result["longitude"] is None

    def test_corrupted_jpeg(self, tmp_path):
        corrupted = tmp_path / "corrupted.jpg"
        corrupted.write_bytes(b"this is not a valid jpeg at all")
        with pytest.raises(Exception):
            extract_metadata(str(corrupted))

    def test_truncated_jpeg(self, tmp_path):
        truncated = tmp_path / "truncated.jpg"
        img = Image.new("RGB", (10, 10))
        buf = io.BytesIO()
        img.save(buf, "JPEG")
        full_data = buf.getvalue()
        truncated.write_bytes(full_data[:len(full_data) // 2])
        with pytest.raises(Exception):
            extract_metadata(str(truncated))

    def test_png_without_exif(self, tmp_path):
        png = tmp_path / "test.png"
        Image.new("RGB", (10, 10)).save(png, "PNG")
        result = extract_metadata(str(png))
        assert result["latitude"] is None
        assert result["longitude"] is None

    def test_nonexistent_file(self):
        with pytest.raises(FileNotFoundError):
            extract_metadata("/nonexistent/file.jpg")


class TestGermanCharacters:
    """Testet Umlaute und ß in Pfaden und Metadaten."""

    def test_path_with_umlauts(self, tmp_path):
        umlaut_dir = tmp_path / "Fotos_Überlingen_Süßen"
        umlaut_dir.mkdir(exist_ok=True)
        img_path = umlaut_dir / "grünes_foto_äöüß.jpg"
        Image.new("RGB", (10, 10)).save(img_path, "JPEG")
        result = extract_metadata(str(img_path))
        # Sollte nicht crashen
        assert isinstance(result, dict)

    def test_timestamp_with_exif_original_date(self, tmp_path):
        """EXIF DateTimeOriginal im Format '2024:07:15 10:05:00'."""
        import piexif
        img_path = tmp_path / "with_date.jpg"
        img = Image.new("RGB", (10, 10))
        exif_dict = {"0th": {}, "Exif": {}}
        exif_dict["Exif"][piexif.ExifIFD.DateTimeOriginal] = "2024:07:15 10:05:00"
        exif_bytes = piexif.dump(exif_dict)
        img.save(img_path, "JPEG", exif=exif_bytes)
        result = extract_metadata(str(img_path))
        assert result["timestamp"] is not None
        assert "2024" in str(result["timestamp"])

    def test_gps_with_real_exif(self, tmp_path):
        """GPS-Koordinaten aus echten EXIF-Daten."""
        import piexif
        img_path = tmp_path / "with_gps.jpg"
        img = Image.new("RGB", (10, 10))
        exif_dict = {"0th": {}, "Exif": {}, "GPS": {}}
        exif_dict["GPS"][piexif.GPSIFD.GPSLatitude] = ((47, 1), (22, 1), (1200, 100))
        exif_dict["GPS"][piexif.GPSIFD.GPSLatitudeRef] = "N"
        exif_dict["GPS"][piexif.GPSIFD.GPSLongitude] = ((8, 1), (33, 1), (0, 1))
        exif_dict["GPS"][piexif.GPSIFD.GPSLongitudeRef] = "E"
        exif_bytes = piexif.dump(exif_dict)
        img.save(img_path, "JPEG", exif=exif_bytes)
        result = extract_metadata(str(img_path))
        assert result["latitude"] is not None
        assert result["longitude"] is not None
        assert 47.0 < result["latitude"] < 48.0
        assert 8.0 < result["longitude"] < 9.0
