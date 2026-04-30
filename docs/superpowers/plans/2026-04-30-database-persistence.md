# Database Persistence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add SQLAlchemy-based persistence for generated blog posts and a Svelte frontend for browsing/filtering articles.

**Architecture:** New `app/db/` module (models, connection, repository) with SQLAlchemy. New pipeline node `persist_article` inserted after `generate_blog_post`. Three new REST endpoints in FastAPI. Frontend uses a lightweight hash-based router store with two new components (ArticleList, ArticleDetail) displayed in the existing main area.

**Tech Stack:** SQLAlchemy 2.0, Alembic, Svelte 5 (runes mode), FastAPI TestClient for tests.

---

### Task 1: Add Database Dependencies

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add sqlalchemy and alembic to dependencies**

```toml
# In pyproject.toml, add to the [project] dependencies list:
    "sqlalchemy>=2.0",
    "alembic>=1.14",
```

- [ ] **Step 2: Install the new dependencies**

Run: `uv sync`
Expected: Should complete without errors.

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "build: add sqlalchemy and alembic dependencies"
```

---

### Task 2: Create DB Models

**Files:**
- Create: `app/db/__init__.py`
- Create: `app/db/models.py`

- [ ] **Step 1: Create `app/db/__init__.py`**

```python
# app/db/__init__.py
```

- [ ] **Step 2: Create `app/db/models.py`**

```python
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
```

- [ ] **Step 3: Commit**

```bash
git add app/db/__init__.py app/db/models.py
git commit -m "feat: add Article and ArticleImage SQLAlchemy models"
```

---

### Task 3: Create DB Connection Module

**Files:**
- Create: `app/db/connection.py`

- [ ] **Step 1: Create `app/db/connection.py`**

```python
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
```

- [ ] **Step 2: Commit**

```bash
git add app/db/connection.py
git commit -m "feat: add DB connection module with lazy init and auto-indexes"
```

---

### Task 4: Create Article Repository

**Files:**
- Create: `app/db/repository.py`

- [ ] **Step 1: Create `app/db/repository.py`**

```python
# app/db/repository.py
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.db.connection import get_session
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
```

- [ ] **Step 2: Commit**

```bash
git add app/db/repository.py
git commit -m "feat: add ArticleRepository with filtered list, get, insert, delete"
```

---

### Task 5: Write Repository Tests

**Files:**
- Create: `tests/test_repository.py`

- [ ] **Step 1: Create `tests/test_repository.py`**

```python
# tests/test_repository.py
from datetime import date, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.models import Base, Article
from app.db.repository import ArticleFilters, ArticleRepository


def _create_session() -> Session:
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    return Session(engine)


class TestArticleRepository:
    def test_insert_and_get_by_id(self):
        session = _create_session()
        repo = ArticleRepository(session)

        article_id = repo.insert(
            article_data={
                "title": "Test Wanderung",
                "tour_date": date(2026, 4, 15),
                "tour_duration_hours": 4.5,
                "tour_duration_source": "gpx",
                "generation_timestamp": datetime(2026, 4, 30, 12, 0, 0),
                "gpx_file": "/data/test.gpx",
                "total_distance_km": 12.3,
                "elevation_gain_m": 800,
                "elevation_loss_m": 500,
                "image_count": 2,
                "markdown_content": "# Test\nInhalt",
                "html_content": "<h1>Test</h1>",
                "markdown_path": "output/test/blogpost.md",
                "html_path": "output/test/blogpost.html",
                "model_used": "gemma4:26b-ctx128k",
                "notes": "Schöne Tour",
            },
            images=[
                {"image_path": "./images/01_test.jpg", "is_map": False, "is_elevation_profile": False},
                {"image_path": "./images/00_map.png", "is_map": True, "is_elevation_profile": False},
            ],
        )

        article = repo.get_by_id(article_id)
        assert article is not None
        assert article.title == "Test Wanderung"
        assert article.tour_date == date(2026, 4, 15)
        assert article.total_distance_km == 12.3
        assert len(article.images) == 2
        assert article.images[0].image_path == "./images/01_test.jpg"

    def test_list_with_tour_date_filter(self):
        session = _create_session()
        repo = ArticleRepository(session)

        repo.insert(
            article_data={"tour_date": date(2026, 4, 1), "title": "April-Tour"},
            images=[],
        )
        repo.insert(
            article_data={"tour_date": date(2026, 5, 15), "title": "Mai-Tour"},
            images=[],
        )

        articles, total = repo.list(ArticleFilters(tour_date_from=date(2026, 5, 1)))
        assert total == 1
        assert articles[0].title == "Mai-Tour"

    def test_list_with_duration_range(self):
        session = _create_session()
        repo = ArticleRepository(session)

        repo.insert(article_data={"tour_duration_hours": 2.0, "title": "Kurz"}, images=[])
        repo.insert(article_data={"tour_duration_hours": 8.0, "title": "Lang"}, images=[])

        articles, total = repo.list(ArticleFilters(duration_min=3.0, duration_max=10.0))
        assert total == 1
        assert articles[0].title == "Lang"

    def test_list_with_generation_timestamp_filter(self):
        session = _create_session()
        repo = ArticleRepository(session)

        repo.insert(
            article_data={
                "generation_timestamp": datetime(2026, 4, 1, 10, 0),
                "title": "Alt",
            },
            images=[],
        )
        repo.insert(
            article_data={
                "generation_timestamp": datetime(2026, 5, 1, 10, 0),
                "title": "Neu",
            },
            images=[],
        )

        articles, total = repo.list(
            ArticleFilters(generated_from=datetime(2026, 4, 15))
        )
        assert total == 1
        assert articles[0].title == "Neu"

    def test_list_pagination(self):
        session = _create_session()
        repo = ArticleRepository(session)

        for i in range(5):
            repo.insert(article_data={"title": f"Tour {i}"}, images=[])

        articles, total = repo.list(ArticleFilters(limit=3, offset=0))
        assert total == 5
        assert len(articles) == 3

        articles2, _ = repo.list(ArticleFilters(limit=3, offset=3))
        assert len(articles2) == 2

    def test_delete_article(self):
        session = _create_session()
        repo = ArticleRepository(session)

        article_id = repo.insert(article_data={"title": "Zu löschen"}, images=[])
        assert repo.get_by_id(article_id) is not None

        result = repo.delete(article_id)
        assert result is True
        assert repo.get_by_id(article_id) is None

    def test_delete_nonexistent(self):
        session = _create_session()
        repo = ArticleRepository(session)

        result = repo.delete(999)
        assert result is False

    def test_get_by_id_nonexistent(self):
        session = _create_session()
        repo = ArticleRepository(session)

        article = repo.get_by_id(999)
        assert article is None

    def test_tour_duration_source_is_null_when_not_provided(self):
        session = _create_session()
        repo = ArticleRepository(session)

        article_id = repo.insert(article_data={"title": "Keine Dauer"}, images=[])
        article = repo.get_by_id(article_id)

        assert article.tour_duration_hours is None
        assert article.tour_duration_source is None
