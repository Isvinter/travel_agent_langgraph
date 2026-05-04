"""Tests for app/api/routes.py and app/api/events.py"""
import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.server import create_app
from app.api.events import event_manager, PipelineEventManager


@pytest.fixture
def client():
    """Return a FastAPI TestClient with a fresh app instance."""
    app = create_app()
    return TestClient(app)


@pytest.fixture
def session_cookie():
    """Return a dict with a test session_id cookie."""
    return {"session_id": "test-session-abc"}


class TestModelsEndpoint:
    def test_returns_model_list(self, client):
        response = client.get("/api/models")
        assert response.status_code == 200
        data = response.json()
        assert "models" in data
        assert "gemma4:26b-ctx128k" in data["models"]

    def test_models_list_is_nonempty(self, client):
        response = client.get("/api/models")
        assert len(response.json()["models"]) >= 1


class TestFileUpload:
    @pytest.fixture(autouse=True)
    def setup_uploads_dir(self):
        """Ensure uploads dir exists and is clean for the test session."""
        from app.api.routes import UPLOADS_DIR
        session_dir = UPLOADS_DIR / "test-session-abc"
        session_dir.mkdir(parents=True, exist_ok=True)
        yield
        # Cleanup
        import shutil
        if session_dir.exists():
            shutil.rmtree(session_dir)

    def test_upload_accepted_file(self, client, session_cookie):
        response = client.post(
            "/api/files/upload",
            files={"file": ("test.gpx", b"<gpx></gpx>", "application/gpx+xml")},
            cookies=session_cookie,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["filename"] == "test.gpx"
        assert "uploads/test-session-abc/test.gpx" in data["path"]

    def test_upload_without_session_cookie_fails(self, client):
        response = client.post(
            "/api/files/upload",
            files={"file": ("test.gpx", b"<gpx></gpx>", "application/gpx+xml")},
        )
        assert response.status_code == 400

    def test_delete_uploaded_file(self, client, session_cookie):
        # Upload first
        client.post(
            "/api/files/upload",
            files={"file": ("to_delete.txt", b"hello", "text/plain")},
            cookies=session_cookie,
        )
        # Delete
        response = client.delete("/api/files/to_delete.txt", cookies=session_cookie)
        assert response.status_code == 200
        assert response.json()["deleted"] == "to_delete.txt"

    def test_delete_nonexistent_file(self, client, session_cookie):
        response = client.delete("/api/files/nonexistent.txt", cookies=session_cookie)
        assert response.status_code == 404


class TestPipelineRun:
    def test_run_without_gpx_fails(self, client):
        response = client.post("/api/pipeline/run", json={
            "model": "gemma4:26b-ctx128k",
            "gpx_file": "",
            "image_files": [],
        })
        assert response.status_code == 422

    def test_run_with_gpx_returns_run_id(self, client):
        response = client.post("/api/pipeline/run", json={
            "model": "gemma4:26b-ctx128k",
            "gpx_file": "tests/fixtures/nonexistent.gpx",
            "image_files": [],
        })
        assert response.status_code == 200
        data = response.json()
        assert "run_id" in data
        assert len(data["run_id"]) == 36  # UUID length

    def test_unknown_run_result_returns_404(self, client):
        response = client.get("/api/pipeline/result/nonexistent-id")
        assert response.status_code == 404


class TestEventManager:
    def test_create_and_get_result(self):
        mgr = PipelineEventManager()
        mgr._runs["test-run"] = type("Queue", (), {"put_nowait": lambda s, e: None})()
        mgr.store_result("test-run", {"success": True, "markdown": "# Hello"})
        result = mgr.get_result("test-run")
        assert result["success"] is True
        assert result["markdown"] == "# Hello"

    def test_get_result_missing_returns_none(self):
        mgr = PipelineEventManager()
        assert mgr.get_result("nonexistent") is None


class TestArticlesList:
    def test_list_empty_returns_empty_array(self, monkeypatch):
        import os
        import tempfile
        from app.db import connection as conn_module
        from app.db.models import Base
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker as sm

        tmp = tempfile.mktemp(suffix=".db")
        try:
            engine = create_engine(f"sqlite:///{tmp}", echo=False)
            Base.metadata.create_all(engine)

            factory = sm(bind=engine)
            monkeypatch.setattr(conn_module, "_engine", engine)
            monkeypatch.setattr(conn_module, "_SessionLocal", factory)
            monkeypatch.setattr(conn_module, "get_session", factory)

            from app.api.server import create_app
            from fastapi.testclient import TestClient
            app = create_app()
            import app.api.routes as routes_mod
            monkeypatch.setattr(routes_mod, "get_session", factory)
            client = TestClient(app)

            response = client.get("/api/articles")
            assert response.status_code == 200
            data = response.json()
            assert data["articles"] == []
            assert data["total"] == 0
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def test_list_with_filters(self, monkeypatch):
        """Testet GET /api/articles mit Filtern."""
        import os
        import tempfile
        from datetime import date as date_type, datetime as datetime_type
        from app.db import connection as conn_module
        from app.db.models import Base
        from app.db.repository import ArticleRepository
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session, sessionmaker as sm

        tmp = tempfile.mktemp(suffix=".db")
        try:
            engine = create_engine(f"sqlite:///{tmp}", echo=False)
            Base.metadata.create_all(engine)
            session = Session(engine)

            factory = sm(bind=engine)
            monkeypatch.setattr(conn_module, "_engine", engine)
            monkeypatch.setattr(conn_module, "_SessionLocal", factory)
            monkeypatch.setattr(conn_module, "get_session", factory)

            from app.api.server import create_app
            from fastapi.testclient import TestClient
            app = create_app()
            import app.api.routes as routes_mod
            monkeypatch.setattr(routes_mod, "get_session", factory)
            client = TestClient(app)

            repo = ArticleRepository(session)
            repo.insert(
                article_data={
                    "title": "Test Tour",
                    "tour_date": date_type(2026, 4, 15),
                    "tour_duration_hours": 5.0,
                    "generation_timestamp": datetime_type(2026, 4, 30, 12, 0, 0),
                    "markdown_content": "# Test",
                    "html_content": "<h1>Test</h1>",
                    "markdown_path": "output/test/md.md",
                    "html_path": "output/test/html.html",
                },
                images=[],
            )
            session.commit()

            response = client.get("/api/articles?tour_date_from=2026-04-01&tour_date_to=2026-05-01")
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 1
            assert data["articles"][0]["title"] == "Test Tour"
            assert data["articles"][0]["tour_duration_hours"] == 5.0
            assert data["articles"][0]["tour_date"] == "2026-04-15"
            assert "markdown_content" not in data["articles"][0]

            session.close()
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def test_list_no_filters_returns_all(self, monkeypatch):
        import os
        import tempfile
        from app.db import connection as conn_module
        from app.db.models import Base
        from app.db.repository import ArticleRepository
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session, sessionmaker as sm

        tmp = tempfile.mktemp(suffix=".db")
        try:
            engine = create_engine(f"sqlite:///{tmp}", echo=False)
            Base.metadata.create_all(engine)
            session = Session(engine)

            factory = sm(bind=engine)
            monkeypatch.setattr(conn_module, "_engine", engine)
            monkeypatch.setattr(conn_module, "_SessionLocal", factory)
            monkeypatch.setattr(conn_module, "get_session", factory)

            from app.api.server import create_app
            from fastapi.testclient import TestClient
            app = create_app()
            import app.api.routes as routes_mod
            monkeypatch.setattr(routes_mod, "get_session", factory)
            client = TestClient(app)

            repo = ArticleRepository(session)
            repo.insert(article_data={"title": "A"}, images=[])
            repo.insert(article_data={"title": "B"}, images=[])
            session.commit()

            response = client.get("/api/articles")
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 2
            assert len(data["articles"]) == 2

            session.close()
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)


