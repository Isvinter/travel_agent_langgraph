# tests/test_photobook_repository.py
from datetime import date, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.models import Base
from app.db.photobook_repository import PhotobookFilters, PhotobookRepository


def _create_session() -> Session:
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    return Session(engine)


class TestPhotobookRepository:
    def test_insert_and_get_by_id(self):
        session = _create_session()
        repo = PhotobookRepository(session)

        photobook_id = repo.insert(
            photobook_data={
                "title": "Test Fotobuch",
                "tour_date": date(2026, 4, 15),
                "tour_duration_hours": 4.5,
                "tour_duration_source": "gpx",
                "generation_timestamp": datetime(2026, 4, 30, 12, 0, 0),
                "gpx_file": "/data/test.gpx",
                "total_distance_km": 12.3,
                "elevation_gain_m": 800,
                "elevation_loss_m": 500,
                "image_count": 3,
                "html_content": "<h1>Fotobuch</h1>",
                "html_path": "output/photobook_test/test.html",
                "model_used": "gemma4:26b-ctx128k",
                "notes": "Schöne Tour",
                "pdf_path": "output/photobook_test/test.pdf",
                "page_count": 12,
                "photobook_size": "normal",
            },
            images=[
                {"image_path": "./images/01_test.jpg", "is_map": False, "is_elevation_profile": False},
                {"image_path": "./images/00_map.png", "is_map": True, "is_elevation_profile": False},
            ],
        )

        record = repo.get_by_id(photobook_id)
        assert record is not None
        assert record.title == "Test Fotobuch"
        assert record.tour_date == date(2026, 4, 15)
        assert record.total_distance_km == 12.3
        assert record.pdf_path == "output/photobook_test/test.pdf"
        assert record.page_count == 12
        assert record.photobook_size == "normal"
        assert len(record.images) == 2
        assert record.images[0].image_path == "./images/01_test.jpg"

    def test_list_with_tour_date_filter(self):
        session = _create_session()
        repo = PhotobookRepository(session)

        repo.insert(photobook_data={"tour_date": date(2026, 4, 1), "title": "April-Buch"}, images=[])
        repo.insert(photobook_data={"tour_date": date(2026, 5, 15), "title": "Mai-Buch"}, images=[])

        records, total = repo.list(PhotobookFilters(tour_date_from=date(2026, 5, 1)))
        assert total == 1
        assert records[0].title == "Mai-Buch"

    def test_list_with_duration_range(self):
        session = _create_session()
        repo = PhotobookRepository(session)

        repo.insert(photobook_data={"tour_duration_hours": 2.0, "title": "Kurz"}, images=[])
        repo.insert(photobook_data={"tour_duration_hours": 8.0, "title": "Lang"}, images=[])

        records, total = repo.list(PhotobookFilters(duration_min=3.0, duration_max=10.0))
        assert total == 1
        assert records[0].title == "Lang"

    def test_list_pagination(self):
        session = _create_session()
        repo = PhotobookRepository(session)

        for i in range(5):
            repo.insert(photobook_data={"title": f"Buch {i}"}, images=[])

        records, total = repo.list(PhotobookFilters(limit=3, offset=0))
        assert total == 5
        assert len(records) == 3

        records2, _ = repo.list(PhotobookFilters(limit=3, offset=3))
        assert len(records2) == 2

    def test_delete(self):
        session = _create_session()
        repo = PhotobookRepository(session)

        pb_id = repo.insert(photobook_data={"title": "Zu löschen"}, images=[])
        assert repo.get_by_id(pb_id) is not None

        result = repo.delete(pb_id)
        assert result is True
        assert repo.get_by_id(pb_id) is None

    def test_delete_nonexistent(self):
        session = _create_session()
        repo = PhotobookRepository(session)

        result = repo.delete(999)
        assert result is False

    def test_get_by_id_nonexistent(self):
        session = _create_session()
        repo = PhotobookRepository(session)

        record = repo.get_by_id(999)
        assert record is None

    def test_delete_batch(self):
        session = _create_session()
        repo = PhotobookRepository(session)

        ids = []
        for i in range(3):
            ids.append(repo.insert(photobook_data={"title": f"Buch {i}"}, images=[]))

        result = repo.delete_batch(ids[:2])
        assert result == 2
        assert repo.get_by_id(ids[0]) is None
        assert repo.get_by_id(ids[1]) is None
        assert repo.get_by_id(ids[2]) is not None