```

- [ ] **Step 2: Run tests**

Run: `uv run pytest tests/test_repository.py -v`
Expected: 9 tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_repository.py
git commit -m "test: add repository unit tests"
```

---

### Task 6: Create Persist Article Service

**Files:**
- Create: `app/services/persist_article.py`

- [ ] **Step 1: Create `app/services/persist_article.py`**

```python
# app/services/persist_article.py
"""Service zum Persistieren generierter Blogposts in der Datenbank."""
from datetime import datetime, date
from typing import Optional, List, Dict, Any

from app.db.connection import get_session
from app.db.repository import ArticleRepository


def _extract_title(markdown: str) -> Optional[str]:
    """Extrahiert den H1-Titel aus dem Markdown-Text."""
    for line in markdown.split("\n"):
        line = line.strip()
        if line.startswith("# ") and not line.startswith("## "):
            return line[2:].strip()
    return None


def _compute_tour_date_and_duration(gpx_stats, images) -> tuple[Optional[date], Optional[float], Optional[str]]:
    """
    Berechnet tour_date und tour_duration aus GPX oder Foto-Timestamps.
    Gibt (tour_date, tour_duration_hours, tour_duration_source) zurück.
    """
    # GPX primary source
    if gpx_stats and hasattr(gpx_stats, "points") and gpx_stats.points:
        points = gpx_stats.points
        if len(points) >= 2 and points[0].time and points[-1].time:
            start = points[0].time
            end = points[-1].time
            duration_hours = (end - start).total_seconds() / 3600.0
            return start.date(), abs(duration_hours), "gpx"

    # Photos fallback
    if images:
        timestamps = [
            datetime.fromisoformat(img.get("timestamp"))
            for img in images
            if isinstance(img, dict) and img.get("timestamp")
        ]
        if len(timestamps) >= 2:
            start = min(timestamps)
            end = max(timestamps)
            duration_hours = (end - start).total_seconds() / 3600.0
            return start.date(), abs(duration_hours), "photos"

    return None, None, None


def persist_article(
    blog_post: Dict[str, Any],
    gpx_stats: Any,
    images: list,
    gpx_file: str,
    model: str,
    notes: Optional[str] = None,
) -> Optional[int]:
    """
    Persistiert einen generierten Blogpost in der Datenbank.

    Args:
        blog_post: Das Ergebnis von generate_blog_post (dict mit markdown, html, file_paths, selected_images)
        gpx_stats: GPXStats-Objekt aus dem State
        images: Liste der im Blog verwendeten Bilder (List[ImageData])
        gpx_file: Pfad zur GPX-Datei
        model: Verwendetes Modell
        notes: Optional: Notizen zur Tour

    Returns:
        article_id oder None bei Fehler
    """
    if not blog_post or not blog_post.get("success"):
        return None

    markdown = blog_post.get("markdown", "")
    html = blog_post.get("html", "")
    file_paths = blog_post.get("file_paths", {})
    selected_images = blog_post.get("selected_images", [])

    tour_date, tour_duration_hours, tour_duration_source = _compute_tour_date_and_duration(
        gpx_stats, [img.model_dump() for img in images] if images else []
    )

    distance_m = gpx_stats.total_distance_m if gpx_stats else None
    gain_m = gpx_stats.elevation_gain_m if gpx_stats else None
    loss_m = gpx_stats.elevation_loss_m if gpx_stats else None

    article_data = {
        "title": _extract_title(markdown),
        "tour_date": tour_date,
        "tour_duration_hours": round(tour_duration_hours, 2) if tour_duration_hours else None,
        "tour_duration_source": tour_duration_source,
        "generation_timestamp": datetime.now(),
        "gpx_file": gpx_file,
        "total_distance_km": round(distance_m / 1000.0, 2) if distance_m else None,
        "elevation_gain_m": round(gain_m, 0) if gain_m else None,
        "elevation_loss_m": round(loss_m, 0) if loss_m else None,
        "image_count": len(selected_images),
        "markdown_content": markdown,
        "html_content": html,
        "markdown_path": file_paths.get("markdown", ""),
        "html_path": file_paths.get("html", ""),
        "model_used": model,
        "notes": notes,
    }

    image_records = []
    for img_path in selected_images:
        image_records.append({
            "image_path": img_path,
            "is_map": img_path.endswith("00_map.png"),
            "is_elevation_profile": img_path.endswith("00_elevation_profile.png"),
        })

    try:
        session = get_session()
        try:
            repo = ArticleRepository(session)
            article_id = repo.insert(article_data, image_records)
            return article_id
        finally:
            session.close()
    except Exception as e:
        print(f"❌ Fehler beim Persistieren des Artikels: {e}")
        return None
```

- [ ] **Step 2: Commit**

```bash
git add app/services/persist_article.py
git commit -m "feat: add persist_article service with GPX/photo duration computation"
```

---

### Task 7: Create Persist Article Node

**Files:**
- Create: `app/nodes/persist_article.py`

