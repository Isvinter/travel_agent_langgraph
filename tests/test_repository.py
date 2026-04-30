# tests/test_repository.py
from datetime import date, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.models import Base, Article
from app.db.repository import ArticleFilters, ArticleRepository


def _create_session() -> Session:
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    return Session(engine)


class TestArticleRepository:
    def test_insert_and_get_by_id(self):
        session = _create_session()
        repo = ArticleRepository(session)

        article_id = repo.insert(
            article_data={
                "title": "Test Wanderung",
                "tour_date": date(2026, 4, 15),
                "tour_duration_hours": 4.5,
                "tour_duration_source": "gpx",
                "generation_timestamp": datetime(2026, 4, 30, 12, 0, 0),
                "gpx_file": "/data/test.gpx",
                "total_distance_km": 12.3,
                "elevation_gain_m": 800,
                "elevation_loss_m": 500,
                "image_count": 2,
                "markdown_content": "# Test\nInhalt",
                "html_content": "<h1>Test</h1>",
                "markdown_path": "output/test/blogpost.md",
                "html_path": "output/test/blogpost.html",
                "model_used": "gemma4:26b-ctx128k",
                "notes": "Schöne Tour",
            },
            images=[
                {"image_path": "./images/01_test.jpg", "is_map": False, "is_elevation_profile": False},
                {"image_path": "./images/00_map.png", "is_map": True, "is_elevation_profile": False},
            ],
        )

        article = repo.get_by_id(article_id)
        assert article is not None
        assert article.title == "Test Wanderung"
        assert article.tour_date == date(2026, 4, 15)
        assert article.total_distance_km == 12.3
        assert len(article.images) == 2
        assert article.images[0].image_path == "./images/01_test.jpg"

    def test_list_with_tour_date_filter(self):
        session = _create_session()
        repo = ArticleRepository(session)

        repo.insert(
            article_data={"tour_date": date(2026, 4, 1), "title": "April-Tour"},
            images=[],
        )
        repo.insert(
            article_data={"tour_date": date(2026, 5, 15), "title": "Mai-Tour"},
            images=[],
        )

        articles, total = repo.list(ArticleFilters(tour_date_from=date(2026, 5, 1)))
        assert total == 1
        assert articles[0].title == "Mai-Tour"

    def test_list_with_duration_range(self):
        session = _create_session()
        repo = ArticleRepository(session)

        repo.insert(article_data={"tour_duration_hours": 2.0, "title": "Kurz"}, images=[])
        repo.insert(article_data={"tour_duration_hours": 8.0, "title": "Lang"}, images=[])

        articles, total = repo.list(ArticleFilters(duration_min=3.0, duration_max=10.0))
        assert total == 1
        assert articles[0].title == "Lang"

    def test_list_with_generation_timestamp_filter(self):
        session = _create_session()
        repo = ArticleRepository(session)

        repo.insert(
            article_data={
                "generation_timestamp": datetime(2026, 4, 1, 10, 0),
                "title": "Alt",
            },
            images=[],
        )
        repo.insert(
            article_data={
                "generation_timestamp": datetime(2026, 5, 1, 10, 0),
                "title": "Neu",
            },
            images=[],
        )

        articles, total = repo.list(
            ArticleFilters(generated_from=datetime(2026, 4, 15))
        )
        assert total == 1
        assert articles[0].title == "Neu"

    def test_list_pagination(self):
        session = _create_session()
        repo = ArticleRepository(session)

        for i in range(5):
            repo.insert(article_data={"title": f"Tour {i}"}, images=[])

        articles, total = repo.list(ArticleFilters(limit=3, offset=0))
        assert total == 5
        assert len(articles) == 3

        articles2, _ = repo.list(ArticleFilters(limit=3, offset=3))
        assert len(articles2) == 2

    def test_delete_article(self):
        session = _create_session()
        repo = ArticleRepository(session)

        article_id = repo.insert(article_data={"title": "Zu löschen"}, images=[])
        assert repo.get_by_id(article_id) is not None

        result = repo.delete(article_id)
        assert result is True
        assert repo.get_by_id(article_id) is None

    def test_delete_nonexistent(self):
        session = _create_session()
        repo = ArticleRepository(session)

        result = repo.delete(999)
        assert result is False

    def test_get_by_id_nonexistent(self):
        session = _create_session()
        repo = ArticleRepository(session)

        article = repo.get_by_id(999)
        assert article is None

    def test_tour_duration_source_is_null_when_not_provided(self):
        session = _create_session()
        repo = ArticleRepository(session)

        article_id = repo.insert(article_data={"title": "Keine Dauer"}, images=[])
        article = repo.get_by_id(article_id)

        assert article.tour_duration_hours is None
        assert article.tour_duration_source is None
