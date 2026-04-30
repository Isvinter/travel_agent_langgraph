# app/db/repository.py
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.db.models import Article, ArticleImage


@dataclass
class ArticleFilters:
    tour_date_from: Optional[date] = None
    tour_date_to: Optional[date] = None
    duration_min: Optional[float] = None
    duration_max: Optional[float] = None
    generated_from: Optional[datetime] = None
    generated_to: Optional[datetime] = None
    limit: int = 20
    offset: int = 0


class ArticleRepository:
    """Repository für den Zugriff auf die artikel-Tabelle."""

    def __init__(self, session: Session):
        self.session = session

    def insert(self, article_data: dict, images: list[dict]) -> int:
        """Fügt einen Artikel mit Bildern ein. Gibt die article_id zurück."""
        article = Article(**article_data)
        self.session.add(article)
        self.session.flush()  # ID generieren

        for img in images:
            self.session.add(ArticleImage(article_id=article.id, **img))

        self.session.commit()
        return article.id

    def list(self, filters: ArticleFilters) -> tuple[list[Article], int]:
        """Gibt gefilterte und paginierte Artikel sowie die Gesamtanzahl zurück."""
        q = select(Article)

        if filters.tour_date_from:
            q = q.where(Article.tour_date >= filters.tour_date_from)
        if filters.tour_date_to:
            q = q.where(Article.tour_date <= filters.tour_date_to)
        if filters.duration_min is not None:
            q = q.where(Article.tour_duration_hours >= filters.duration_min)
        if filters.duration_max is not None:
            q = q.where(Article.tour_duration_hours <= filters.duration_max)
        if filters.generated_from:
            q = q.where(Article.generation_timestamp >= filters.generated_from)
        if filters.generated_to:
            q = q.where(Article.generation_timestamp <= filters.generated_to)

        # Count total (ohne Limit/Offset)
        count_q = select(func.count()).select_from(q.subquery())
        total = self.session.execute(count_q).scalar_one()

        q = q.order_by(Article.generation_timestamp.desc())
        q = q.offset(filters.offset).limit(filters.limit)
        articles = self.session.execute(q).scalars().all()

        return articles, total

    def get_by_id(self, article_id: int) -> Optional[Article]:
        """Holt einen einzelnen Artikel inkl. Bilder."""
        q = select(Article).where(Article.id == article_id)
        return self.session.execute(q).scalar_one_or_none()

    def delete(self, article_id: int) -> bool:
        """Löscht einen Artikel und seine Bilder (CASCADE). Gibt True zurück wenn gelöscht."""
        article = self.get_by_id(article_id)
        if article is None:
            return False
        self.session.delete(article)
        self.session.commit()
        return True
