# app/db/connection.py
import os
from sqlalchemy import create_engine, Index
from sqlalchemy.orm import sessionmaker, Session
from app.db.models import Base, Article

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///travel_agent.db")

_engine = None
_SessionLocal = None


def _get_engine():
    global _engine
    if _engine is None:
        connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
        _engine = create_engine(DATABASE_URL, connect_args=connect_args, echo=False)
        Base.metadata.create_all(_engine)
        _ensure_indexes()
    return _engine


def _get_session_factory() -> sessionmaker[Session]:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=_get_engine())
    return _SessionLocal


def _ensure_indexes():
    """Erstellt Indexe falls sie nicht existieren."""
    engine = _get_engine()
    from sqlalchemy import inspect
    inspector = inspect(engine)
    existing = inspector.get_indexes("articles")
    existing_names = [idx["name"] for idx in existing]
    for col in ["tour_date", "generation_timestamp", "tour_duration_hours"]:
        idx_name = f"idx_articles_{col}"
        if idx_name not in existing_names:
            Index(idx_name, Article.__table__.c[col]).create(engine)


def get_session() -> Session:
    """Gibt eine neue SQLAlchemy-Session zurück. Der Aufrufer ist für das Schließen verantwortlich."""
    return _get_session_factory()()
