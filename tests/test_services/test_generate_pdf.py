"""Tests for app/services/generate_pdf.py"""
import pytest


class TestRewriteImagePaths:
    """Unit tests for HTML path rewriting (no Chrome needed)."""

    def test_rewrites_relative_image_paths_to_file_urls(self):
        """./images/ Pfade werden zu file:/// Pfaden umgeschrieben."""
        from app.services.generate_pdf import _rewrite_html_for_pdf

        html = '<img src="./images/photo.jpg" alt="Foto"><img src="./images/map.png">'
        result = _rewrite_html_for_pdf(html, "/home/user/output/2026-05-04")

        assert 'src="file:///home/user/output/2026-05-04/images/photo.jpg"' in result
        assert 'src="file:///home/user/output/2026-05-04/images/map.png"' in result
        assert "./images/" not in result

    def test_rewrites_max_width_for_print(self):
        from app.services.generate_pdf import _rewrite_html_for_pdf

        html = '<style>body { max-width: 780px; }</style>'
        result = _rewrite_html_for_pdf(html, "/tmp")

        assert "max-width: 100%" in result
        assert "max-width: 780px" not in result

    def test_injects_print_page_css(self):
        from app.services.generate_pdf import _rewrite_html_for_pdf

        html = '<html><head></head><body>Hallo</body></html>'
        result = _rewrite_html_for_pdf(html, "/tmp")

        assert "@page { size: A4; margin: 15mm; }" in result

    def test_handles_none_html(self):
        from app.services.generate_pdf import _rewrite_html_for_pdf

        result = _rewrite_html_for_pdf(None, "/tmp")
        assert result is None

    def test_handles_empty_html(self):
        from app.services.generate_pdf import _rewrite_html_for_pdf

        result = _rewrite_html_for_pdf("", "/tmp")
        assert result == ""

    def test_output_dir_none_uses_cwd(self):
        from app.services.generate_pdf import _rewrite_html_for_pdf

        html = '<img src="./images/photo.jpg">'
        result = _rewrite_html_for_pdf(html, None)

        # Sollte file:/// mit CWD-Absolutpfad enthalten
        assert "file:///" in result
        assert "images/photo.jpg" in result

    def test_injects_css_when_no_head_tag(self):
        from app.services.generate_pdf import _rewrite_html_for_pdf

        html = '<html><body>Hallo</body></html>'
        result = _rewrite_html_for_pdf(html, "/tmp")

        assert "@page { size: A4; margin: 15mm; }" in result
        assert "</head>" not in result  # kein head-tag drin
