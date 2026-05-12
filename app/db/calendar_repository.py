"""Repository für Kalender-Datenbankzugriffe."""
from __future__ import annotations
from typing import Optional, Tuple
from sqlalchemy import desc, func
from app.db.models import Calendar, CalendarImage
from app.db.base_repository import BaseRepository


class CalendarFilters:
    def __init__(self, limit: int = 20, offset: int = 0, year: Optional[int] = None, preset: Optional[str] = None):
        self.limit = limit
        self.offset = offset
        self.year = year
        self.preset = preset


class CalendarRepository(BaseRepository):
    model = Calendar
    image_model = CalendarImage
    image_fk_name = "calendar_id"

    def list(self, filters: CalendarFilters) -> Tuple[list, int]:
        query = self.session.query(Calendar)
        count_query = self.session.query(func.count(Calendar.id))

        if filters.year:
            query = query.filter(Calendar.year == filters.year)
            count_query = count_query.filter(Calendar.year == filters.year)
        if filters.preset:
            query = query.filter(Calendar.preset == filters.preset)
            count_query = count_query.filter(Calendar.preset == filters.preset)

        total = count_query.scalar() or 0
        records = query.order_by(desc(Calendar.created_at)).offset(filters.offset).limit(filters.limit).all()
        return records, total

    def create(
        self,
        preset: str,
        year: int,
        custom_instructions: Optional[str] = None,
        html_content: Optional[str] = None,
        html_path: Optional[str] = None,
        pdf_path: Optional[str] = None,
        model_used: Optional[str] = None,
        image_entries: Optional[list[dict]] = None,
    ) -> Calendar:
        cal = Calendar(
            preset=preset,
            year=year,
            custom_instructions=custom_instructions,
            html_content=html_content,
            html_path=html_path,
            pdf_path=pdf_path,
            status="complete",
            model_used=model_used,
        )
        self.session.add(cal)
        self.session.flush()

        if image_entries:
            for entry in image_entries:
                img = CalendarImage(
                    calendar_id=cal.id,
                    image_path=entry["image_path"],
                    month_index=entry["month_index"],
                    slot_index=entry["slot_index"],
                )
                self.session.add(img)

        self.session.commit()
        return cal
