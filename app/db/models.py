# app/db/models.py
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, Date, DateTime, Text, ForeignKey
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class Article(Base):
    __tablename__ = "articles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String, nullable=True)
    tour_date = Column(Date, nullable=True)
    tour_duration_hours = Column(Float, nullable=True)
    tour_duration_source = Column(String, nullable=True)
    generation_timestamp = Column(DateTime, default=datetime.now)
    gpx_file = Column(String, nullable=True)
    total_distance_km = Column(Float, nullable=True)
    elevation_gain_m = Column(Float, nullable=True)
    elevation_loss_m = Column(Float, nullable=True)
    image_count = Column(Integer, nullable=True)
    markdown_content = Column(Text, nullable=True)
    html_content = Column(Text, nullable=True)
    markdown_path = Column(String, nullable=True)
    html_path = Column(String, nullable=True)
    model_used = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.now)

    images = relationship("ArticleImage", back_populates="article", cascade="all, delete-orphan")


class ArticleImage(Base):
    __tablename__ = "article_images"

    id = Column(Integer, primary_key=True, autoincrement=True)
    article_id = Column(Integer, ForeignKey("articles.id", ondelete="CASCADE"), nullable=False)
    image_path = Column(String, nullable=False)
    is_map = Column(Boolean, default=False)
    is_elevation_profile = Column(Boolean, default=False)

    article = relationship("Article", back_populates="images")
