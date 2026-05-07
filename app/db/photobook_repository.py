# app/db/photobook_repository.py
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional, List

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.db.models import Photobook, PhotobookImage


@dataclass
class PhotobookFilters:
    tour_date_from: Optional[date] = None
    tour_date_to: Optional[date] = None
    duration_min: Optional[float] = None
    duration_max: Optional[float] = None
    generated_from: Optional[datetime] = None
    generated_to: Optional[datetime] = None
    limit: int = 20
    offset: int = 0


class PhotobookRepository:
    """Repository für den Zugriff auf die photobooks-Tabelle."""

    def __init__(self, session: Session):
        self.session = session

    def insert(self, photobook_data: dict, images: list[dict]) -> int:
        """Fügt ein Fotobuch mit Bildern ein. Gibt die photobook_id zurück."""
        photobook = Photobook(**photobook_data)
        self.session.add(photobook)
        self.session.flush()

        for img in images:
            self.session.add(PhotobookImage(photobook_id=photobook.id, **img))

        self.session.commit()
        return photobook.id

    def list(self, filters: PhotobookFilters) -> tuple[list[Photobook], int]:
        """Gibt gefilterte und paginierte Fotobücher sowie die Gesamtanzahl zurück."""
        q = select(Photobook)

        if filters.tour_date_from:
            q = q.where(Photobook.tour_date >= filters.tour_date_from)
        if filters.tour_date_to:
            q = q.where(Photobook.tour_date <= filters.tour_date_to)
        if filters.duration_min is not None:
            q = q.where(Photobook.tour_duration_hours >= filters.duration_min)
        if filters.duration_max is not None:
            q = q.where(Photobook.tour_duration_hours <= filters.duration_max)
        if filters.generated_from:
            q = q.where(Photobook.generation_timestamp >= filters.generated_from)
        if filters.generated_to:
            q = q.where(Photobook.generation_timestamp <= filters.generated_to)

        count_q = select(func.count()).select_from(q.subquery())
        total = self.session.execute(count_q).scalar_one()

        q = q.order_by(Photobook.generation_timestamp.desc())
        q = q.offset(filters.offset).limit(filters.limit)
        records = self.session.execute(q).scalars().all()

        return records, total

    def get_by_id(self, photobook_id: int) -> Optional[Photobook]:
        """Holt ein einzelnes Fotobuch inkl. Bilder."""
        q = select(Photobook).where(Photobook.id == photobook_id)
        return self.session.execute(q).scalar_one_or_none()

    def delete(self, photobook_id: int) -> bool:
        """Löscht ein Fotobuch und seine Bilder (CASCADE). Gibt True zurück wenn gelöscht."""
        photobook = self.get_by_id(photobook_id)
        if photobook is None:
            return False
        self.session.delete(photobook)
        self.session.commit()
        return True

    def delete_batch(self, photobook_ids: List[int]) -> int:
        """Löscht mehrere Fotobücher und ihre Bilder (CASCADE). Gibt Anzahl gelöschter zurück."""
        if not photobook_ids:
            return 0
        count = (
            self.session.query(Photobook)
            .where(Photobook.id.in_(photobook_ids))
            .delete(synchronize_session="fetch")
        )
        self.session.commit()
        return count