- [ ] **Step 1: Create `app/nodes/persist_article.py`**

```python
# app/nodes/persist_article.py
from app.state import AppState
from app.services.persist_article import persist_article


def persist_article_node(state: AppState) -> AppState:
    """Persistiert den generierten Blogpost in der Datenbank."""
    print("💾 Persisting article to database...")

    if not state.blog_post:
        print("⚠️ No blog post to persist.")
        return state

    article_id = persist_article(
        blog_post=state.blog_post,
        gpx_stats=state.gpx_stats,
        images=state.images,
        gpx_file=state.gpx_file,
        model=state.model,
        notes=state.notes,
    )

    if article_id:
        print(f"✅ Article persisted with ID: {article_id}")
        state.metadata["article_id"] = article_id
    else:
        print("⚠️ Article was not persisted (generation failed or DB error).")
        state.metadata["article_id"] = None

    return state
```

- [ ] **Step 2: Commit**

```bash
git add app/nodes/persist_article.py
git commit -m "feat: add persist_article pipeline node"
```

---

### Task 8: Write Persist Article Tests

**Files:**
- Create: `tests/test_persist_service.py`

- [ ] **Step 1: Create `tests/test_persist_service.py`**

```python
# tests/test_persist_service.py
from datetime import datetime, date
import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.models import Base
from app.db.repository import ArticleRepository


class FakePoint:
    def __init__(self, time_val):
        self.time = time_val


class FakeGPXStats:
    def __init__(self):
        self.total_distance_m = 12300.0
        self.elevation_gain_m = 800.0
        self.elevation_loss_m = 500.0
        self.points = [
            FakePoint(datetime(2026, 4, 15, 8, 0, 0)),
            FakePoint(datetime(2026, 4, 15, 12, 30, 0)),
            FakePoint(datetime(2026, 4, 15, 12, 30, 10)),
        ]


class TestPersistArticleService:
    def test_persist_with_full_data(self, monkeypatch):
        """Integrationstest: Service persistiert vollständigen Blogpost."""
        from app.services.persist_article import persist_article
        from app.db import connection as conn_module

        # SQLite in-memory für den Test
        engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(engine)
        session = Session(engine)

        monkeypatch.setattr(conn_module, "_engine", engine)
        monkeypatch.setattr(conn_module, "_SessionLocal", None)

        def fake_get_session():
            # Immer denselben Session-Objekt zurückgeben
            return session

        monkeypatch.setattr(conn_module, "get_session", fake_get_session)

        blog_post = {
            "success": True,
            "markdown": "# Unsere große Wanderung\n\nEin toller Tag!",
            "html": "<h1>Unsere große Wanderung</h1><p>Ein toller Tag!</p>",
            "file_paths": {
                "markdown": "output/test/blogpost.md",
                "html": "output/test/blogpost.html",
            },
            "selected_images": [
                "./images/00_map.png",
                "./images/01_test.jpg",
            ],
            "descriptions": {
                "Hier ist die Übersichtskarte der Route": "./images/00_map.png",
                "Testbild": "./images/01_test.jpg",
            },
        }

        gpx_stats = FakeGPXStats()

        article_id = persist_article(
            blog_post=blog_post,
            gpx_stats=gpx_stats,
            images=[],
            gpx_file="/data/test.gpx",
            model="gemma4:26b-ctx128k",
            notes="Schöne Tour!",
        )

        assert article_id is not None

        repo = ArticleRepository(session)
        article = repo.get_by_id(article_id)
        assert article is not None
        assert article.title == "Unsere große Wanderung"
        assert article.tour_date == date(2026, 4, 15)
        assert article.tour_duration_hours == pytest.approx(4.5, rel=0.01)
        assert article.tour_duration_source == "gpx"
        assert article.total_distance_km == 12.3
        assert article.elevation_gain_m == 800.0
        assert article.elevation_loss_m == 500.0
        assert article.image_count == 2
        assert article.model_used == "gemma4:26b-ctx128k"
        assert article.notes == "Schöne Tour!"
        assert len(article.images) == 2
        assert article.images[0].image_path == "./images/00_map.png"
        assert article.images[0].is_map is True
        assert article.images[1].is_map is False

        session.close()

    def test_persist_with_failed_generation_returns_none(self):
        """Kein Persistieren wenn blog_post nicht erfolgreich war."""
        from app.services.persist_article import persist_article

        blog_post = {"success": False, "error": "Generation failed"}
        article_id = persist_article(
            blog_post=blog_post,
            gpx_stats=None,
            images=[],
            gpx_file="",
            model="",
        )
        assert article_id is None

    def test_persist_without_gpx_uses_photos_for_duration(self, monkeypatch):
        """Fallback auf Foto-Timestamps wenn keine GPX-Daten."""
        from app.services.persist_article import persist_article
        from app.db import connection as conn_module

        engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(engine)
        session = Session(engine)

        monkeypatch.setattr(conn_module, "_engine", engine)
        monkeypatch.setattr(conn_module, "_SessionLocal", None)
        monkeypatch.setattr(conn_module, "get_session", lambda: session)

        blog_post = {
            "success": True,
            "markdown": "# Fotobasierte Wanderung",
            "html": "",
            "file_paths": {"markdown": "", "html": ""},
            "selected_images": [],
            "descriptions": {},
        }

        images_with_timestamps = [
            {"path": "img1.jpg", "timestamp": "2026-04-20T08:00:00"},
            {"path": "img2.jpg", "timestamp": "2026-04-20T14:00:00"},
        ]

        # GPX-Objekt ohne Zeitstempel simulieren
        class GPXWithoutTime:
            total_distance_m = None
            elevation_gain_m = None
            elevation_loss_m = None
            points = []

        article_id = persist_article(
            blog_post=blog_post,
            gpx_stats=GPXWithoutTime(),
            images=images_with_timestamps,
            gpx_file="",
            model="",
        )

        repo = ArticleRepository(session)
        article = repo.get_by_id(article_id)
        assert article.tour_duration_source == "photos"
        assert article.tour_duration_hours == 6.0

        session.close()
```

