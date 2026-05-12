import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.db.models import Base
from app.db.calendar_repository import CalendarRepository, CalendarFilters


def _create_session() -> Session:
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    return Session(engine)


class TestCalendarRepository:
    @pytest.mark.unit
    def test_create_and_retrieve(self):
        session = _create_session()
        repo = CalendarRepository(session)

        cal = repo.create(preset="mixed", year=2026, html_path="/tmp/test.html")
        assert cal.id is not None
        assert cal.year == 2026

        fetched = repo.get_by_id(cal.id)
        assert fetched is not None
        assert fetched.preset == "mixed"

        session.close()

    @pytest.mark.unit
    def test_list_with_filters(self):
        session = _create_session()
        repo = CalendarRepository(session)

        repo.create(preset="mixed", year=2026)
        repo.create(preset="nature_landscape", year=2025)

        records, total = repo.list(CalendarFilters(limit=10))
        assert total >= 2

        records_26, _ = repo.list(CalendarFilters(limit=10, year=2026))
        assert all(r.year == 2026 for r in records_26)

        session.close()

    @pytest.mark.unit
    def test_delete(self):
        session = _create_session()
        repo = CalendarRepository(session)

        cal = repo.create(preset="mixed", year=2026)
        assert repo.delete(cal.id) is True
        assert repo.get_by_id(cal.id) is None

        session.close()

    @pytest.mark.unit
    def test_create_with_images(self):
        session = _create_session()
        repo = CalendarRepository(session)

        cal = repo.create(
            preset="mixed",
            year=2026,
            image_entries=[
                {"image_path": "/tmp/img1.jpg", "month_index": 0, "slot_index": 0},
                {"image_path": "/tmp/img2.jpg", "month_index": 1, "slot_index": 0},
            ],
        )
        fetched = repo.get_by_id(cal.id)
        assert len(fetched.images) == 2

        session.close()
