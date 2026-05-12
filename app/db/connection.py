# app/db/connection.py
import os
from pathlib import Path
from sqlalchemy import create_engine, Index
from sqlalchemy.orm import sessionmaker, Session
from app.db.models import Base, Article, Photobook

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///travel_agent.db")

_engine = None
_SessionLocal = None


def _run_migrations():
    """Führt Alembic-Migrationen aus; fällt auf create_all zurück falls keine Migrationen existieren."""
    if ":memory:" in DATABASE_URL or DATABASE_URL.startswith("sqlite+aiosqlite"):
        Base.metadata.create_all(_get_engine())
        _ensure_indexes()
        return
    try:
        from alembic.config import Config
        from alembic import command
        base_dir = Path(__file__).resolve().parent.parent.parent
        alembic_ini = base_dir / "alembic.ini"
        if alembic_ini.exists():
            alembic_cfg = Config(str(alembic_ini))
            alembic_cfg.set_main_option("script_location", str(base_dir / "migrations"))
            alembic_cfg.set_main_option("sqlalchemy.url", DATABASE_URL)
            command.upgrade(alembic_cfg, "head")
            # Nach Alembic: create_all für Tabellen ohne Migration (z.B. neue Features)
            Base.metadata.create_all(_get_engine())
            _ensure_indexes()
            return
    except Exception as e:
        import logging
        logging.getLogger("app.db.connection").error(
            "Alembic-Migration fehlgeschlagen, falle auf create_all zurück: %s", e
        )
    Base.metadata.create_all(_get_engine())
    _ensure_indexes()


def _get_engine():
    global _engine
    if _engine is None:
        connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
        _engine = create_engine(DATABASE_URL, connect_args=connect_args, echo=False)
        if DATABASE_URL.startswith("sqlite"):
            from sqlalchemy import event
            @event.listens_for(_engine, "connect")
            def _set_sqlite_pragma(dbapi_connection, connection_record):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA journal_mode=WAL;")
                cursor.close()
        _run_migrations()
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
    for model, table_name in [(Article, "articles"), (Photobook, "photobooks")]:
        existing = inspector.get_indexes(table_name)
        existing_names = [idx["name"] for idx in existing]
        for col in ["tour_date", "generation_timestamp", "tour_duration_hours"]:
            idx_name = f"idx_{table_name}_{col}"
            if idx_name not in existing_names:
                Index(idx_name, model.__table__.c[col]).create(engine)
    # Composite-Index für articles.status + generation_timestamp
    existing_article_idx = inspector.get_indexes("articles")
    existing_article_names = [idx["name"] for idx in existing_article_idx]
    if "idx_articles_status" not in existing_article_names:
        Index("idx_articles_status", Article.__table__.c["status"], Article.__table__.c["generation_timestamp"]).create(engine)


def get_session() -> Session:
    """Gibt eine neue SQLAlchemy-Session zurück. Der Aufrufer ist für das Schließen verantwortlich."""
    return _get_session_factory()()
