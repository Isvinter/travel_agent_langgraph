# app/db/repository.py
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional, List

from sqlalchemy.orm import Session

from app.db.models import Article, ArticleImage
from app.db.base_repository import BaseRepository


@dataclass
class ArticleFilters:
    tour_date_from: Optional[date] = None
    tour_date_to: Optional[date] = None
    duration_min: Optional[float] = None
    duration_max: Optional[float] = None
    generated_from: Optional[datetime] = None
    generated_to: Optional[datetime] = None
    status: Optional[str] = None
    limit: int = 20
    offset: int = 0


class ArticleRepository(BaseRepository[Article, ArticleFilters]):
    """Repository für den Zugriff auf die artikel-Tabelle."""

    model = Article
    image_model = ArticleImage
    image_fk_name = "article_id"

    def insert(self, article_data: dict = None, images: list[dict] = None, **kwargs) -> int:
        return super().insert(article_data, images)

    def _apply_filters(self, q, filters: ArticleFilters):
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
        if filters.status:
            q = q.where(Article.status == filters.status)
        return q
