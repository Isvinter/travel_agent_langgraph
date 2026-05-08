"""Shared pytest fixtures for the travel agent test suite."""

import os
import tempfile
from pathlib import Path
from typing import List

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.state import AppState, ImageData
from app.services.gpx_analytics import GPXStats, analyze_track

FIXTURES_DIR = Path(__file__).parent / "fixtures"
GPX_PATH = str(FIXTURES_DIR / "gpx" / "tour.gpx")
NOTES_DIR = str(FIXTURES_DIR / "notes")


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    return FIXTURES_DIR


@pytest.fixture(scope="session")
def sample_gpx_path() -> str:
    return GPX_PATH


@pytest.fixture(scope="session")
def sample_gpx_stats() -> GPXStats:
    stats, pauses = analyze_track(GPX_PATH)
    return stats


@pytest.fixture(scope="session")
def sample_gpx_pauses() -> List[dict]:
    stats, pauses = analyze_track(GPX_PATH)
    return pauses


@pytest.fixture
def sample_images() -> List[ImageData]:
    return [
        ImageData(
            path=str(FIXTURES_DIR / "images" / "photo_a.jpg"),
            timestamp=None,
            latitude=None,
            longitude=None,
        ),
        ImageData(
            path=str(FIXTURES_DIR / "images" / "photo_b.jpg"),
            timestamp=None,
            latitude=None,
            longitude=None,
        ),
        ImageData(
            path=str(FIXTURES_DIR / "images" / "photo_c.jpg"),
            timestamp=None,
            latitude=None,
            longitude=None,
        ),
    ]


@pytest.fixture
def sample_state(sample_gpx_path, sample_images) -> AppState:
    return AppState(
        gpx_file=sample_gpx_path,
        images=sample_images,
        model="gemma4:26b-ctx128k",
    )


@pytest.fixture
def notes_dir_path() -> str:
    return str(NOTES_DIR)


# ── API-Test-Fixtures mit temporärer Datenbank ──────────

@pytest.fixture
def _test_db(monkeypatch):
    """Temporäre Test-Datenbank für API-Tests.

    Erzeugt eine frische SQLite-DB im Temp-Verzeichnis und patched
    das connection-Modul sowie routes.get_session, sodass API-Tests
    gegen die temporäre DB laufen.
    """
    from app.db.models import Base
    import app.db.connection as conn_module
    import app.api.routes as routes_mod

    tmp = tempfile.mktemp(suffix=".db")
    engine = create_engine(f"sqlite:///{tmp}", echo=False)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)

    monkeypatch.setattr(conn_module, "_engine", engine)
    monkeypatch.setattr(conn_module, "_SessionLocal", factory)
    monkeypatch.setattr(conn_module, "get_session", factory)
    monkeypatch.setattr(routes_mod, "get_session", factory)

    yield {"engine": engine, "factory": factory, "tmp": tmp}

    if os.path.exists(tmp):
        os.unlink(tmp)


@pytest.fixture
def test_client(_test_db):
    """FastAPI TestClient (temporäre DB)."""
    from app.api.server import create_app
    from fastapi.testclient import TestClient
    return TestClient(create_app())


@pytest.fixture
def test_session(_test_db):
    """SQLAlchemy Session auf der temporären Test-DB."""
    return Session(_test_db["engine"])

