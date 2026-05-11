# app/db/base_repository.py
from typing import Generic, Optional, List, TypeVar, Tuple
from sqlalchemy import select, func, Select
from sqlalchemy.orm import Session, DeclarativeBase, selectinload

T = TypeVar("T", bound=DeclarativeBase)
F = TypeVar("F")


class BaseRepository(Generic[T, F]):
    """Generisches Repository für CRUD-Operationen auf einer Tabelle."""

    model: type[T]
    image_model: type[DeclarativeBase] | None = None
    image_fk_name: str = "article_id"

    def __init__(self, session: Session):
        self.session = session

    def insert(self, data: dict, images: list[dict]) -> int:
        """Fügt einen Datensatz mit Bildern ein. Gibt die ID zurück."""
        if data is None:
            raise ValueError("data darf nicht None sein")
        record: T = self.model(**data)
        self.session.add(record)
        self.session.flush()

        if self.image_model:
            for img in images:
                self.session.add(self.image_model(**{self.image_fk_name: record.id, **img}))

        try:
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        return record.id

    def get_by_id(self, record_id: int) -> Optional[T]:
        """Holt einen einzelnen Datensatz inkl. Images (eager geladen)."""
        q = select(self.model).options(selectinload(self.model.images)).where(self.model.id == record_id)
        return self.session.execute(q).scalar_one_or_none()

    def delete(self, record_id: int) -> bool:
        """Löscht einen Datensatz (CASCADE). Gibt True zurück wenn gelöscht."""
        record = self.get_by_id(record_id)
        if record is None:
            return False
        self.session.delete(record)
        try:
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        return True

    def delete_batch(self, record_ids: List[int]) -> int:
        """Löscht mehrere Datensätze (CASCADE). Gibt Anzahl gelöschter zurück."""
        if not record_ids:
            return 0
        count = (
            self.session.query(self.model)
            .where(self.model.id.in_(record_ids))
            .delete(synchronize_session="fetch")
        )
        try:
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        return count

    def update(self, record_id: int, updates: dict) -> Optional[T]:
        """Aktualisiert Felder eines Datensatzes."""
        record = self.get_by_id(record_id)
        if record is None:
            return None
        for key, value in updates.items():
            setattr(record, key, value)
        try:
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        return record

    def list(self, filters: F) -> Tuple[list[T], int]:
        """Gibt gefilterte und paginierte Datensätze sowie die Gesamtanzahl zurück.
        
        Subklassen müssen _apply_filters() implementieren.
        """
        q = select(self.model)
        q = self._apply_filters(q, filters)

        count_q = select(func.count()).select_from(q.subquery())
        total = self.session.execute(count_q).scalar_one()

        q = q.order_by(self.model.generation_timestamp.desc())
        q = q.offset(filters.offset).limit(filters.limit)
        records = self.session.execute(q).scalars().all()

        return records, total

    def _apply_filters(self, q: Select[Tuple[T]], filters: F) -> Select[Tuple[T]]:
        """Wendet Filterspezifische Bedingungen an. Von Subklassen zu überschreiben."""
        raise NotImplementedError("Subklassen müssen _apply_filters() implementieren")
