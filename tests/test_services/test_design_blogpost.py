"""Tests for app/services/design_blogpost.py"""
from unittest.mock import patch, Mock
from requests.exceptions import ConnectionError

import pytest

from app.services.design_blogpost import (
    design_blogpost_service,
    _alias_image_paths,
    _restore_image_paths,
    _build_design_prompt,
    _call_ollama_text,
    _extract_styled_html,
)


class TestAliasImagePaths:
    def test_aliases_map_and_elevation(self):
        html = '<p>Text</p><img alt="Map" src="./images/00_map.png"><img alt="Elev" src="./images/00_elevation_profile.png">'
        aliased, rev_map = _alias_image_paths(html)
        assert 'src="MAP"' in aliased
        assert 'src="ELEV"' in aliased
        assert rev_map["MAP"] == "./images/00_map.png"
        assert rev_map["ELEV"] == "./images/00_elevation_profile.png"

    def test_aliases_numbered_images(self):
        html = '<img src="./images/01_IMG_5513.jpg"><img src="./images/02_IMG_5515.jpg"><img src="./images/12_IMG_5538.jpg">'
        aliased, rev_map = _alias_image_paths(html)
        assert 'src="IMG_01"' in aliased
        assert 'src="IMG_02"' in aliased
        assert 'src="IMG_12"' in aliased
        assert rev_map["IMG_01"] == "./images/01_IMG_5513.jpg"
        assert rev_map["IMG_02"] == "./images/02_IMG_5515.jpg"
        assert rev_map["IMG_12"] == "./images/12_IMG_5538.jpg"

    def test_aliases_no_images(self):
        html = "<h1>Title</h1><p>Text</p>"
        aliased, rev_map = _alias_image_paths(html)
        assert aliased == html
        assert rev_map == {}

    def test_restore_paths(self):
        styled = '<body><h1>Hi</h1><img alt="X" src="IMG_01"><img alt="Y" src="MAP"></body>'
        rev_map = {"IMG_01": "./images/01_IMG_5513.jpg", "MAP": "./images/00_map.png"}
        restored = _restore_image_paths(styled, rev_map)
        assert 'src="./images/01_IMG_5513.jpg"' in restored
        assert 'src="./images/00_map.png"' in restored
        assert 'src="IMG_01"' not in restored
        assert 'src="MAP"' not in restored


class TestBuildDesignPrompt:
    def test_includes_role_and_constraints(self):
        html_body = "<h1>Test Title</h1><p>Some content</p>"
        prompt = _build_design_prompt(html_body)

        assert "Web-Designer" in prompt
        assert "Reiseblogs" in prompt
        assert "SCHEMA-INTEGRITÄT" in prompt
        assert "STRENG VERBOTEN" in prompt
        assert "<h1> oder <h2> oder <h3> in <p>" in prompt
        assert "<style>" in prompt
        assert "kein JavaScript" in prompt
        assert "---CONTENT---" in prompt
        assert "<h1>Test Title</h1>" in prompt

    def test_appends_content_after_delimiter(self):
        html_body = "<p>Hello world</p>"
        prompt = _build_design_prompt(html_body)

        parts = prompt.split("---CONTENT---")
        assert len(parts) == 2
        assert parts[1].strip() == "<p>Hello world</p>"


class TestCallOllamaText:
    def test_returns_content_on_success(self):
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "message": {"content": "<html><head><style>body{}</style></head><body><h1>Hi</h1></body></html>"},
        }

        with patch("requests.post", return_value=mock_resp):
            result = _call_ollama_text(
                prompt="Make it pretty",
                model="gemma4:26b-ctx128k",
            )
        assert result is not None
        assert "<html>" in result
        assert "<style>" in result

    def test_returns_none_on_connection_error(self):
        with patch("requests.post",
                   side_effect=ConnectionError("Connection refused")):
            result = _call_ollama_text(
                prompt="Make it pretty",
                model="gemma4:26b-ctx128k",
            )
        assert result is None

    def test_returns_none_on_non_200(self):
        mock_resp = Mock()
        mock_resp.status_code = 500
        mock_resp.text = "Internal server error"

        with patch("requests.post", return_value=mock_resp):
            result = _call_ollama_text(
                prompt="Make it pretty",
                model="gemma4:26b-ctx128k",
            )
        assert result is None