- [ ] **Step 2: Run tests**

Run: `uv run pytest tests/test_persist_service.py -v`
Expected: 3 tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_persist_service.py
git commit -m "test: add persist_article service tests"
```

---

### Task 9: Integrate Persist Node into Graph

**Files:**
- Modify: `app/graph.py`

- [ ] **Step 1: Read the current graph.py**

The file is at `app/graph.py`. We need to add:
1. Import for `persist_article_node`
2. Node name in `NODE_NAMES`
3. Node wrapper
4. Node registration
5. Edge from `generate_blog_post` to `persist_article`
6. Change `set_finish_point` to `persist_article`

- [ ] **Step 2: Add import**

Find: `from app.nodes.review_content_node import review_content_node`

Add after:
```python
from app.nodes.persist_article import persist_article_node
```

- [ ] **Step 3: Add node name to NODE_NAMES**

Find: `"review_content": "Inhalte prüfen",`

Add after:
```python
    "persist_article": "Artikel speichern",
```

- [ ] **Step 4: Add node wrapper**

Find:
```python
    rcn = _wrap_node(review_content_node, "review_content", event_emitter) if event_emitter else review_content_node
```

Add after:
```python
    pan = _wrap_node(persist_article_node, "persist_article", event_emitter) if event_emitter else persist_article_node
```

- [ ] **Step 5: Register node**

Find:
```python
    builder.add_node("review_content", rcn)
```

Add after:
```python
    builder.add_node("persist_article", pan)
```

- [ ] **Step 6: Add edge and update finish point**

Find:
```python
    builder.add_edge("review_content", "generate_blog_post")

    builder.set_finish_point("generate_blog_post")
```

Replace with:
```python
    builder.add_edge("review_content", "generate_blog_post")
    builder.add_edge("generate_blog_post", "persist_article")

    builder.set_finish_point("persist_article")
```

- [ ] **Step 7: Verify the file**

The complete `build_graph` function should now end with:
```python
    builder.add_edge("enrich_poi", "select_images")
    builder.add_edge("select_images", "review_content")
    builder.add_edge("review_content", "generate_blog_post")
    builder.add_edge("generate_blog_post", "persist_article")

    builder.set_finish_point("persist_article")

    return builder.compile()
```

- [ ] **Step 8: Commit**

```bash
git add app/graph.py
git commit -m "feat: add persist_article node to pipeline graph"
```

---

### Task 10: Add API Endpoints for Articles

**Files:**
- Modify: `app/api/routes.py`

- [ ] **Step 1: Add imports at top of routes.py**

Find:
```python
from pathlib import Path
```

Add after:
```python
from datetime import date, datetime
from typing import Optional
```

Find:
```python
from app.api.events import event_manager
from app.state import AVAILABLE_MODELS
```

Add after:
```python
from app.db.connection import get_session
from app.db.repository import ArticleRepository, ArticleFilters
from app.db.models import Article, ArticleImage
import shutil
```

- [ ] **Step 2: Add helper to serialize article to dict**

Add before the `router = APIRouter(prefix="/api")` line:
```python
def _article_to_summary(a: Article) -> dict:
    return {
        "id": a.id,
        "title": a.title,
        "tour_date": a.tour_date.isoformat() if a.tour_date else None,
        "tour_duration_hours": a.tour_duration_hours,
        "tour_duration_source": a.tour_duration_source,
        "generation_timestamp": a.generation_timestamp.isoformat() if a.generation_timestamp else None,
        "total_distance_km": a.total_distance_km,
        "elevation_gain_m": a.elevation_gain_m,
        "elevation_loss_m": a.elevation_loss_m,
        "image_count": a.image_count,
        "model_used": a.model_used,
        "notes": a.notes,
    }


def _article_to_detail(a: Article) -> dict:
    return {
        **_article_to_summary(a),
        "markdown_content": a.markdown_content,
        "html_content": a.html_content,
        "markdown_path": a.markdown_path,
        "html_path": a.html_path,
        "gpx_file": a.gpx_file,
        "images": [
            {
                "image_path": img.image_path,
                "is_map": img.is_map,
                "is_elevation_profile": img.is_elevation_profile,
            }
            for img in a.images
        ],
    }
```

- [ ] **Step 3: Add the three endpoints before the SSE Streaming section**

Find:
```python
# ── SSE Streaming ──────────────────────────────────────
```

Insert before:
```python
# ── Articles ──────────────────────────────────────────

@router.get("/articles")
async def get_articles(
    tour_date_from: Optional[str] = None,
    tour_date_to: Optional[str] = None,
    duration_min: Optional[float] = None,
    duration_max: Optional[float] = None,
    generated_from: Optional[str] = None,
    generated_to: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
):
    """Liste aller persistierten Artikel mit optionalen Filtern."""
    filters = ArticleFilters(limit=limit, offset=offset)

    if tour_date_from:
        filters.tour_date_from = date.fromisoformat(tour_date_from)
    if tour_date_to:
        filters.tour_date_to = date.fromisoformat(tour_date_to)
    if duration_min is not None:
        filters.duration_min = duration_min
    if duration_max is not None:
        filters.duration_max = duration_max
    if generated_from:
        filters.generated_from = datetime.fromisoformat(generated_from)
    if generated_to:
        filters.generated_to = datetime.fromisoformat(generated_to)

    session = get_session()
    try:
        repo = ArticleRepository(session)
        articles, total = repo.list(filters)
        return {
            "articles": [_article_to_summary(a) for a in articles],
            "total": total,
        }
    finally:
        session.close()


@router.get("/articles/{article_id}")
async def get_article(article_id: int):
    """Einzelnen Artikel mit vollständigem Inhalt abrufen."""
    session = get_session()
    try:
        repo = ArticleRepository(session)
        article = repo.get_by_id(article_id)
        if article is None:
            raise HTTPException(status_code=404, detail="Article not found")
        return {"article": _article_to_detail(article)}
    finally:
        session.close()


