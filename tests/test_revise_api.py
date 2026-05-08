"""Tests für die /revise und /publish API-Endpoints."""


class TestReviseApi:
    def test_revise_article_not_found(self, test_client):
        res = test_client.post("/api/articles/99999/revise", json={"changes": []})
        assert res.status_code == 404

    def test_revise_article_not_a_draft(self, test_client, test_session):
        """Artikel mit status='published' kann nicht revidiert werden."""
        from app.db.repository import ArticleRepository
        repo = ArticleRepository(test_session)
        article_id = repo.insert(
            {"title": "Test", "status": "published", "model_used": "gemma4", "revision_round": 0},
            []
        )
        try:
            res = test_client.post(
                f"/api/articles/{article_id}/revise",
                json={"changes": [{"element_type": "paragraph", "element_index": 0, "original_content": "test", "instruction": "rewrite"}]}
            )
            assert res.status_code == 400
            data = res.json()
            assert "not a draft" in data["detail"].lower()
        finally:
            repo.delete(article_id)

    def test_publish_article_not_found(self, test_client):
        res = test_client.post("/api/articles/99999/publish")
        assert res.status_code == 404

    def test_publish_article_success(self, test_client, test_session):
        """Draft wird erfolgreich veröffentlicht."""
        from app.db.repository import ArticleRepository
        repo = ArticleRepository(test_session)
        article_id = repo.insert(
            {"title": "Test Draft", "status": "draft", "model_used": "gemma4", "revision_round": 0},
            []
        )
        try:
            res = test_client.post(f"/api/articles/{article_id}/publish")
            assert res.status_code == 200
            data = res.json()
            assert data["status"] == "published"
            assert data["article_id"] == article_id
        finally:
            repo.delete(article_id)