class TestArticleDetail:
    def test_get_by_valid_id(self, monkeypatch):
        import os
        import tempfile
        from app.db import connection as conn_module
        from app.db.models import Base
        from app.db.repository import ArticleRepository
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session, sessionmaker as sm

        tmp = tempfile.mktemp(suffix=".db")
        try:
            engine = create_engine(f"sqlite:///{tmp}", echo=False)
            Base.metadata.create_all(engine)
            session = Session(engine)

            factory = sm(bind=engine)
            monkeypatch.setattr(conn_module, "_engine", engine)
            monkeypatch.setattr(conn_module, "_SessionLocal", factory)
            monkeypatch.setattr(conn_module, "get_session", factory)

            from app.api.server import create_app
            from fastapi.testclient import TestClient
            app = create_app()
            import app.api.routes as routes_mod
            monkeypatch.setattr(routes_mod, "get_session", factory)
            client = TestClient(app)

            repo = ArticleRepository(session)
            article_id = repo.insert(
                article_data={
                    "title": "Detail Test",
                    "markdown_content": "# Detail Test\nContent",
                    "html_content": "<h1>Detail Test</h1><p>Content</p>",
                    "markdown_path": "output/test/md.md",
                    "html_path": "output/test/html.html",
                },
                images=[
                    {"image_path": "./images/01.jpg", "is_map": False, "is_elevation_profile": False},
                ],
            )
            session.commit()

            response = client.get(f"/api/articles/{article_id}")
            assert response.status_code == 200
            data = response.json()
            assert data["article"]["id"] == article_id
            assert data["article"]["title"] == "Detail Test"
            assert data["article"]["markdown_content"] == "# Detail Test\nContent"
            assert len(data["article"]["images"]) == 1

            session.close()
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def test_get_by_invalid_id_returns_404(self, client):
        response = client.get("/api/articles/99999")
        assert response.status_code == 404