class TestExtractStyledHtml:
    def test_passes_through_valid_html_with_style(self):
        html = (
            "<!DOCTYPE html><html lang='de'><head><meta charset='utf-8'><title>Test</title>"
            "<style>body{color:red;font-family:sans-serif}</style></head>"
            "<body><h1>Hi</h1><p>Lorem ipsum dolor sit amet.</p></body></html>"
        )
        result = _extract_styled_html(html)
        assert result == html

    def test_returns_none_for_empty_string(self):
        assert _extract_styled_html("") is None

    def test_returns_none_for_too_short_response(self):
        assert _extract_styled_html("short") is None

    def test_returns_none_if_no_style_tag(self):
        html = "<html><head></head><body><h1>No CSS</h1></body></html>"
        result = _extract_styled_html(html)
        assert result is None

    def test_returns_none_if_no_body_tag(self):
        html = ("<html><head><style>body{color:red;font-family:serif;margin:0;"
                "padding:0;line-height:1.8;max-width:800px}</style></head></html>")
        result = _extract_styled_html(html)
        assert result is None

    def test_strips_markdown_html_fence(self):
        html = ("<html><head><meta charset='utf-8'><title>T</title>"
                "<style>body{color:red;font-family:serif}</style></head>"
                "<body><h1>Hi</h1><p>Content here.</p></body></html>")
        fenced = f"```html\n{html}\n```"
        result = _extract_styled_html(fenced)
        assert result == html

    def test_strips_markdown_plain_fence(self):
        html = ("<html><head><meta charset='utf-8'><title>T</title>"
                "<style>body{color:red;font-family:serif}</style></head>"
                "<body><h1>Hi</h1><p>Content here.</p></body></html>")
        fenced = f"```\n{html}\n```"
        result = _extract_styled_html(fenced)
        assert result == html


class TestDesignBlogpostServiceIntegration:
    def test_returns_styled_html_with_restored_image_paths(self):
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "message": {
                "content": (
                    "<!DOCTYPE html>\n<html>\n<head>\n"
                    "<meta charset='utf-8'>\n"
                    "<style>body{font-family:serif;max-width:800px}</style>\n"
                    "</head>\n<body>\n<h1>Test</h1>\n"
                    "<img alt=\"Foto\" src=\"IMG_01\">\n"
                    "<img alt=\"Karte\" src=\"MAP\">\n"
                    "<p>Content</p>\n</body>\n</html>"
                ),
            },
        }

        with patch("requests.post", return_value=mock_resp):
            result = design_blogpost_service(
                html_body=(
                    "<h1>Test</h1>"
                    '<img alt="Foto" src="./images/01_IMG_5513.jpg">'
                    '<img alt="Karte" src="./images/00_map.png">'
                    "<p>Content</p>"
                ),
                model="gemma4:26b-ctx128k",
            )
        assert result is not None
        assert "<style>" in result
        assert "font-family" in result
        assert 'src="./images/01_IMG_5513.jpg"' in result
        assert 'src="./images/00_map.png"' in result
        # Keine Alias-Reste
        assert 'src="IMG_01"' not in result
        assert 'src="MAP"' not in result

    def test_returns_none_when_ollama_fails(self):
        with patch("requests.post",
                   side_effect=Exception("Connection refused")):
            result = design_blogpost_service(
                html_body="<h1>Test</h1>",
                model="gemma4:26b-ctx128k",
            )
        assert result is None

    def test_returns_none_when_response_lacks_style(self):
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "message": {"content": "<html><body><h1>Just content, no CSS</h1></body></html>"},
        }

        with patch("requests.post", return_value=mock_resp):
            result = design_blogpost_service(
                html_body="<h1>Test</h1>",
                model="gemma4:26b-ctx128k",
            )
        assert result is None
