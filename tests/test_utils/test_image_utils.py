"""Tests für die gemeinsame Bildkompressions-Utility."""
import os
import pytest
from PIL import Image
from app.utils.image_utils import compress_image_to_jpeg


class TestCompressImageToJpeg:
    """Unit tests für compress_image_to_jpeg aus dem shared utility."""

    @pytest.mark.unit
    def test_compresses_image_to_small_size(self, tmp_path):
        """Ein 2000x2000 Bild muss auf ≤50KB komprimiert werden."""
        src = str(tmp_path / "src.jpg")
        dst = str(tmp_path / "dst.jpg")
        img = Image.new("RGB", (2000, 2000), color="red")
        img.save(src)

        result = compress_image_to_jpeg(src, dst, max_size_bytes=50 * 1024, max_dim=200)
        assert result == dst
        assert os.path.exists(dst)
        assert os.path.getsize(dst) <= 50 * 1024

    @pytest.mark.unit
    def test_returns_none_for_missing_source(self):
        """Nonexistente Quelle gibt None zurück."""
        result = compress_image_to_jpeg("/nonexistent/src.jpg", "/tmp/dst.jpg")
        assert result is None

    @pytest.mark.unit
    def test_output_is_jpeg_rgb(self, tmp_path):
        """Output muss JPEG und RGB sein."""
        src = str(tmp_path / "src.png")
        dst = str(tmp_path / "dst.jpg")
        img = Image.new("RGBA", (400, 300), color=(255, 0, 0, 128))
        img.save(src)

        result = compress_image_to_jpeg(src, dst, max_size_bytes=500 * 1024, max_dim=400)
        assert result == dst
        with Image.open(dst) as out:
            assert out.mode == "RGB"
            assert out.format == "JPEG"

    @pytest.mark.unit
    def test_max_dimension_enforced(self, tmp_path):
        """Output-Dimension darf max_dim nicht überschreiten."""
        src = str(tmp_path / "src.jpg")
        dst = str(tmp_path / "dst.jpg")
        img = Image.new("RGB", (3000, 1000), color="blue")
        img.save(src)

        result = compress_image_to_jpeg(src, dst, max_size_bytes=5 * 1024 * 1024, max_dim=600)
        assert result == dst
        with Image.open(dst) as out:
            assert max(out.size) <= 600

    @pytest.mark.unit
    def test_creates_output_directory_if_missing(self, tmp_path):
        """Sollte das Output-Verzeichnis nicht automatisch erstellen — Aufrufer ist verantwortlich."""
        src = str(tmp_path / "src.jpg")
        dst_dir = str(tmp_path / "nested" / "subdir")
        dst = os.path.join(dst_dir, "dst.jpg")
        img = Image.new("RGB", (100, 100), color="green")
        img.save(src)

        result = compress_image_to_jpeg(src, dst, max_size_bytes=500 * 1024, max_dim=100)
        assert result is None  # Verzeichnis existiert nicht → Fehler

    @pytest.mark.unit
    def test_encode_image_base64_returns_base64_string(self, tmp_path):
        """encode_image_base64 muss einen validen Base64-String zurückgeben."""
        from app.utils.image_utils import encode_image_base64
        src = str(tmp_path / "src.jpg")
        img = Image.new("RGB", (1200, 800), color="blue")
        img.save(src)

        result = encode_image_base64(src, max_size=600)
        assert result is not None
        assert isinstance(result, str)
        import re
        assert re.match(r'^[A-Za-z0-9+/]+=*$', result) is not None

    @pytest.mark.unit
    def test_encode_image_base64_returns_none_for_missing_file(self):
        """Nonexistente Datei gibt None zurück."""
        from app.utils.image_utils import encode_image_base64
        result = encode_image_base64("/nonexistent/img.jpg")
        assert result is None
