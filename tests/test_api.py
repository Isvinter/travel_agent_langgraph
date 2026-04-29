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
            "gpx_file": "/some/fake/path.gpx",
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