class TestArticleDelete:
    def test_delete_existing_article(self, monkeypatch):
        import os
        import tempfile
        from app.db import connection as conn_module
        from app.db.models import Base
        from app.db.repository import ArticleRepository
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session, sessionmaker as sm

        tmp = tempfile.mktemp(suffix=".db")
        try:
            engine = create_engine(f"sqlite:///{tmp}", echo=False)
            Base.metadata.create_all(engine)
            session = Session(engine)

            factory = sm(bind=engine)
            monkeypatch.setattr(conn_module, "_engine", engine)
            monkeypatch.setattr(conn_module, "_SessionLocal", factory)
            monkeypatch.setattr(conn_module, "get_session", factory)

            from app.api.server import create_app
            from fastapi.testclient import TestClient
            app = create_app()
            import app.api.routes as routes_mod
            monkeypatch.setattr(routes_mod, "get_session", factory)
            client = TestClient(app)

            repo = ArticleRepository(session)
            article_id = repo.insert(
                article_data={"title": "Delete Me", "markdown_path": "output/test/md.md"},
                images=[],
            )
            session.commit()

            response = client.delete(f"/api/articles/{article_id}")
            assert response.status_code == 200
            assert response.json()["deleted"] == article_id

            # Verify it's gone
            response2 = client.get(f"/api/articles/{article_id}")
            assert response2.status_code == 404

            session.close()
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def test_delete_nonexistent_article_returns_404(self, client):
        response = client.delete("/api/articles/99999")
        assert response.status_code == 404


class TestArticlePdf:
    def test_pdf_endpoint_returns_404_for_missing_article(self, client):
        response = client.get("/api/articles/99999/pdf")
        assert response.status_code == 404

    def test_pdf_endpoint_with_valid_article(self, monkeypatch):
        """Testet, dass der Endpunkt einen 200-Status und application/pdf liefert.
        Achtung: Mockt die PDF-Generierung, da Chrome im Test nicht verfügbar ist."""
        import os
        import tempfile
        from app.db import connection as conn_module
        from app.db.models import Base
        from app.db.repository import ArticleRepository
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session, sessionmaker as sm
        from unittest.mock import patch

        tmp = tempfile.mktemp(suffix=".db")
        try:
            engine = create_engine(f"sqlite:///{tmp}", echo=False)
            Base.metadata.create_all(engine)
            session = Session(engine)

            factory = sm(bind=engine)
            monkeypatch.setattr(conn_module, "_engine", engine)
            monkeypatch.setattr(conn_module, "_SessionLocal", factory)
            monkeypatch.setattr(conn_module, "get_session", factory)

            from app.api.server import create_app
            from fastapi.testclient import TestClient
            app = create_app()
            import app.api.routes as routes_mod
            monkeypatch.setattr(routes_mod, "get_session", factory)
            client = TestClient(app)

            repo = ArticleRepository(session)
            article_id = repo.insert(
                article_data={
                    "title": "PDF Test",
                    "markdown_content": "# PDF Test",
                    "html_content": "<h1>PDF Test</h1><p>Content</p>",
                    "markdown_path": "output/test/md.md",
                    "html_path": "output/test/html.html",
                },
                images=[],
            )
            session.commit()

            # Mock generate_pdf um Chrome-Aufruf zu vermeiden
            with patch("app.services.generate_pdf.generate_pdf", return_value=b"%PDF-1.4 mock") as mock_gen:
                response = client.get(f"/api/articles/{article_id}/pdf")
                assert response.status_code == 200
                assert response.headers["content-type"] == "application/pdf"
                assert "attachment" in response.headers["content-disposition"]
                assert response.content == b"%PDF-1.4 mock"
                mock_gen.assert_called_once()

            session.close()
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def test_pdf_endpoint_with_no_html_content(self, monkeypatch):
        import os
        import tempfile
        from app.db import connection as conn_module
        from app.db.models import Base
        from app.db.repository import ArticleRepository
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session, sessionmaker as sm

        tmp = tempfile.mktemp(suffix=".db")
        try:
            engine = create_engine(f"sqlite:///{tmp}", echo=False)
            Base.metadata.create_all(engine)
            session = Session(engine)

            factory = sm(bind=engine)
            monkeypatch.setattr(conn_module, "_engine", engine)
            monkeypatch.setattr(conn_module, "_SessionLocal", factory)
            monkeypatch.setattr(conn_module, "get_session", factory)

            from app.api.server import create_app
            from fastapi.testclient import TestClient
            app = create_app()
            import app.api.routes as routes_mod
            monkeypatch.setattr(routes_mod, "get_session", factory)
            client = TestClient(app)

            repo = ArticleRepository(session)
            article_id = repo.insert(
                article_data={"title": "No HTML", "markdown_path": "output/test/md.md"},
                images=[],
            )
            session.commit()

            response = client.get(f"/api/articles/{article_id}/pdf")
            assert response.status_code == 400

            session.close()
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
