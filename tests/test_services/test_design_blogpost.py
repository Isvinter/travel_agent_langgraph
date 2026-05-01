"""Tests for app/services/design_blogpost.py"""
import json
from unittest.mock import patch, Mock

import pytest

from app.services.design_blogpost import (
    design_blogpost_service,
    _build_design_prompt,
    _call_ollama_text,
    _extract_styled_html,
)


class TestBuildDesignPrompt:
    def test_includes_role_and_constraints(self):
        html_body = "<h1>Test Title</h1><p>Some content</p>"
        prompt = _build_design_prompt(html_body)

        assert "Web-Designer" in prompt
        assert "Reiseblogs" in prompt
        assert "NICHT verändert" in prompt
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
                   side_effect=Exception("Connection refused")):
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
        html = "<html><body><h1>No CSS</h1></body></html>"
        result = _extract_styled_html(html)
        assert result is None


class TestDesignBlogpostServiceIntegration:
    def test_returns_styled_html(self):
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "message": {
                "content": (
                    "<!DOCTYPE html>\n<html>\n<head>\n"
                    "<meta charset='utf-8'>\n"
                    "<style>body{font-family:serif;max-width:800px}</style>\n"
                    "</head>\n<body>\n<h1>Test</h1>\n<p>Content</p>\n</body>\n</html>"
                ),
            },
        }

        with patch("requests.post", return_value=mock_resp):
            result = design_blogpost_service(
                html_body="<h1>Test</h1><p>Content</p>",
                model="gemma4:26b-ctx128k",
            )
        assert result is not None
        assert "<style>" in result
        assert "font-family" in result
        assert "<h1>Test</h1>" in result

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
            "message": {"content": "<h1>Just content, no CSS</h1>"},
        }

        with patch("requests.post", return_value=mock_resp):
            result = design_blogpost_service(
                html_body="<h1>Test</h1>",
                model="gemma4:26b-ctx128k",
            )
        assert result is None
