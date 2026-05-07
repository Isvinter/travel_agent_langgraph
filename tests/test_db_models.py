"""Tests für app/db/models.py — ORM-Modelle"""
from datetime import date, datetime

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session

from app.db.models import Base, Article, ArticleImage, Photobook, PhotobookImage


@pytest.fixture(scope="module")
def engine():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def session(engine):
    with Session(engine) as s:
        yield s


class TestArticleModel:
    def test_create_minimal_article(self, session):
        a = Article(title="Testartikel")
        session.add(a)
        session.commit()
        assert a.id is not None
        assert a.title == "Testartikel"
        assert a.created_at is not None
        assert isinstance(a.created_at, datetime)

    def test_create_full_article(self, session):
        a = Article(
            title="Vollständiger Test",
            tour_date=date(2024, 7, 15),
            tour_duration_hours=5.5,
            tour_duration_source="gpx",
            gpx_file="/test/tour.gpx",
            total_distance_km=42.0,
            elevation_gain_m=1200,
            elevation_loss_m=1300,
            image_count=8,
            markdown_content="# Test\nSome content",
            html_content="<h1>Test</h1><p>Some content</p>",
            markdown_path="/output/test.md",
            html_path="/output/test.html",
            model_used="gemma4:26b",
            notes="Tour-Notizen",
        )
        session.add(a)
        session.commit()
        assert a.id is not None
        assert a.total_distance_km == 42.0
        assert a.elevation_gain_m == 1200
        assert a.tour_date == date(2024, 7, 15)

    def test_nullable_fields_default_to_none(self, session):
        a = Article()
        session.add(a)
        session.commit()
        assert a.title is None
        assert a.tour_date is None
        assert a.tour_duration_hours is None
        assert a.gpx_file is None
        assert a.html_content is None

    def test_image_count_is_nullable(self, session):
        a = Article(title="Ohne Bilder")
        session.add(a)
        session.commit()
        assert a.image_count is None  # nullable


class TestArticleImageModel:
    def test_create_article_with_images(self, session):
        a = Article(title="Mit Bildern")
        a.images = [
            ArticleImage(image_path="/images/1.jpg", is_map=False),
            ArticleImage(image_path="/images/2.jpg", is_map=True),
        ]
        session.add(a)
        session.commit()
        assert len(a.images) == 2
        assert a.images[0].image_path == "/images/1.jpg"
        assert a.images[1].is_map is True

    def test_cascade_delete_article_images(self, session):
        a = Article(title="Zum Löschen")
        a.images = [ArticleImage(image_path="/images/x.jpg")]
        session.add(a)
        session.commit()
        article_id = a.id
        session.delete(a)
        session.commit()
        img = session.get(ArticleImage, (session.get(Article, article_id),))
        # Nach CASCADE-Delete sollten keine Images mehr da sein
        remaining = session.query(ArticleImage).filter_by(article_id=article_id).all()
        assert len(remaining) == 0

    def test_image_path_is_required(self, session):
        """ArticleImage ohne image_path sollte einen IntegrityError werfen."""
        a = Article(title="Test")
        session.add(a)
        session.flush()
        img = ArticleImage(article_id=a.id)  # Kein image_path
        session.add(img)
        with pytest.raises(Exception):
            session.commit()
        session.rollback()


class TestPhotobookModel:
    def test_create_minimal_photobook(self, session):
        p = Photobook(title="Fotobuch Test")
        session.add(p)
        session.commit()
        assert p.id is not None
        assert p.created_at is not None

    def test_photobook_specific_fields(self, session):
        p = Photobook(
            title="Mein Fotobuch",
            pdf_path="/output/photobook.pdf",
            page_count=12,
            photobook_size="normal",
        )
        session.add(p)
        session.commit()
        assert p.pdf_path == "/output/photobook.pdf"
        assert p.page_count == 12
        assert p.photobook_size == "normal"


class TestPhotobookImageModel:
    def test_create_photobook_with_images(self, session):
        p = Photobook(title="Mit Bildern")
        p.images = [
            PhotobookImage(image_path="/images/a.jpg"),
            PhotobookImage(image_path="/images/b.jpg", is_elevation_profile=True),
        ]
        session.add(p)
        session.commit()
        assert len(p.images) == 2
        assert p.images[1].is_elevation_profile is True

    def test_cascade_delete_photobook_images(self, session):
        p = Photobook(title="Zum Löschen")
        p.images = [PhotobookImage(image_path="/images/y.jpg")]
        session.add(p)
        session.commit()
        photobook_id = p.id
        session.delete(p)
        session.commit()
        remaining = session.query(PhotobookImage).filter_by(photobook_id=photobook_id).all()
        assert len(remaining) == 0


class TestTableNames:
    def test_article_table_name(self):
        assert Article.__tablename__ == "articles"

    def test_article_image_table_name(self):
        assert ArticleImage.__tablename__ == "article_images"

    def test_photobook_table_name(self):
        assert Photobook.__tablename__ == "photobooks"

    def test_photobook_image_table_name(self):
        assert PhotobookImage.__tablename__ == "photobook_images"
