"""Tests für app/db/connection.py"""
import importlib
import os
from unittest.mock import patch, MagicMock

import pytest
from sqlalchemy.engine import Engine


class TestDatabaseURL:
    def test_defaults_to_sqlite_when_not_set(self):
        import app.db.connection as conn_module
        importlib.reload(conn_module)
        assert conn_module.DATABASE_URL == "sqlite:///travel_agent.db"

    def test_respects_env_variable(self):
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://user:pass@localhost/test"}):
            import app.db.connection as conn_module
            importlib.reload(conn_module)
            assert conn_module.DATABASE_URL == "postgresql://user:pass@localhost/test"


class TestGetEngine:
    def test_creates_sqlite_engine_with_check_same_thread(self):
        import app.db.connection as conn_module
        importlib.reload(conn_module)
        conn_module._engine = None
        conn_module.DATABASE_URL = "sqlite:///:memory:"
        engine = conn_module._get_engine()
        assert isinstance(engine, Engine)
        assert engine.url.database == ":memory:"

    def test_engine_is_singleton(self):
        import app.db.connection as conn_module
        importlib.reload(conn_module)
        conn_module._engine = None
        conn_module.DATABASE_URL = "sqlite:///:memory:"
        engine1 = conn_module._get_engine()
        engine2 = conn_module._get_engine()
        assert engine1 is engine2


class TestGetSession:
    def test_returns_valid_session(self):
        import app.db.connection as conn_module
        importlib.reload(conn_module)
        conn_module._engine = None
        conn_module._SessionLocal = None
        conn_module.DATABASE_URL = "sqlite:///:memory:"
        session = conn_module.get_session()
        assert session is not None
        session.close()

    def test_session_factory_is_singleton(self):
        import app.db.connection as conn_module
        importlib.reload(conn_module)
        conn_module._engine = None
        conn_module._SessionLocal = None
        conn_module.DATABASE_URL = "sqlite:///:memory:"
        factory1 = conn_module._get_session_factory()
        factory2 = conn_module._get_session_factory()
        assert factory1 is factory2


class TestIndexCreation:
    def test_ensure_indexes_runs_without_error(self):
        import app.db.connection as conn_module
        importlib.reload(conn_module)
        conn_module._engine = None
        conn_module.DATABASE_URL = "sqlite:///:memory:"
        conn_module._ensure_indexes()  # Sollte nicht crashen