@router.delete("/articles/{article_id}")
async def delete_article(article_id: int):
    """Artikel und zugehörige Dateien löschen."""
    session = get_session()
    try:
        repo = ArticleRepository(session)
        article = repo.get_by_id(article_id)
        if article is None:
            raise HTTPException(status_code=404, detail="Article not found")

        output_dir = os.path.dirname(article.markdown_path) if article.markdown_path else None
        repo.delete(article_id)

        if output_dir and os.path.exists(output_dir):
            try:
                shutil.rmtree(output_dir)
            except OSError as e:
                print(f"⚠️ Konnte Output-Verzeichnis nicht löschen: {e}")

        return {"deleted": article_id}
    finally:
        session.close()
```

- [ ] **Step 4: Commit**

```bash
git add app/api/routes.py
git commit -m "feat: add /api/articles endpoints with filtering and delete"
```

---

### Task 11: Write API Endpoint Tests

**Files:**
- Modify: `tests/test_api.py` (append new test classes)

- [ ] **Step 1: Add test cases at the end of `tests/test_api.py`**

```python
# tests/test_api.py — append these classes after the existing TestEventManager class


class TestArticlesList:
    def test_list_empty_returns_empty_array(self, client):
        response = client.get("/api/articles")
        assert response.status_code == 200
        data = response.json()
        assert data["articles"] == []
        assert data["total"] == 0

    def test_list_with_filters(self, client, monkeypatch):
        """Testet GET /api/articles mit Filtern."""
        from datetime import date as date_type, datetime as datetime_type
        from app.db import connection as conn_module
        from app.db.models import Base
        from app.db.repository import ArticleRepository
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session

        engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(engine)
        session = Session(engine)

        monkeypatch.setattr(conn_module, "_engine", engine)
        monkeypatch.setattr(conn_module, "_SessionLocal", None)
        monkeypatch.setattr(conn_module, "get_session", lambda: Session(engine))

        repo = ArticleRepository(session)
        repo.insert(
            article_data={
                "title": "Test Tour",
                "tour_date": date_type(2026, 4, 15),
                "tour_duration_hours": 5.0,
                "generation_timestamp": datetime_type(2026, 4, 30, 12, 0, 0),
                "markdown_content": "# Test",
                "html_content": "<h1>Test</h1>",
                "markdown_path": "output/test/md.md",
                "html_path": "output/test/html.html",
            },
            images=[],
        )
        session.commit()

        response = client.get("/api/articles?tour_date_from=2026-04-01&tour_date_to=2026-05-01")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["articles"][0]["title"] == "Test Tour"
        assert data["articles"][0]["tour_duration_hours"] == 5.0
        assert data["articles"][0]["tour_date"] == "2026-04-15"
        assert "markdown_content" not in data["articles"][0]

        session.close()

    def test_list_no_filters_returns_all(self, client, monkeypatch):
        from datetime import date as date_type, datetime as datetime_type
        from app.db import connection as conn_module
        from app.db.models import Base
        from app.db.repository import ArticleRepository
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session

        engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(engine)
        session = Session(engine)

        monkeypatch.setattr(conn_module, "_engine", engine)
        monkeypatch.setattr(conn_module, "_SessionLocal", None)
        monkeypatch.setattr(conn_module, "get_session", lambda: Session(engine))

        repo = ArticleRepository(session)
        repo.insert(article_data={"title": "A"}, images=[])
        repo.insert(article_data={"title": "B"}, images=[])
        session.commit()

        response = client.get("/api/articles")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["articles"]) == 2

        session.close()


class TestArticleDetail:
    def test_get_by_valid_id(self, client, monkeypatch):
        from datetime import date as date_type, datetime as datetime_type
        from app.db import connection as conn_module
        from app.db.models import Base
        from app.db.repository import ArticleRepository
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session

        engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(engine)
        session = Session(engine)

        monkeypatch.setattr(conn_module, "_engine", engine)
        monkeypatch.setattr(conn_module, "_SessionLocal", None)
        monkeypatch.setattr(conn_module, "get_session", lambda: Session(engine))

        repo = ArticleRepository(session)
        article_id = repo.insert(
            article_data={
                "title": "Detail Test",
                "markdown_content": "# Detail Test\nContent",
                "html_content": "<h1>Detail Test</h1><p>Content</p>",
                "markdown_path": "output/test/md.md",
                "html_path": "output/test/html.html",
            },
            images=[
                {"image_path": "./images/01.jpg", "is_map": False, "is_elevation_profile": False},
            ],
        )
        session.commit()

        response = client.get(f"/api/articles/{article_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["article"]["id"] == article_id
        assert data["article"]["title"] == "Detail Test"
        assert data["article"]["markdown_content"] == "# Detail Test\nContent"
        assert len(data["article"]["images"]) == 1

        session.close()

    def test_get_by_invalid_id_returns_404(self, client):
        response = client.get("/api/articles/99999")
        assert response.status_code == 404


class TestArticleDelete:
    def test_delete_existing_article(self, client, monkeypatch):
        from app.db import connection as conn_module
        from app.db.models import Base
        from app.db.repository import ArticleRepository
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session

        engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(engine)
        session = Session(engine)

        monkeypatch.setattr(conn_module, "_engine", engine)
        monkeypatch.setattr(conn_module, "_SessionLocal", None)
        monkeypatch.setattr(conn_module, "get_session", lambda: Session(engine))

        repo = ArticleRepository(session)
        article_id = repo.insert(
            article_data={"title": "Delete Me", "markdown_path": "output/test/md.md"},
            images=[],
        )
        session.commit()

        response = client.delete(f"/api/articles/{article_id}")
        assert response.status_code == 200
        assert response.json()["deleted"] == article_id

        # Verify it's gone
        response2 = client.get(f"/api/articles/{article_id}")
        assert response2.status_code == 404

        session.close()

    def test_delete_nonexistent_article_returns_404(self, client):
        response = client.delete("/api/articles/99999")
        assert response.status_code == 404
```

- [ ] **Step 2: Run all API tests**

Run: `uv run pytest tests/test_api.py -v`
Expected: All tests (old + new) PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_api.py
git commit -m "test: add API endpoint tests for article listing, detail, and delete"
```

---

### Task 12: Create Frontend Router Store

**Files:**
- Create: `frontend/src/lib/stores/router.ts`

- [ ] **Step 1: Create `frontend/src/lib/stores/router.ts`**

```typescript
// frontend/src/lib/stores/router.ts
import { writable, derived } from "svelte/store";

export type Route =
  | { page: "pipeline" }
  | { page: "articles" }
  | { page: "article"; id: number };

function parseHash(hash: string): Route {
  const path = hash.replace(/^#\/?/, "") || "/";

  if (path === "/" || path === "" || path === "pipeline") {
    return { page: "pipeline" };
  }

  const articlesMatch = path.match(/^articles\/(\d+)$/);
  if (articlesMatch) {
    return { page: "article", id: parseInt(articlesMatch[1], 10) };
  }

  if (path === "articles") {
    return { page: "articles" };
  }

  return { page: "pipeline" };
}

function currentHash(): string {
  return typeof window !== "undefined" ? window.location.hash : "";
}

export const route = writable<Route>(parseHash(currentHash()));

export function navigateTo(route: Route) {
  let hash: string;
  switch (route.page) {
    case "pipeline":
      hash = "#/";
      break;
    case "articles":
      hash = "#/articles";
      break;
    case "article":
      hash = `#/articles/${route.id}`;
      break;
  }
  window.location.hash = hash;
}

