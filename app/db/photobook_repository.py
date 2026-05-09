# app/db/photobook_repository.py
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional, List

from sqlalchemy.orm import Session

from app.db.models import Photobook, PhotobookImage
from app.db.base_repository import BaseRepository


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


class PhotobookRepository(BaseRepository[Photobook, PhotobookFilters]):
    """Repository für den Zugriff auf die photobooks-Tabelle."""

    model = Photobook
    image_model = PhotobookImage
    image_fk_name = "photobook_id"

    def insert(self, photobook_data: dict = None, images: list[dict] = None, **kwargs) -> int:
        return super().insert(photobook_data, images)

    def _apply_filters(self, q, filters: PhotobookFilters):
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
        return q
