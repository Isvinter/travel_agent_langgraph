# tests/test_persist_service.py
from datetime import datetime, date
import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.models import Base
from app.db.repository import ArticleRepository
from app.state import ImageData


class FakePoint:
    def __init__(self, time_val):
        self.time = time_val


class FakeGPXStats:
    def __init__(self):
        self.total_distance_m = 12300.0
        self.elevation_gain_m = 800.0
        self.elevation_loss_m = 500.0
        self.points = [
            FakePoint(datetime(2026, 4, 15, 8, 0, 0)),
            FakePoint(datetime(2026, 4, 15, 12, 30, 0)),
            FakePoint(datetime(2026, 4, 15, 12, 30, 10)),
        ]


class TestPersistArticleService:
    def test_persist_with_full_data(self, monkeypatch):
        """Integrationstest: Service persistiert vollständigen Blogpost."""
        from app.services.persist_article import persist_article
        from app.db import connection as conn_module

        # SQLite in-memory für den Test
        engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(engine)
        session = Session(engine)

        monkeypatch.setattr(conn_module, "_engine", engine)
        monkeypatch.setattr(conn_module, "_SessionLocal", None)

        def fake_get_session():
            # Immer denselben Session-Objekt zurückgeben
            return session

        monkeypatch.setattr(conn_module, "get_session", fake_get_session)

        blog_post = {
            "success": True,
            "markdown": "# Unsere große Wanderung\n\nEin toller Tag!",
            "html": "<h1>Unsere große Wanderung</h1><p>Ein toller Tag!</p>",
            "file_paths": {
                "markdown": "output/test/blogpost.md",
                "html": "output/test/blogpost.html",
            },
            "selected_images": [
                "./images/00_map.png",
                "./images/01_test.jpg",
            ],
            "descriptions": {
                "Hier ist die Übersichtskarte der Route": "./images/00_map.png",
                "Testbild": "./images/01_test.jpg",
            },
        }

        gpx_stats = FakeGPXStats()

        article_id = persist_article(
            blog_post=blog_post,
            gpx_stats=gpx_stats,
            images=[],
            gpx_file="/data/test.gpx",
            model="gemma4:26b-ctx128k",
            notes="Schöne Tour!",
        )

        assert article_id is not None

        repo = ArticleRepository(session)
        article = repo.get_by_id(article_id)
        assert article is not None
        assert article.title == "Unsere große Wanderung"
        assert article.tour_date == date(2026, 4, 15)
        assert article.tour_duration_hours == pytest.approx(4.5, rel=0.01)
        assert article.tour_duration_source == "gpx"
        assert article.total_distance_km == 12.3
        assert article.elevation_gain_m == 800.0
        assert article.elevation_loss_m == 500.0
        assert article.image_count == 2
        assert article.model_used == "gemma4:26b-ctx128k"
        assert article.notes == "Schöne Tour!"
        assert len(article.images) == 2
        assert article.images[0].image_path == "./images/00_map.png"
        assert article.images[0].is_map is True
        assert article.images[1].is_map is False

        session.close()

    def test_persist_with_failed_generation_returns_none(self):
        """Kein Persistieren wenn blog_post nicht erfolgreich war."""
        from app.services.persist_article import persist_article

        blog_post = {"success": False, "error": "Generation failed"}
        article_id = persist_article(
            blog_post=blog_post,
            gpx_stats=None,
            images=[],
            gpx_file="",
            model="",
        )
        assert article_id is None

    def test_persist_without_gpx_uses_photos_for_duration(self, monkeypatch):
        """Fallback auf Foto-Timestamps wenn keine GPX-Daten."""
        from app.services.persist_article import persist_article
        from app.db import connection as conn_module

        engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(engine)
        session = Session(engine)

        monkeypatch.setattr(conn_module, "_engine", engine)
        monkeypatch.setattr(conn_module, "_SessionLocal", None)
        monkeypatch.setattr(conn_module, "get_session", lambda: session)

        blog_post = {
            "success": True,
            "markdown": "# Fotobasierte Wanderung",
            "html": "",
            "file_paths": {"markdown": "", "html": ""},
            "selected_images": [],
            "descriptions": {},
        }

        images_with_timestamps = [
            ImageData(path="img1.jpg", timestamp="2026-04-20T08:00:00"),
            ImageData(path="img2.jpg", timestamp="2026-04-20T14:00:00"),
        ]

        # GPX-Objekt ohne Zeitstempel simulieren
        class GPXWithoutTime:
            total_distance_m = None
            elevation_gain_m = None
            elevation_loss_m = None
            points = []

        article_id = persist_article(
            blog_post=blog_post,
            gpx_stats=GPXWithoutTime(),
            images=images_with_timestamps,
            gpx_file="",
            model="",
        )

        repo = ArticleRepository(session)
        article = repo.get_by_id(article_id)
        assert article.tour_duration_source == "photos"
        assert article.tour_duration_hours == 6.0

        session.close()
