"""Tests für den save_draft-Node."""
from unittest.mock import patch
from app.state import AppState, ImageData
from app.services.gpx_analytics import TrackPoint, GPXStats
from datetime import datetime


class TestSaveDraftNode:
    def test_save_draft_persists_article_and_sets_metadata(self):
        from app.nodes.save_draft import save_draft_node

        state = AppState(
            blog_post={"success": True, "markdown": "# Test"},
            selected_images=[ImageData(path="img1.jpg")],
            gpx_file="test.gpx",
            model="test-model",
            notes="Test tour",
        )

        with patch("app.nodes.save_draft.persist_article", return_value=42):
            result = save_draft_node(state)
            assert result.metadata["article_id"] == 42

    def test_save_draft_no_blog_post_does_nothing(self):
        from app.nodes.save_draft import save_draft_node

        state = AppState(blog_post=None)

        with patch("app.nodes.save_draft.persist_article") as mock_persist:
            result = save_draft_node(state)
            mock_persist.assert_not_called()
            assert result is state

    def test_save_draft_handles_persist_failure(self):
        from app.nodes.save_draft import save_draft_node

        state = AppState(
            blog_post={"success": True, "markdown": "# Test"},
            selected_images=[ImageData(path="img1.jpg")],
            gpx_file="test.gpx",
            model="test-model",
        )

        with patch("app.nodes.save_draft.persist_article",
                   side_effect=RuntimeError("DB error")):
            result = save_draft_node(state)
            assert "article_id" not in result.metadata

    def test_save_draft_passes_correct_status(self):
        from app.nodes.save_draft import save_draft_node

        state = AppState(
            blog_post={"success": True, "markdown": "# Test"},
            selected_images=[ImageData(path="img1.jpg")],
            gpx_file="test.gpx",
            model="test-model",
        )

        with patch("app.nodes.save_draft.persist_article", return_value=42) as mock_persist:
            save_draft_node(state)
            call_kwargs = mock_persist.call_args.kwargs
            assert call_kwargs["status"] == "draft"
