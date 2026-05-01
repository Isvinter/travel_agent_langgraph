"""Tests for app/nodes/design_blogpost.py"""
import os
import tempfile
from unittest.mock import patch

from app.nodes.design_blogpost import design_blogpost_node
from app.state import AppState


class TestDesignBlogpostNode:
    def test_returns_unchanged_when_no_blog_post(self):
        state = AppState()
        result = design_blogpost_node(state)
        assert result.blog_post is None

    def test_returns_unchanged_when_blog_post_not_successful(self):
        state = AppState(blog_post={"success": False, "html": "<h1>X</h1>"})
        result = design_blogpost_node(state)
        assert result.blog_post["html"] == "<h1>X</h1>"

    def test_returns_unchanged_when_html_empty(self):
        state = AppState(blog_post={"success": True, "html": ""})
        result = design_blogpost_node(state)
        assert result.blog_post["html"] == ""

    def test_updates_html_when_service_succeeds(self):
        state = AppState(blog_post={
            "success": True,
            "html": "<h1>Old</h1>",
            "markdown": "# Old",
            "file_paths": {},
        })
        styled = "<html><head><style>body{}</style></head><body><h1>Old</h1></body></html>"
        with patch("app.nodes.design_blogpost.design_blogpost_service",
                   return_value=styled):
            result = design_blogpost_node(state)
        assert result.blog_post["html"] == styled
        assert result.blog_post["markdown"] == "# Old"

    def test_keeps_original_html_when_service_raises(self):
        state = AppState(blog_post={
            "success": True,
            "html": "<h1>Old</h1>",
            "markdown": "# Old",
        })
        with patch("app.nodes.design_blogpost.design_blogpost_service",
                   side_effect=Exception("Ollama not reachable")):
            result = design_blogpost_node(state)
        assert result.blog_post["html"] == "<h1>Old</h1>"

    def test_keeps_original_html_when_service_fails(self):
        state = AppState(blog_post={
            "success": True,
            "html": "<h1>Old</h1>",
            "markdown": "# Old",
        })
        with patch("app.nodes.design_blogpost.design_blogpost_service",
                   return_value=None):
            result = design_blogpost_node(state)
        assert result.blog_post["html"] == "<h1>Old</h1>"

    def test_overwrites_html_file_when_service_succeeds(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            html_path = os.path.join(tmpdir, "test.html")
            with open(html_path, "w") as f:
                f.write("<h1>Old</h1>")

            state = AppState(blog_post={
                "success": True,
                "html": "<h1>Old</h1>",
                "markdown": "# Old",
                "file_paths": {"html": html_path, "markdown": "/tmp/nonexistent.md"},
            })
            styled = "<html><head><style>body{}</style></head><body><h1>Old</h1></body></html>"
            with patch("app.nodes.design_blogpost.design_blogpost_service",
                       return_value=styled):
                design_blogpost_node(state)

            with open(html_path, "r") as f:
                content = f.read()
            assert content == styled
