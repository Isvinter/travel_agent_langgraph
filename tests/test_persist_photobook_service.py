# tests/test_persist_photobook_service.py
from datetime import datetime, date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.models import Base
from app.db.photobook_repository import PhotobookRepository
from app.state import ImageData


class FakePoint:
    def __init__(self, time_val):
        self.time = time_val


class FakeGPXStats:
    def __init__(self):
        self.total_distance_m = 25000.0
        self.elevation_gain_m = 1200.0
        self.elevation_loss_m = 900.0
        self.points = [
            FakePoint(datetime(2026, 5, 1, 7, 0, 0)),
            FakePoint(datetime(2026, 5, 1, 16, 0, 0)),
        ]


class TestPersistPhotobookService:
    def test_persist_with_full_data(self, monkeypatch):
        """Integrationstest: Service persistiert vollständiges Fotobuch."""
        from app.services.persist_photobook import persist_photobook
        from app.db import connection as conn_module

        engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(engine)
        session = Session(engine)

        monkeypatch.setattr(conn_module, "_engine", engine)
        monkeypatch.setattr(conn_module, "_SessionLocal", None)
        monkeypatch.setattr(conn_module, "get_session", lambda: session)

        gpx_stats = FakeGPXStats()
        photobook_images = [
            ImageData(path="/tmp/00_map.png", timestamp="2026-05-01T10:00:00"),
            ImageData(path="/tmp/01_photo.jpg", timestamp="2026-05-01T12:00:00"),
            ImageData(path="/tmp/02_photo.jpg", timestamp="2026-05-01T14:00:00"),
        ]
        page_descriptions = [{"template_id": "cover_hero"}, {"template_id": "single_full"}]

        photobook_id = persist_photobook(
            gpx_stats=gpx_stats,
            photobook_images=photobook_images,
            photobook_pages=page_descriptions,
            photobook_html="<h1>Fotobuch</h1>",
            photobook_html_path="output/photobook_2026-05-01_08-00-00/test.html",
            photobook_pdf_path="output/photobook_2026-05-01_08-00-00/test.pdf",
            photobook_size="normal",
            gpx_file="/data/test.gpx",
            model="gemma4:26b-ctx128k",
            notes="Tolle Fototour",
        )

        assert photobook_id is not None

        repo = PhotobookRepository(session)
        record = repo.get_by_id(photobook_id)
        assert record is not None
        assert record.tour_date == date(2026, 5, 1)
        assert record.tour_duration_hours == pytest.approx(9.0, rel=0.01)
        assert record.tour_duration_source == "gpx"
        assert record.total_distance_km == 25.0
        assert record.elevation_gain_m == 1200.0
        assert record.elevation_loss_m == 900.0
        assert record.image_count == 3
        assert record.model_used == "gemma4:26b-ctx128k"
        assert record.notes == "Tolle Fototour"
        assert record.photobook_size == "normal"
        assert record.page_count == 2
        assert record.pdf_path == "output/photobook_2026-05-01_08-00-00/test.pdf"
        assert record.html_content == "<h1>Fotobuch</h1>"
        assert len(record.images) == 3

        session.close()

    def test_persist_without_gpx_uses_photos_for_duration(self, monkeypatch):
        """Fallback auf Foto-Timestamps wenn keine GPX-Daten."""
        from app.services.persist_photobook import persist_photobook
        from app.db import connection as conn_module

        engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(engine)
        session = Session(engine)

        monkeypatch.setattr(conn_module, "_engine", engine)
        monkeypatch.setattr(conn_module, "_SessionLocal", None)
        monkeypatch.setattr(conn_module, "get_session", lambda: session)

        class GPXWithoutTime:
            total_distance_m = None
            elevation_gain_m = None
            elevation_loss_m = None
            points = []

        photobook_images = [
            ImageData(path="img1.jpg", timestamp="2026-04-20T08:00:00"),
            ImageData(path="img2.jpg", timestamp="2026-04-20T14:00:00"),
        ]

        photobook_id = persist_photobook(
            gpx_stats=GPXWithoutTime(),
            photobook_images=photobook_images,
            photobook_pages=[{"template_id": "single_full"}],
            photobook_html="<h1>Test</h1>",
            photobook_html_path="output/test.html",
            photobook_pdf_path="output/test.pdf",
            photobook_size="short",
            gpx_file="",
            model="",
        )

        repo = PhotobookRepository(session)
        record = repo.get_by_id(photobook_id)
        assert record.tour_duration_source == "photos"
        assert record.tour_duration_hours == 6.0
        assert record.photobook_size == "short"

        session.close()
