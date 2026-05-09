"""Tests für Draft-Persistenz (save_draft Node + status-Feld)."""
from unittest.mock import MagicMock, patch
from app.services.persist_article import persist_article
from app.state import BlogPostResult


class TestPersistArticleStatus:
    def test_persist_article_default_status_is_published(self):
        """Bei Aufruf ohne status-Parameter wird 'published' verwendet."""
        blog_post = BlogPostResult(
            success=True,
            markdown="# Test\n\nEin Absatz.",
            html="<h1>Test</h1><p>Ein Absatz.</p>",
            file_paths={"markdown": "out/test.md", "html": "out/test.html"},
            selected_images=[],
        )

        with patch("app.services.persist_article.get_session") as mock_session:
            mock_session.return_value = MagicMock()
            mock_repo = MagicMock()
            mock_repo.insert.return_value = 42
            with patch("app.services.persist_article.ArticleRepository", return_value=mock_repo):
                result = persist_article(
                    blog_post=blog_post,
                    gpx_stats=None,
                    images=[],
                    gpx_file="test.gpx",
                    model="test-model",
                    notes=None,
                )
                assert result == 42
                call_data = mock_repo.insert.call_args[0][0]
                assert call_data["status"] == "published"
                assert call_data["revision_round"] == 0

    def test_persist_article_draft_status(self):
        """Bei Aufruf mit status='draft' wird dieser Status persistiert."""
        blog_post = BlogPostResult(
            success=True,
            markdown="# Test\n\nEin Absatz.",
            html="<h1>Test</h1><p>Ein Absatz.</p>",
            file_paths={},
            selected_images=[],
        )

        with patch("app.services.persist_article.get_session") as mock_session:
            mock_session.return_value = MagicMock()
            mock_repo = MagicMock()
            mock_repo.insert.return_value = 42
            with patch("app.services.persist_article.ArticleRepository", return_value=mock_repo):
                result = persist_article(
                    blog_post=blog_post,
                    gpx_stats=None,
                    images=[],
                    gpx_file="test.gpx",
                    model="test-model",
                    notes=None,
                    status="draft",
                )
                assert result == 42
                call_data = mock_repo.insert.call_args[0][0]
                assert call_data["status"] == "draft"

    def test_persist_article_unsuccessful_blog_post_returns_none(self):
        result = persist_article(
            blog_post=BlogPostResult(success=False),
            gpx_stats=None,
            images=[],
            gpx_file="",
            model="",
            notes=None,
        )
        assert result is None