// Listen for hash changes (back/forward browser buttons)
if (typeof window !== "undefined") {
  window.addEventListener("hashchange", () => {
    route.set(parseHash(window.location.hash));
  });
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/lib/stores/router.ts
git commit -m "feat: add hash-based router store for frontend navigation"
```

---

### Task 13: Create ArticleList Component

**Files:**
- Create: `frontend/src/lib/ArticleList.svelte`

- [ ] **Step 1: Create `frontend/src/lib/ArticleList.svelte`**

```svelte
<svelte:options runes />

<script lang="ts">
  import { navigateTo } from "./stores/router";

  interface ArticleSummary {
    id: number;
    title: string | null;
    tour_date: string | null;
    tour_duration_hours: number | null;
    total_distance_km: number | null;
    elevation_gain_m: number | null;
    image_count: number | null;
    generation_timestamp: string | null;
  }

  let articles: ArticleSummary[] = $state([]);
  let total: number = $state(0);
  let loading: boolean = $state(true);
  let error: string | null = $state(null);

  let tourDateFrom: string = $state("");
  let tourDateTo: string = $state("");
  let durationMin: string = $state("");
  let durationMax: string = $state("");

  async function fetchArticles() {
    loading = true;
    error = null;

    try {
      const params = new URLSearchParams();
      if (tourDateFrom) params.set("tour_date_from", tourDateFrom);
      if (tourDateTo) params.set("tour_date_to", tourDateTo);
      if (durationMin) params.set("duration_min", durationMin);
      if (durationMax) params.set("duration_max", durationMax);
      params.set("limit", "50");

      const res = await fetch(`/api/articles?${params.toString()}`);
      if (!res.ok) throw new Error(`API error: ${res.status}`);
      const data = await res.json();
      articles = data.articles;
      total = data.total;
    } catch (e: any) {
      error = e.message;
    } finally {
      loading = false;
    }
  }

  function formatDate(iso: string | null): string {
    if (!iso) return "—";
    return new Date(iso).toLocaleDateString("de-DE");
  }

  function formatDuration(hours: number | null): string {
    if (hours === null || hours === undefined) return "—";
    const h = Math.floor(hours);
    const m = Math.round((hours - h) * 60);
    return `${h}h ${m}m`;
  }

  function handleView(id: number) {
    navigateTo({ page: "article", id });
  }

  // Fetch on mount
  $effect(() => {
    fetchArticles();
  });
</script>

<div class="article-list">
  <div class="header">
    <h2>Gespeicherte Artikel ({total})</h2>
  </div>

  <div class="filters">
    <label>
      Tour-Datum von:
      <input type="date" bind:value={tourDateFrom} />
    </label>
    <label>
      Tour-Datum bis:
      <input type="date" bind:value={tourDateTo} />
    </label>
    <label>
      Dauer (min h):
      <input type="number" bind:value={durationMin} placeholder="z.B. 2" step="0.5" />
    </label>
    <label>
      Dauer (max h):
      <input type="number" bind:value={durationMax} placeholder="z.B. 8" step="0.5" />
    </label>
    <button class="filter-btn" onclick={fetchArticles}>Filtern</button>
  </div>

  {#if loading}
    <p class="status">Lade Artikel...</p>
  {:else if error}
    <p class="status error">Fehler: {error}</p>
  {:else if articles.length === 0}
    <p class="status">Keine Artikel gefunden.</p>
  {:else}
    <div class="table-container">
      <table>
        <thead>
          <tr>
            <th>Titel</th>
            <th>Tour-Datum</th>
            <th>Dauer</th>
            <th>Distanz</th>
            <th>Höhenmeter</th>
            <th>Bilder</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {#each articles as a}
            <tr>
              <td>{a.title || "Ohne Titel"}</td>
              <td>{formatDate(a.tour_date)}</td>
              <td>{formatDuration(a.tour_duration_hours)}</td>
              <td>{a.total_distance_km ? `${a.total_distance_km} km` : "—"}</td>
              <td>{a.elevation_gain_m ? `${a.elevation_gain_m} m` : "—"}</td>
              <td>{a.image_count ?? "—"}</td>
              <td>
                <button class="view-btn" onclick={() => handleView(a.id)}>Ansehen</button>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>

<style>
  .article-list {
    padding: 1rem;
    height: 100%;
    overflow-y: auto;
  }
  .header {
    margin-bottom: 1rem;
  }
  .filters {
    display: flex;
    gap: 0.75rem;
    flex-wrap: wrap;
    margin-bottom: 1rem;
    align-items: flex-end;
  }
  .filters label {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
    font-size: 0.75rem;
    color: var(--text-muted);
  }
  .filters input {
    padding: 0.35rem 0.5rem;
    font-size: 0.8rem;
  }
  .filter-btn {
    padding: 0.4rem 0.75rem;
    background: var(--accent);
    color: white;
    font-size: 0.8rem;
    height: fit-content;
    align-self: flex-end;
  }
  .status {
    color: var(--text-muted);
    padding: 2rem 0;
    text-align: center;
  }
  .status.error {
    color: var(--error);
  }
  .table-container {
    overflow-x: auto;
  }
  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.8rem;
  }
  th {
    text-align: left;
    color: var(--text-muted);
    font-weight: normal;
    padding: 0.5rem 0.5rem;
    border-bottom: 1px solid var(--border);
    white-space: nowrap;
  }
  td {
    padding: 0.5rem;
    border-bottom: 1px solid var(--border);
    white-space: nowrap;
  }
  tr:hover {
    background: rgba(255, 255, 255, 0.03);
  }
  .view-btn {
    padding: 0.3rem 0.6rem;
    background: var(--surface-alt);
    color: var(--text);
    font-size: 0.75rem;
  }
  .view-btn:hover {
    background: var(--accent);
  }
</style>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/lib/ArticleList.svelte
git commit -m "feat: add ArticleList component with filters and data table"
```

---

### Task 14: Create ArticleDetail Component

**Files:**
- Create: `frontend/src/lib/ArticleDetail.svelte`

- [ ] **Step 1: Create `frontend/src/lib/ArticleDetail.svelte`**

```svelte
<svelte:options runes />

<script lang="ts">
  import { navigateTo } from "./stores/router";

  let { id }: { id: number } = $props();

  interface ArticleFull {
    id: number;
    title: string | null;
    tour_date: string | null;
    tour_duration_hours: number | null;
    generation_timestamp: string | null;
    total_distance_km: number | null;
    elevation_gain_m: number | null;
    elevation_loss_m: number | null;
    html_content: string | null;
    markdown_content: string | null;
    markdown_path: string | null;
    html_path: string | null;
    gpx_file: string | null;
    model_used: string | null;
    notes: string | null;
    images: { image_path: string; is_map: boolean; is_elevation_profile: boolean }[];
  }

  let article: ArticleFull | null = $state(null);
  let loading: boolean = $state(true);
  let error: string | null = $state(null);
  let deleting: boolean = $state(false);

  async function fetchArticle() {
    loading = true;
    error = null;
    try {
      const res = await fetch(`/api/articles/${id}`);
      if (!res.ok) {
        if (res.status === 404) throw new Error("Artikel nicht gefunden.");
        throw new Error(`API error: ${res.status}`);
      }
      const data = await res.json();
      article = data.article;
    } catch (e: any) {
      error = e.message;
    } finally {
      loading = false;
    }
  }

  async function handleDelete() {
    if (!confirm("Artikel wirklich löschen? Dies entfernt auch die Dateien.")) return;
    deleting = true;
    try {
      const res = await fetch(`/api/articles/${id}`, { method: "DELETE" });
      if (!res.ok) throw new Error(`Delete failed: ${res.status}`);
      navigateTo({ page: "articles" });
    } catch (e: any) {
      error = e.message;
      deleting = false;
    }
  }

  function formatDate(iso: string | null): string {
    if (!iso) return "—";
    return new Date(iso).toLocaleDateString("de-DE");
  }

  function formatDuration(hours: number | null): string {
    if (hours === null || hours === undefined) return "—";
    const h = Math.floor(hours);
    const m = Math.round((hours - h) * 60);
    return `${h}h ${m}m`;
  }

  $effect(() => {
    fetchArticle();
  });
</script>

<div class="article-detail">
  <div class="toolbar">
    <button class="back-btn" onclick={() => navigateTo({ page: "articles" })}>
      ← Zurück zur Liste
    </button>
    {#if article}
      <button class="delete-btn" onclick={handleDelete} disabled={deleting}>
        {deleting ? "Lösche..." : "🗑 Löschen"}
      </button>
    {/if}
  </div>

  {#if loading}
    <p class="status">Lade Artikel...</p>
  {:else if error}
    <p class="status error">{error}</p>
  {:else if article}
    <h1 class="title">{article.title || "Ohne Titel"}</h1>

    <div class="meta">
      {#if article.tour_date}
        <span>📅 {formatDate(article.tour_date)}</span>
      {/if}
      {#if article.tour_duration_hours}
        <span>⏱ {formatDuration(article.tour_duration_hours)}</span>
      {/if}
      {#if article.total_distance_km}
        <span>📏 {article.total_distance_km} km</span>
      {/if}
      {#if article.elevation_gain_m}
        <span>⛰ {article.elevation_gain_m} m ↑</span>
      {/if}
      {#if article.model_used}
        <span>🤖 {article.model_used}</span>
      {/if}
    </div>

    {#if article.notes}
      <details class="notes-section">
        <summary>Notizen</summary>
        <pre class="notes">{article.notes}</pre>
      </details>
    {/if}

    {#if article.html_content}
      <div class="content">
        {@html article.html_content}
      </div>
    {/if}
  {/if}
</div>

<style>
  .article-detail {
    padding: 1rem;
    height: 100%;
    overflow-y: auto;
  }
  .toolbar {
    display: flex;
    justify-content: space-between;
    margin-bottom: 1rem;
  }
  .back-btn, .delete-btn {
    padding: 0.4rem 0.75rem;
    font-size: 0.8rem;
  }
  .back-btn {
    background: var(--surface-alt);
    color: var(--text);
  }
  .back-btn:hover {
    background: var(--accent);
  }
  .delete-btn {
    background: var(--error);
    color: white;
  }
  .delete-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  .title {
    font-size: 1.5rem;
    margin-bottom: 0.75rem;
  }
  .meta {
    display: flex;
    gap: 1rem;
    flex-wrap: wrap;
    margin-bottom: 1rem;
    color: var(--text-muted);
    font-size: 0.8rem;
  }
  .notes-section {
    margin-bottom: 1rem;
  }
  .notes-section summary {
    cursor: pointer;
    color: var(--accent);
    font-size: 0.85rem;
  }
  .notes {
    background: var(--surface);
    padding: 0.75rem;
    border-radius: 4px;
    margin-top: 0.5rem;
    font-size: 0.8rem;
    white-space: pre-wrap;
  }
  .content {
    line-height: 1.6;
  }
  .content :global(img) {
    max-width: 100%;
    border-radius: 4px;
  }
  .content :global(h1),
  .content :global(h2),
  .content :global(h3) {
    margin-top: 1.25rem;
    margin-bottom: 0.5rem;
  }
  .content :global(p) {
    margin-bottom: 0.75rem;
  }
  .status {
    color: var(--text-muted);
    padding: 2rem 0;
    text-align: center;
  }
  .status.error {
    color: var(--error);
  }
</style>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/lib/ArticleDetail.svelte
git commit -m "feat: add ArticleDetail component with HTML rendering and delete"
```

---

### Task 15: Integrate Navigation into App.svelte

**Files:**
- Modify: `frontend/src/App.svelte`

- [ ] **Step 1: Update App.svelte with navigation and conditional rendering**

Replace the entire file content:
```svelte
<svelte:options runes />

<script lang="ts">
  import { route, navigateTo } from "./lib/stores/router";
  import ModelSelector from "./lib/ModelSelector.svelte";
  import FileDropZone from "./lib/FileDropZone.svelte";
  import OutputDirInput from "./lib/OutputDirInput.svelte";
  import NotesInput from "./lib/NotesInput.svelte";
  import RunButton from "./lib/RunButton.svelte";
  import OutputWindow from "./lib/OutputWindow.svelte";
  import ArticleList from "./lib/ArticleList.svelte";
  import ArticleDetail from "./lib/ArticleDetail.svelte";

  let modelSelector: ModelSelector;
  let fileDropZone: FileDropZone;
  let outputDirInput: OutputDirInput;
  let notesInput: NotesInput;

  let rt = $derived($route);
</script>

<div class="layout">
  <aside class="sidebar">
    <h1 class="title">Travel Agent</h1>

    <nav class="nav-tabs">
      <button
        class="nav-tab"
        class:active={rt.page === "pipeline"}
        onclick={() => navigateTo({ page: "pipeline" })}
      >
        Pipeline
      </button>
      <button
        class="nav-tab"
        class:active={rt.page === "articles" || rt.page === "article"}
        onclick={() => navigateTo({ page: "articles" })}
      >
        Artikel
      </button>
    </nav>

    {#if rt.page === "pipeline"}
      <ModelSelector bind:this={modelSelector} />
      <FileDropZone bind:this={fileDropZone} />
      <OutputDirInput bind:this={outputDirInput} />
      <NotesInput bind:this={notesInput} />

      <div class="run-section">
        <RunButton
          getModel={() => modelSelector.getModel()}
          getFiles={() => fileDropZone.getFiles()}
          getOutputDir={() => outputDirInput.getOutputDir()}
          getNotes={() => notesInput.getNotes()}
        />
      </div>
    {/if}
  </aside>

  <main class="main">
    {#if rt.page === "pipeline"}
      <OutputWindow />
    {:else if rt.page === "articles"}
      <ArticleList />
    {:else if rt.page === "article"}
      <ArticleDetail id={rt.id} />
    {/if}
  </main>
</div>

<style>
  .layout {
    display: flex;
    height: 100vh;
    width: 100vw;
  }
  .sidebar {
    width: 340px;
    min-width: 340px;
    background: var(--surface);
    border-right: 1px solid var(--border);
    padding: 1.25rem;
    display: flex;
    flex-direction: column;
    gap: 1.25rem;
    overflow-y: auto;
  }
  .title {
    font-size: 1rem;
    font-weight: bold;
    color: var(--accent);
    letter-spacing: 0.05em;
    text-transform: uppercase;
  }
  .nav-tabs {
    display: flex;
    gap: 0.25rem;
  }
  .nav-tab {
    flex: 1;
    padding: 0.5rem 0.75rem;
    background: var(--bg);
    color: var(--text-muted);
    font-size: 0.8rem;
  }
  .nav-tab.active {
    background: var(--accent);
    color: white;
  }
  .nav-tab:hover:not(.active) {
    background: var(--surface-alt);
    color: var(--text);
  }
  .run-section {
    margin-top: auto;
    padding-top: 0.5rem;
  }
  .main {
    flex: 1;
    display: flex;
    flex-direction: column;
    padding: 1rem;
    overflow: hidden;
  }
</style>
```

- [ ] **Step 2: Verify the build compiles**

Run: `cd frontend && npm run build`
Expected: Build succeeds with no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/App.svelte
git commit -m "feat: add navigation tabs and article views to frontend"
```

---

### Task 16: Run Full Test Suite

- [ ] **Step 1: Run all tests**

```bash
uv run pytest tests/ -v
```

Expected: All tests PASS (repository + persist_service + API).

- [ ] **Step 2: Verify frontend builds**

```bash
cd frontend && npm run build
```

Expected: Build succeeds.

---

## Verification Checklist

- [ ] `uv run pytest tests/test_repository.py -v` — 9 tests pass
- [ ] `uv run pytest tests/test_persist_service.py -v` — 3 tests pass
- [ ] `uv run pytest tests/test_api.py -v` — all tests pass (existing + new)
- [ ] `cd frontend && npm run build` — compiles without errors
- [ ] `uv run python -c "from app.db.connection import get_session; s = get_session(); s.close(); print('OK')"` — DB connects
- [ ] `uv run python -c "from app.graph import build_graph; g = build_graph(); print('OK')"` — graph compiles with new node
