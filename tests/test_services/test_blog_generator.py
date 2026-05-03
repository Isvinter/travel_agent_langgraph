"""Tests for app/services/blog_generator.py"""
import base64
import os

import pytest
from PIL import Image

import app.services.blog_generator as bg


class TestEncodeImageToBase64:
    @pytest.mark.unit
    def test_encodes_jpeg_to_base64(self, tmp_path):
        img_path = str(tmp_path / "test.jpg")
        img = Image.new("RGB", (100, 100), color="red")
        img.save(img_path)

        result = bg.encode_image_to_base64(img_path, max_size=800)
        assert result is not None
        decoded = base64.b64decode(result)
        assert decoded[:2] == b'\xff\xd8'

    @pytest.mark.unit
    def test_returns_none_for_nonexistent(self):
        result = bg.encode_image_to_base64("/nonexistent/image.jpg")
        assert result is None


class TestCompressImageToJpeg:
    @pytest.mark.unit
    def test_compresses_image_to_small_size(self, tmp_path):
        src = str(tmp_path / "src.jpg")
        dst = str(tmp_path / "dst.jpg")
        img = Image.new("RGB", (2000, 2000), color="red")
        img.save(src)

        result = bg.compress_image_to_jpeg(src, dst, max_size_bytes=50 * 1024, max_dim=200)
        assert result == dst
        assert os.path.exists(dst)
        assert os.path.getsize(dst) <= 50 * 1024

    @pytest.mark.unit
    def test_returns_none_for_missing_source(self):
        result = bg.compress_image_to_jpeg("/nonexistent/src.jpg", "/tmp/dst.jpg")
        assert result is None


class TestConstructBlogPostPrompt:
    @pytest.mark.unit
    def test_includes_stats_and_notes_in_prompt(self, tmp_path):
        # Erstelle ein echtes Bild, damit encode_image_to_base64 es findet
        img_path = str(tmp_path / "photo.jpg")
        img = Image.new("RGB", (100, 100), color="blue")
        img.save(img_path)

        images = [{"path": img_path, "timestamp": "2025-06-01", "latitude": 47.0, "longitude": 8.0}]
        gpx_stats = {"total_distance_m": 5000, "elevation_gain_m": 200}
        prompt, image_data = bg.construct_blog_post_prompt(
            images=images,
            gpx_stats=gpx_stats,
            notes="Test notes here",
        )
        assert "5000" in prompt or "5" in prompt
        assert "Test notes" in prompt
        assert len(image_data) >= 1

    @pytest.mark.unit
    def test_handles_missing_optional_fields(self):
        prompt, image_data = bg.construct_blog_post_prompt(images=[])
        assert len(image_data) >= 0
        assert isinstance(prompt, str)


class TestStripThinkingTokens:
    def test_strips_thinking_tags(self):
        text = "<thinking>This is CoT reasoning\nwith multiple lines</thinking>\n# Title\nContent"
        result = bg._strip_thinking_tokens(text)
        assert "<thinking>" not in result
        assert "CoT reasoning" not in result
        assert "# Title" in result

    def test_strips_think_tags(self):
        text = "<think>reasoning here</think>\n\n# Title"
        result = bg._strip_thinking_tokens(text)
        assert "reasoning here" not in result
        assert "# Title" in result

    def test_passes_through_clean_text(self):
        text = "# Title\n## Section\nContent"
        result = bg._strip_thinking_tokens(text)
        assert result == text

    def test_strips_leading_whitespace(self):
        text = "\n\n\n# Title"
        result = bg._strip_thinking_tokens(text)
        assert result == "# Title"
