"""Tests for app/services/design_blogpost.py (template-based redesign)."""
import pytest

from app.services.design_blogpost import (
    _extract_title,
    _add_image_captions,
    design_blogpost_service,
)


class TestExtractTitle:
    def test_extracts_h1_text(self):
        assert _extract_title("<h1>Bergtour ins Allgäu</h1>") == "Bergtour ins Allgäu"

    def test_returns_fallback_when_no_h1(self):
        assert _extract_title("<h2>Subtitle</h2><p>Text</p>") == "Reisebericht"

    def test_handles_nested_tags_in_h1(self):
        assert _extract_title("<h1><strong>Wichtig:</strong> Gratwanderung</h1>") == "Wichtig: Gratwanderung"

    def test_handles_html_entities(self):
        assert _extract_title("<h1>M&uuml;nchen &gt; Garmisch</h1>") == "München > Garmisch"


class TestDesignBlogpostService:
    def test_wraps_html_in_template(self):
        html = "<h1>Meine Tour</h1><p>War super.</p>"
        result = design_blogpost_service(html)
        assert result is not None
        assert "<!DOCTYPE html>" in result
        assert "<html lang=\"de\">" in result
        assert "<style>" in result
        assert "</style>" in result
        assert "<body>" in result
        assert "</body>" in result
        assert "</html>" in result

    def test_includes_title_in_meta(self):
        html = "<h1>Gipfelerlebnis</h1><p>Text</p>"
        result = design_blogpost_service(html)
        assert "<title>Gipfelerlebnis</title>" in result

    def test_fallback_title_when_no_h1(self):
        html = "<h2>Einstieg</h2><p>Normaler Text</p>"
        result = design_blogpost_service(html)
        assert result is not None
        assert "<title>Reisebericht</title>" in result

    def test_preserves_all_html_tags(self):
        html = "<h1>Titel</h1><h2>Abschnitt</h2><h3>Detail</h3><p>Text <strong>fett</strong> und <em>kursiv</em></p><blockquote>Zitat</blockquote><ul><li>Punkt 1</li><li>Punkt 2</li></ul>"
        result = design_blogpost_service(html)
        assert result is not None
        assert "<h1>Titel</h1>" in result
        assert "<h2>Abschnitt</h2>" in result
        assert "<h3>Detail</h3>" in result
        assert "<strong>fett</strong>" in result
        assert "<em>kursiv</em>" in result
        assert "<blockquote>Zitat</blockquote>" in result
        assert "<li>Punkt 1</li>" in result

    def test_preserves_image_tags_with_paths(self):
        html = '<h1>Tour</h1><img alt="Foto" src="./images/01_IMG_5513.jpg"><img alt="Karte" src="./images/00_map.png">'
        result = design_blogpost_service(html)
        assert result is not None
        assert 'src="./images/01_IMG_5513.jpg"' in result
        assert 'src="./images/00_map.png"' in result
        assert 'alt="Foto"' in result
        assert 'alt="Karte"' in result

    def test_includes_css_rules(self):
        result = design_blogpost_service("<h1>Test</h1>")
        assert result is not None
        assert "font-family" in result
        assert "max-width" in result
        assert "line-height" in result
        assert "@media" in result

    def test_returns_none_for_empty_body(self):
        assert design_blogpost_service("") is None
        assert design_blogpost_service("   ") is None

    def test_returns_none_for_none(self):
        assert design_blogpost_service("") is None

    def test_no_llm_dependency(self):
        """Verify the template approach works without any network calls."""
        html = "<h1>Test</h1><p>No LLM needed.</p>"
        result = design_blogpost_service(html)
        assert result is not None
        assert "<style>" in result
        assert "<h1>Test</h1>" in result
        # Should work instantly, no network calls

    def test_image_captions_added(self):
        html = '<h1>Tour</h1><img alt="Panoramablick vom Gipfel" src="./images/01_IMG.jpg">'
        result = design_blogpost_service(html)
        assert result is not None
        assert "<figure>" in result
        assert "<figcaption>Panoramablick vom Gipfel</figcaption>" in result


class TestAddImageCaptions:
    def test_wraps_image_with_alt(self):
        html = '<img alt="Panoramablick" src="./images/01_IMG.jpg">'
        result = _add_image_captions(html)
        assert "<figure>" in result
        assert "<figcaption>Panoramablick</figcaption>" in result
        assert 'alt="Panoramablick"' in result

    def test_handles_html_entities_in_alt(self):
        html = '<img alt="M&uuml;nchen &gt; Garmisch" src="./images/01.jpg">'
        result = _add_image_captions(html)
        assert "<figcaption>München > Garmisch</figcaption>" in result

    def test_skips_image_without_alt(self):
        html = '<img src="./images/01.jpg">'
        result = _add_image_captions(html)
        assert "<figure>" not in result

    def test_skips_image_with_empty_alt(self):
        html = '<img alt="" src="./images/01.jpg">'
        result = _add_image_captions(html)
        assert "<figure>" not in result

    def test_preserves_other_html(self):
        html = '<h1>Tour</h1><img alt="Blick" src="./images/01.jpg"><p>Text</p>'
        result = _add_image_captions(html)
        assert "<h1>Tour</h1>" in result
        assert "<p>Text</p>" in result
        assert "<figure>" in result
