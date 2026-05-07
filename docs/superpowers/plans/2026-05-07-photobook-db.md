# Photobook Database Persistence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist photobooks to SQLite (new `photobooks` + `photobook_images` tables) and add frontend listing/detail views with sub-tabs under "Datenbank".

**Architecture:** Mirror the existing `Article`/`ArticleRepository`/`/api/articles` pattern for photobooks. New `Photobook` and `PhotobookImage` SQLAlchemy models, `PhotobookRepository`, new API endpoints under `/api/photobooks`, new `persist_photobook` node+service integrated into the photobook pipeline graph branch, and new Svelte components with sub-tab navigation in `App.svelte`.

**Tech Stack:** SQLAlchemy (SQLite), FastAPI, LangGraph, Svelte 5 (runes) + TypeScript

---

## File Structure

| Action | File | Purpose |
|--------|------|---------|
| CREATE | `app/db/photobook_repository.py` | `PhotobookRepository` + `PhotobookFilters` |
| CREATE | `app/services/persist_photobook.py` | Business logic: extract photobook data, insert via repo |
| CREATE | `app/nodes/persist_photobook.py` | Thin LangGraph node wrapper |
| CREATE | `tests/test_photobook_repository.py` | Repository unit tests |
| CREATE | `tests/test_persist_photobook_service.py` | Service integration tests |
| CREATE | `frontend/src/lib/PhotobookList.svelte` | List component with filters, batch delete |
| CREATE | `frontend/src/lib/PhotobookDetail.svelte` | Detail view with HTML rendering, PDF export |
| MODIFY | `app/db/models.py` | Add `Photobook` and `PhotobookImage` models |
| MODIFY | `app/db/connection.py` | Add photobook table indexes |
| MODIFY | `app/graph.py` | Add `persist_photobook` node, wire into photobook branch |
| MODIFY | `app/api/routes.py` | Add 6 photobook endpoints + serializers |
| MODIFY | `app/api/events.py` | Add `photobook_id` param to `complete_run` |
| MODIFY | `frontend/src/lib/stores/router.ts` | Add `photobooks` and `photobook` routes |
| MODIFY | `frontend/src/App.svelte` | Add sub-tabs, import new components |

---

### Task 1: Add Photobook and PhotobookImage SQLAlchemy models

**Files:**
- Modify: `app/db/models.py`

- [ ] **Step 1: Add models**

Add after the `ArticleImage` class (line 45):

```python
class Photobook(Base):
    __tablename__ = "photobooks"

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
    html_content = Column(Text, nullable=True)
    html_path = Column(String, nullable=True)
    model_used = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    pdf_path = Column(String, nullable=True)
    page_count = Column(Integer, nullable=True)
    photobook_size = Column(String, nullable=True)

    images = relationship("PhotobookImage", back_populates="photobook", cascade="all, delete-orphan")


class PhotobookImage(Base):
    __tablename__ = "photobook_images"

    id = Column(Integer, primary_key=True, autoincrement=True)
    photobook_id = Column(Integer, ForeignKey("photobooks.id", ondelete="CASCADE"), nullable=False)
    image_path = Column(String, nullable=False)
    is_map = Column(Boolean, default=False)
    is_elevation_profile = Column(Boolean, default=False)

    photobook = relationship("Photobook", back_populates="images")
```

- [ ] **Step 2: Verify models load**

Run: `uv run python -c "from app.db.models import Photobook, PhotobookImage; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add app/db/models.py
git commit -m "feat: add Photobook and PhotobookImage SQLAlchemy models"
```

---

### Task 2: Add photobook table indexes

**Files:**
- Modify: `app/db/connection.py`

- [ ] **Step 1: Update imports and _ensure_indexes**

Change the import on line 5 from `from app.db.models import Base, Article` to:

```python
from app.db.models import Base, Article, Photobook
```

Replace `_ensure_indexes` (lines 30-40) with:

```python
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
```

- [ ] **Step 2: Verify indexes are created**

Run: `uv run python -c "
from app.db.connection import get_session
session = get_session()
from sqlalchemy import inspect
inspector = inspect(session.get_bind())
idxs = inspector.get_indexes('photobooks')
print([i['name'] for i in idxs])
session.close()
"`
Expected: Output shows `['idx_photobooks_tour_date', 'idx_photobooks_generation_timestamp', 'idx_photobooks_tour_duration_hours']`

- [ ] **Step 3: Commit**

```bash
git add app/db/connection.py
git commit -m "feat: add indexes for photobooks table"
```

---

### Task 3: Write PhotobookRepository tests

**Files:**
- Create: `tests/test_photobook_repository.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_photobook_repository.py
from datetime import date, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.models import Base
from app.db.photobook_repository import PhotobookFilters, PhotobookRepository


def _create_session() -> Session:
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    return Session(engine)


class TestPhotobookRepository:
    def test_insert_and_get_by_id(self):
        session = _create_session()
        repo = PhotobookRepository(session)

        photobook_id = repo.insert(
            photobook_data={
                "title": "Test Fotobuch",
                "tour_date": date(2026, 4, 15),
                "tour_duration_hours": 4.5,
                "tour_duration_source": "gpx",
                "generation_timestamp": datetime(2026, 4, 30, 12, 0, 0),
                "gpx_file": "/data/test.gpx",
                "total_distance_km": 12.3,
                "elevation_gain_m": 800,
                "elevation_loss_m": 500,
                "image_count": 3,
                "html_content": "<h1>Fotobuch</h1>",
                "html_path": "output/photobook_test/test.html",
                "model_used": "gemma4:26b-ctx128k",
                "notes": "Schöne Tour",
                "pdf_path": "output/photobook_test/test.pdf",
                "page_count": 12,
                "photobook_size": "normal",
            },
            images=[
                {"image_path": "./images/01_test.jpg", "is_map": False, "is_elevation_profile": False},
                {"image_path": "./images/00_map.png", "is_map": True, "is_elevation_profile": False},
            ],
        )

        record = repo.get_by_id(photobook_id)
        assert record is not None
        assert record.title == "Test Fotobuch"
        assert record.tour_date == date(2026, 4, 15)
        assert record.total_distance_km == 12.3
        assert record.pdf_path == "output/photobook_test/test.pdf"
        assert record.page_count == 12
        assert record.photobook_size == "normal"
        assert len(record.images) == 2
        assert record.images[0].image_path == "./images/01_test.jpg"

    def test_list_with_tour_date_filter(self):
        session = _create_session()
        repo = PhotobookRepository(session)

        repo.insert(photobook_data={"tour_date": date(2026, 4, 1), "title": "April-Buch"}, images=[])
        repo.insert(photobook_data={"tour_date": date(2026, 5, 15), "title": "Mai-Buch"}, images=[])

        records, total = repo.list(PhotobookFilters(tour_date_from=date(2026, 5, 1)))
        assert total == 1
        assert records[0].title == "Mai-Buch"

    def test_list_with_duration_range(self):
        session = _create_session()
        repo = PhotobookRepository(session)

        repo.insert(photobook_data={"tour_duration_hours": 2.0, "title": "Kurz"}, images=[])
        repo.insert(photobook_data={"tour_duration_hours": 8.0, "title": "Lang"}, images=[])

        records, total = repo.list(PhotobookFilters(duration_min=3.0, duration_max=10.0))
        assert total == 1
        assert records[0].title == "Lang"

    def test_list_pagination(self):
        session = _create_session()
        repo = PhotobookRepository(session)

        for i in range(5):
            repo.insert(photobook_data={"title": f"Buch {i}"}, images=[])

        records, total = repo.list(PhotobookFilters(limit=3, offset=0))
        assert total == 5
        assert len(records) == 3

        records2, _ = repo.list(PhotobookFilters(limit=3, offset=3))
        assert len(records2) == 2

    def test_delete(self):
        session = _create_session()
        repo = PhotobookRepository(session)

        pb_id = repo.insert(photobook_data={"title": "Zu löschen"}, images=[])
        assert repo.get_by_id(pb_id) is not None

        result = repo.delete(pb_id)
        assert result is True
        assert repo.get_by_id(pb_id) is None

    def test_delete_nonexistent(self):
        session = _create_session()
        repo = PhotobookRepository(session)

        result = repo.delete(999)
        assert result is False

    def test_get_by_id_nonexistent(self):
        session = _create_session()
        repo = PhotobookRepository(session)

        record = repo.get_by_id(999)
        assert record is None

    def test_delete_batch(self):
        session = _create_session()
        repo = PhotobookRepository(session)

        ids = []
        for i in range(3):
            ids.append(repo.insert(photobook_data={"title": f"Buch {i}"}, images=[]))

        result = repo.delete_batch(ids[:2])
        assert result == 2
        assert repo.get_by_id(ids[0]) is None
        assert repo.get_by_id(ids[1]) is None
        assert repo.get_by_id(ids[2]) is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_photobook_repository.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.db.photobook_repository'`

- [ ] **Step 3: Implement PhotobookRepository**

Create `app/db/photobook_repository.py`:

```python
# app/db/photobook_repository.py
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional, List

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.db.models import Photobook, PhotobookImage


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


class PhotobookRepository:
    """Repository für den Zugriff auf die photobooks-Tabelle."""

    def __init__(self, session: Session):
        self.session = session

    def insert(self, photobook_data: dict, images: list[dict]) -> int:
        """Fügt ein Fotobuch mit Bildern ein. Gibt die photobook_id zurück."""
        photobook = Photobook(**photobook_data)
        self.session.add(photobook)
        self.session.flush()

        for img in images:
            self.session.add(PhotobookImage(photobook_id=photobook.id, **img))

        self.session.commit()
        return photobook.id

    def list(self, filters: PhotobookFilters) -> tuple[list[Photobook], int]:
        """Gibt gefilterte und paginierte Fotobücher sowie die Gesamtanzahl zurück."""
        q = select(Photobook)

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

        count_q = select(func.count()).select_from(q.subquery())
        total = self.session.execute(count_q).scalar_one()

        q = q.order_by(Photobook.generation_timestamp.desc())
        q = q.offset(filters.offset).limit(filters.limit)
        records = self.session.execute(q).scalars().all()

        return records, total

    def get_by_id(self, photobook_id: int) -> Optional[Photobook]:
        """Holt ein einzelnes Fotobuch inkl. Bilder."""
        q = select(Photobook).where(Photobook.id == photobook_id)
        return self.session.execute(q).scalar_one_or_none()

    def delete(self, photobook_id: int) -> bool:
        """Löscht ein Fotobuch und seine Bilder (CASCADE). Gibt True zurück wenn gelöscht."""
        photobook = self.get_by_id(photobook_id)
        if photobook is None:
            return False
        self.session.delete(photobook)
        self.session.commit()
        return True

    def delete_batch(self, photobook_ids: List[int]) -> int:
        """Löscht mehrere Fotobücher und ihre Bilder (CASCADE). Gibt Anzahl gelöschter zurück."""
        if not photobook_ids:
            return 0
        count = (
            self.session.query(Photobook)
            .where(Photobook.id.in_(photobook_ids))
            .delete(synchronize_session="fetch")
        )
        self.session.commit()
        return count
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_photobook_repository.py -v`
Expected: All 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_photobook_repository.py app/db/photobook_repository.py
git commit -m "feat: add PhotobookRepository with tests"
```

---

### Task 4: Write persist_photobook service tests

**Files:**
- Create: `tests/test_persist_photobook_service.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_persist_photobook_service.py
from datetime import datetime, date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.models import Base
from app.db.photobook_repository import PhotobookRepository
from app.state import ImageData


class FakePoint:
    def __init__(self, time_val):
        self.time = time_val


class FakeGPXStats:
    def __init__(self):
        self.total_distance_m = 25000.0
        self.elevation_gain_m = 1200.0
        self.elevation_loss_m = 900.0
        self.points = [
            FakePoint(datetime(2026, 5, 1, 7, 0, 0)),
            FakePoint(datetime(2026, 5, 1, 16, 0, 0)),
        ]


class TestPersistPhotobookService:
    def test_persist_with_full_data(self, monkeypatch):
        """Integrationstest: Service persistiert vollständiges Fotobuch."""
        from app.services.persist_photobook import persist_photobook
        from app.db import connection as conn_module

        engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(engine)
        session = Session(engine)

        monkeypatch.setattr(conn_module, "_engine", engine)
        monkeypatch.setattr(conn_module, "_SessionLocal", None)
        monkeypatch.setattr(conn_module, "get_session", lambda: session)

        gpx_stats = FakeGPXStats()
        photobook_images = [
            ImageData(path="/tmp/00_map.png", timestamp="2026-05-01T10:00:00"),
            ImageData(path="/tmp/01_photo.jpg", timestamp="2026-05-01T12:00:00"),
            ImageData(path="/tmp/02_photo.jpg", timestamp="2026-05-01T14:00:00"),
        ]
        page_descriptions = [{"template_id": "cover_hero"}, {"template_id": "single_full"}]

        photobook_id = persist_photobook(
            gpx_stats=gpx_stats,
            photobook_images=photobook_images,
            photobook_pages=page_descriptions,
            photobook_html="<h1>Fotobuch</h1>",
            photobook_html_path="output/photobook_2026-05-01_08-00-00/test.html",
            photobook_pdf_path="output/photobook_2026-05-01_08-00-00/test.pdf",
            photobook_size="normal",
            gpx_file="/data/test.gpx",
            model="gemma4:26b-ctx128k",
            notes="Tolle Fototour",
        )

        assert photobook_id is not None

        repo = PhotobookRepository(session)
        record = repo.get_by_id(photobook_id)
        assert record is not None
        assert record.tour_date == date(2026, 5, 1)
        assert record.tour_duration_hours == pytest.approx(9.0, rel=0.01)
        assert record.tour_duration_source == "gpx"
        assert record.total_distance_km == 25.0
        assert record.elevation_gain_m == 1200.0
        assert record.elevation_loss_m == 900.0
        assert record.image_count == 3
        assert record.model_used == "gemma4:26b-ctx128k"
        assert record.notes == "Tolle Fototour"
        assert record.photobook_size == "normal"
        assert record.page_count == 2
        assert record.pdf_path == "output/photobook_2026-05-01_08-00-00/test.pdf"
        assert record.html_content == "<h1>Fotobuch</h1>"
        assert len(record.images) == 3

        session.close()

    def test_persist_without_gpx_uses_photos_for_duration(self, monkeypatch):
        """Fallback auf Foto-Timestamps wenn keine GPX-Daten."""
        from app.services.persist_photobook import persist_photobook
        from app.db import connection as conn_module

        engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(engine)
        session = Session(engine)

        monkeypatch.setattr(conn_module, "_engine", engine)
        monkeypatch.setattr(conn_module, "_SessionLocal", None)
        monkeypatch.setattr(conn_module, "get_session", lambda: session)

        class GPXWithoutTime:
            total_distance_m = None
            elevation_gain_m = None
            elevation_loss_m = None
            points = []

        photobook_images = [
            ImageData(path="img1.jpg", timestamp="2026-04-20T08:00:00"),
            ImageData(path="img2.jpg", timestamp="2026-04-20T14:00:00"),
        ]

        photobook_id = persist_photobook(
            gpx_stats=GPXWithoutTime(),
            photobook_images=photobook_images,
            photobook_pages=[{"template_id": "single_full"}],
            photobook_html="<h1>Test</h1>",
            photobook_html_path="output/test.html",
            photobook_pdf_path="output/test.pdf",
            photobook_size="short",
            gpx_file="",
            model="",
        )

        repo = PhotobookRepository(session)
        record = repo.get_by_id(photobook_id)
        assert record.tour_duration_source == "photos"
        assert record.tour_duration_hours == 6.0
        assert record.photobook_size == "short"

        session.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_persist_photobook_service.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.persist_photobook'`

- [ ] **Step 3: Implement persist_photobook service**

Create `app/services/persist_photobook.py`:

```python
# app/services/persist_photobook.py
"""Service zum Persistieren generierter Fotobücher in der Datenbank."""
import re
from datetime import datetime, date
from typing import Optional, List

from app.db.connection import get_session
from app.db.photobook_repository import PhotobookRepository


def _sanitize_html(html: str) -> str:
    """Entfernt potenziell gefährliche Inhalte aus LLM-generiertem HTML."""
    if not html:
        return html
    html = re.sub(r'<script[^>]*>.*?</script\s*>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<script[^>]*/>', '', html, flags=re.IGNORECASE)
    html = re.sub(r'<style[^>]*>.*?</style\s*>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'\s+on\w+\s*=\s*"[^"]*"', '', html, flags=re.IGNORECASE)
    html = re.sub(r"\s+on\w+\s*=\s*'[^']*'", '', html, flags=re.IGNORECASE)
    html = re.sub(r'\s+on\w+\s*=\s*\S+', '', html, flags=re.IGNORECASE)
    html = re.sub(r'(href|src)\s*=\s*"[^"]*javascript:[^"]*"', r'\1="#"', html, flags=re.IGNORECASE)
    html = re.sub(r"(href|src)\s*=\s*'[^']*javascript:[^']*'", r"\1='#'", html, flags=re.IGNORECASE)
    return html


def _compute_tour_date_and_duration(gpx_stats, photobook_images) -> tuple:
    """Berechnet tour_date und tour_duration aus GPX oder Foto-Timestamps."""
    if gpx_stats and hasattr(gpx_stats, "points") and gpx_stats.points:
        points = gpx_stats.points
        if len(points) >= 2 and points[0].time and points[-1].time:
            start = points[0].time
            end = points[-1].time
            duration_hours = (end - start).total_seconds() / 3600.0
            return start.date(), abs(duration_hours), "gpx"

    if photobook_images:
        timestamps = []
        for img in photobook_images:
            ts = img.timestamp if hasattr(img, "timestamp") else img.get("timestamp")
            if not ts:
                continue
            try:
                timestamps.append(datetime.fromisoformat(str(ts)))
            except (ValueError, TypeError):
                continue
        if len(timestamps) >= 2:
            start = min(timestamps)
            end = max(timestamps)
            duration_hours = (end - start).total_seconds() / 3600.0
            return start.date(), abs(duration_hours), "photos"

    return None, None, None


def persist_photobook(
    gpx_stats,
    photobook_images: List,
    photobook_pages: List,
    photobook_html: Optional[str],
    photobook_html_path: Optional[str],
    photobook_pdf_path: Optional[str],
    photobook_size: Optional[str],
    gpx_file: str,
    model: str,
    notes: Optional[str] = None,
) -> Optional[int]:
    """Persistiert ein generiertes Fotobuch in der Datenbank."""
    tour_date, tour_duration_hours, tour_duration_source = _compute_tour_date_and_duration(
        gpx_stats, photobook_images
    )

    distance_m = gpx_stats.total_distance_m if gpx_stats else None
    gain_m = gpx_stats.elevation_gain_m if gpx_stats else None
    loss_m = gpx_stats.elevation_loss_m if gpx_stats else None

    photobook_data = {
        "title": None,
        "tour_date": tour_date,
        "tour_duration_hours": round(tour_duration_hours, 2) if tour_duration_hours else None,
        "tour_duration_source": tour_duration_source,
        "generation_timestamp": datetime.now(),
        "gpx_file": gpx_file,
        "total_distance_km": round(distance_m / 1000.0, 2) if distance_m else None,
        "elevation_gain_m": round(gain_m, 0) if gain_m else None,
        "elevation_loss_m": round(loss_m, 0) if loss_m else None,
        "image_count": len(photobook_images),
        "html_content": _sanitize_html(photobook_html or ""),
        "html_path": photobook_html_path or "",
        "model_used": model,
        "notes": notes,
        "pdf_path": photobook_pdf_path,
        "page_count": len(photobook_pages),
        "photobook_size": photobook_size,
    }

    image_records = []
    for img in photobook_images:
        path = img.path if hasattr(img, "path") else img.get("path", "")
        image_records.append({
            "image_path": path,
            "is_map": path.endswith("00_map.png"),
            "is_elevation_profile": path.endswith("00_elevation_profile.png"),
        })

    try:
        session = get_session()
        try:
            repo = PhotobookRepository(session)
            photobook_id = repo.insert(photobook_data, image_records)
            return photobook_id
        finally:
            session.close()
    except Exception as e:
        print(f"❌ Fehler beim Persistieren des Fotobuchs: {e}")
        return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_persist_photobook_service.py -v`
Expected: All 2 tests PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_persist_photobook_service.py app/services/persist_photobook.py
git commit -m "feat: add persist_photobook service with tests"
```

---

### Task 5: Add persist_photobook LangGraph node + wire into graph

**Files:**
- Create: `app/nodes/persist_photobook.py`
- Modify: `app/graph.py`

- [ ] **Step 1: Create node**

Create `app/nodes/persist_photobook.py`:

```python
# app/nodes/persist_photobook.py
from app.state import AppState
from app.services.persist_photobook import persist_photobook


def persist_photobook_node(state: AppState) -> AppState:
    """Persistiert das generierte Fotobuch in der Datenbank."""
    print("💾 Persisting photobook to database...")

    photobook_id = persist_photobook(
        gpx_stats=state.gpx_stats,
        photobook_images=state.photobook_images,
        photobook_pages=state.photobook_pages,
        photobook_html=state.photobook_html,
        photobook_html_path=state.photobook_html_path,
        photobook_pdf_path=state.photobook_pdf_path,
        photobook_size=state.output_config.photobook.size,
        gpx_file=state.gpx_file,
        model=state.model,
        notes=state.notes,
    )

    if photobook_id:
        print(f"✅ Photobook persisted with ID: {photobook_id}")
        state.metadata["photobook_id"] = photobook_id
    else:
        print("⚠️ Photobook was not persisted (DB error).")
        state.metadata["photobook_id"] = None

    return state
```

- [ ] **Step 2: Integrate into graph.py**

In `app/graph.py`, add import at line 23 (after photobook imports):

```python
from app.nodes.persist_photobook import persist_photobook_node
```

Add `NODE_NAMES` entry at line 48 (after `generate_photobook_pdf`):

```python
    "persist_photobook": "Fotobuch speichern",
```

Add node wrapper (after line 142, `gpp` definition):

```python
    ppb_persist = _wrap_node(persist_photobook_node, "persist_photobook", event_emitter) if event_emitter else persist_photobook_node
```

Add node registration (after line 148):

```python
    builder.add_node("persist_photobook", ppb_persist)
```

Change the edge from `generate_photobook_pdf → END` to `generate_photobook_pdf → persist_photobook → END`:

Replace line 186:
```python
    builder.add_edge("generate_photobook_pdf", END)
```
with:
```python
    builder.add_edge("generate_photobook_pdf", "persist_photobook")
    builder.add_edge("persist_photobook", END)
```

- [ ] **Step 3: Verify graph compiles**

Run: `uv run python -c "from app.graph import build_graph; g = build_graph(); print('Graph OK:', g.name)"`
Expected: `Graph OK: LangGraph`

- [ ] **Step 4: Commit**

```bash
git add app/nodes/persist_photobook.py app/graph.py
git commit -m "feat: add persist_photobook node to pipeline graph"
```

---

### Task 6: Add photobook API endpoints and serializers

**Files:**
- Modify: `app/api/routes.py`

- [ ] **Step 1: Add imports**

Add after the line `from app.db.models import Article, ArticleImage` (line 18):

```python
from app.db.models import Photobook, PhotobookImage
from app.db.photobook_repository import PhotobookRepository, PhotobookFilters
```

- [ ] **Step 2: Add serialization helpers**

Add after `_article_to_detail` (after line 103):

```python
def _photobook_to_summary(p: Photobook) -> dict:
    return {
        "id": p.id,
        "title": p.title,
        "tour_date": p.tour_date.isoformat() if p.tour_date else None,
        "tour_duration_hours": p.tour_duration_hours,
        "tour_duration_source": p.tour_duration_source,
        "generation_timestamp": p.generation_timestamp.isoformat() if p.generation_timestamp else None,
        "total_distance_km": p.total_distance_km,
        "elevation_gain_m": p.elevation_gain_m,
        "elevation_loss_m": p.elevation_loss_m,
        "image_count": p.image_count,
        "model_used": p.model_used,
        "notes": p.notes,
        "photobook_size": p.photobook_size,
        "page_count": p.page_count,
    }


def _photobook_to_detail(p: Photobook) -> dict:
    return {
        **_photobook_to_summary(p),
        "html_content": _rewrite_photobook_html(p.html_content, p.id),
        "html_path": p.html_path,
        "pdf_path": p.pdf_path,
        "gpx_file": p.gpx_file,
        "images": [
            {
                "image_path": img.image_path,
                "is_map": img.is_map,
                "is_elevation_profile": img.is_elevation_profile,
            }
            for img in p.images
        ],
    }


def _rewrite_photobook_html(html_content: str | None, photobook_id: int) -> str | None:
    """Passt HTML-Inhalt für das Frontend an. Gleiche Logik wie _rewrite_html_content."""
    if not html_content:
        return html_content

    html_content = re.sub(
        r"<style[^>]*>.*?</style\s*>",
        "",
        html_content,
        flags=re.DOTALL | re.IGNORECASE,
    )

    body_match = re.search(
        r"<body[^>]*>(.*?)</body\s*>",
        html_content,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if body_match:
        html_content = body_match.group(1).strip()
    else:
        html_content = re.sub(r"<!DOCTYPE[^>]*>", "", html_content, flags=re.IGNORECASE)
        html_content = re.sub(r"<html[^>]*>", "", html_content, flags=re.IGNORECASE)
        html_content = re.sub(r"</html\s*>", "", html_content, flags=re.IGNORECASE)
        html_content = re.sub(
            r"<head[^>]*>.*?</head\s*>",
            "",
            html_content,
            flags=re.DOTALL | re.IGNORECASE,
        )

    html_content = html_content.replace(
        "./images/",
        f"/api/photobooks/{photobook_id}/images/",
    )

    return html_content
```

- [ ] **Step 3: Add photobook endpoints**

Add after the `# ── Photobook PDF Download ─────────────────────────────` section (before `# ── SSE Streaming ──────────────────────────────────────`):

```python
# ── Photobooks ────────────────────────────────────────

@router.get("/photobooks")
async def get_photobooks(
    tour_date_from: Optional[str] = None,
    tour_date_to: Optional[str] = None,
    duration_min: Optional[float] = None,
    duration_max: Optional[float] = None,
    generated_from: Optional[str] = None,
    generated_to: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
):
    """Liste aller persistierten Fotobücher mit optionalen Filtern."""
    filters = PhotobookFilters(limit=limit, offset=offset)

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
        repo = PhotobookRepository(session)
        records, total = repo.list(filters)
        return {
            "photobooks": [_photobook_to_summary(p) for p in records],
            "total": total,
        }
    finally:
        session.close()


@router.get("/photobooks/{photobook_id}")
async def get_photobook(photobook_id: int):
    """Einzelnes Fotobuch mit vollständigem Inhalt abrufen."""
    session = get_session()
    try:
        repo = PhotobookRepository(session)
        record = repo.get_by_id(photobook_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Photobook not found")
        return {"photobook": _photobook_to_detail(record)}
    finally:
        session.close()


@router.delete("/photobooks/{photobook_id}")
async def delete_photobook(photobook_id: int):
    """Fotobuch und zugehörige Dateien löschen."""
    session = get_session()
    try:
        repo = PhotobookRepository(session)
        record = repo.get_by_id(photobook_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Photobook not found")

        output_dir = os.path.dirname(record.html_path) if record.html_path else None
        repo.delete(photobook_id)

        if output_dir and os.path.exists(output_dir):
            try:
                shutil.rmtree(output_dir)
            except OSError as e:
                print(f"⚠️ Konnte Output-Verzeichnis nicht löschen: {e}")

        return {"deleted": photobook_id}
    finally:
        session.close()


@router.post("/photobooks/delete-batch")
async def delete_photobooks_batch(body: DeleteBatchRequest):
    """Mehrere Fotobücher und deren Dateien auf einmal löschen."""
    if not body.ids:
        raise HTTPException(status_code=400, detail="No photobook IDs provided")

    session = get_session()
    try:
        repo = PhotobookRepository(session)

        output_dirs: list[str] = []
        for pb_id in body.ids:
            record = repo.get_by_id(pb_id)
            if record and record.html_path:
                d = os.path.dirname(record.html_path)
                if d not in output_dirs:
                    output_dirs.append(d)

        deleted = repo.delete_batch(body.ids)

        for d in output_dirs:
            if os.path.exists(d):
                try:
                    shutil.rmtree(d)
                except OSError as e:
                    print(f"⚠️ Konnte Output-Verzeichnis nicht löschen: {e}")

        return {"deleted": deleted}
    finally:
        session.close()


@router.get("/photobooks/{photobook_id}/pdf")
async def get_photobook_pdf(photobook_id: int):
    """PDF eines persistierten Fotobuchs ausliefern."""
    session = get_session()
    try:
        repo = PhotobookRepository(session)
        record = repo.get_by_id(photobook_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Fotobuch nicht gefunden")
        if not record.pdf_path:
            raise HTTPException(status_code=400, detail="Fotobuch hat kein PDF")

        path = Path(record.pdf_path)
        if not path.exists():
            raise HTTPException(status_code=404, detail="PDF-Datei nicht gefunden")

        return FileResponse(
            path,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{path.name}"',
                "Cache-Control": "no-cache",
            },
        )
    finally:
        session.close()


@router.get("/photobooks/{photobook_id}/images/{filename}")
async def get_photobook_image(photobook_id: int, filename: str):
    """Bilddatei eines Fotobuchs ausliefern."""
    session = get_session()
    try:
        repo = PhotobookRepository(session)
        record = repo.get_by_id(photobook_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Photobook not found")

        for img in record.images:
            if os.path.basename(img.image_path) == filename:
                if os.path.isfile(img.image_path):
                    return FileResponse(img.image_path)
                break

        output_dir = None
        if record.html_path:
            output_dir = os.path.dirname(record.html_path)

        if output_dir:
            image_path = os.path.join(output_dir, "images", filename)
            if os.path.isfile(image_path):
                return FileResponse(image_path)

        raise HTTPException(status_code=404, detail="Image not found")
    finally:
        session.close()
```

- [ ] **Step 4: Update _run_pipeline_in_background to include photobook_id in result**

In the `_run_pipeline_in_background` function, change the section that extracts metadata (around lines 330-340) to also extract `photobook_id`:

Replace:
```python
        article_id = None
        pdf_available = False
        if hasattr(result, "metadata"):
            article_id = result.metadata.get("article_id")
        if blog_post and isinstance(blog_post, dict) and "pdf_bytes" in blog_post:
            pdf_available = True

        # Fotobuch: PDF verfügbar wenn Pfad gesetzt ist
        if photobook_pdf_path:
            pdf_available = True

        event_manager.complete_run(
            run_id, "success", output_path,
            article_id=article_id,
            pdf_available=pdf_available,
        )
```

with:
```python
        article_id = None
        photobook_id = None
        pdf_available = False
        if hasattr(result, "metadata"):
            article_id = result.metadata.get("article_id")
            photobook_id = result.metadata.get("photobook_id")
        if blog_post and isinstance(blog_post, dict) and "pdf_bytes" in blog_post:
            pdf_available = True

        # Fotobuch: PDF verfügbar wenn Pfad gesetzt ist
        if photobook_pdf_path:
            pdf_available = True

        event_manager.complete_run(
            run_id, "success", output_path,
            article_id=article_id,
            photobook_id=photobook_id,
            pdf_available=pdf_available,
        )
```

- [ ] **Step 5: Update event_manager.complete_run signature**

In `app/api/events.py`, change the `complete_run` method signature from:
```python
    def complete_run(self, run_id: str, status: str, output_dir: str = "",
                     article_id: int = None, pdf_available: bool = False):
```
to:
```python
    def complete_run(self, run_id: str, status: str, output_dir: str = "",
                     article_id: int = None, photobook_id: int = None,
                     pdf_available: bool = False):
```

Add after the `if article_id is not None:` block:
```python
        if photobook_id is not None:
            event["photobook_id"] = photobook_id
```

- [ ] **Step 6: Remove old transient photobook endpoint**

Delete the entire `# ── Photobook PDF Download ─────────────────────────────` section (the old `GET /api/photobook/{run_id}/pdf` endpoint, lines 549-573).

- [ ] **Step 7: Verify routes are registered**

Run: `uv run python -c "
from app.api.server import create_app
app = create_app()
for r in app.routes:
    if hasattr(r, 'path') and 'photobook' in r.path:
        print(r.methods, r.path)
"`
Expected: Shows all 6 new photobook routes

- [ ] **Step 8: Commit**

```bash
git add app/api/routes.py app/api/events.py
git commit -m "feat: add photobook CRUD API endpoints, remove transient endpoint"
```

---

### Task 7: Add photobook API tests

**Files:**
- Modify: `tests/test_api_endpoints.py`

- [ ] **Step 1: Replace old photobook test class with new persistence-based tests**

Replace the entire `TestPhotobookPdf` class (lines 505-544) with:

```python
class TestPhotobooksList:
    def test_list_empty_returns_empty_array(self, monkeypatch):
        import os
        import tempfile
        from app.db import connection as conn_module
        from app.db.models import Base
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker as sm

        tmp = tempfile.mktemp(suffix=".db")
        try:
            engine = create_engine(f"sqlite:///{tmp}", echo=False)
            Base.metadata.create_all(engine)

            factory = sm(bind=engine)
            monkeypatch.setattr(conn_module, "_engine", engine)
            monkeypatch.setattr(conn_module, "_SessionLocal", factory)
            monkeypatch.setattr(conn_module, "get_session", factory)

            from app.api.server import create_app
            from fastapi.testclient import TestClient
            app = create_app()
            import app.api.routes as routes_mod
            monkeypatch.setattr(routes_mod, "get_session", factory)
            client = TestClient(app)

            response = client.get("/api/photobooks")
            assert response.status_code == 200
            data = response.json()
            assert data["photobooks"] == []
            assert data["total"] == 0
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def test_list_with_filters(self, monkeypatch):
        import os
        import tempfile
        from datetime import date as date_type, datetime as datetime_type
        from app.db import connection as conn_module
        from app.db.models import Base
        from app.db.photobook_repository import PhotobookRepository
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session, sessionmaker as sm

        tmp = tempfile.mktemp(suffix=".db")
        try:
            engine = create_engine(f"sqlite:///{tmp}", echo=False)
            Base.metadata.create_all(engine)
            session = Session(engine)

            factory = sm(bind=engine)
            monkeypatch.setattr(conn_module, "_engine", engine)
            monkeypatch.setattr(conn_module, "_SessionLocal", factory)
            monkeypatch.setattr(conn_module, "get_session", factory)

            from app.api.server import create_app
            from fastapi.testclient import TestClient
            app = create_app()
            import app.api.routes as routes_mod
            monkeypatch.setattr(routes_mod, "get_session", factory)
            client = TestClient(app)

            repo = PhotobookRepository(session)
            repo.insert(
                photobook_data={
                    "title": "Test Fotobuch",
                    "tour_date": date_type(2026, 4, 15),
                    "tour_duration_hours": 5.0,
                    "generation_timestamp": datetime_type(2026, 4, 30, 12, 0, 0),
                    "html_content": "<h1>Test</h1>",
                    "html_path": "output/test/html.html",
                    "photobook_size": "normal",
                    "page_count": 10,
                },
                images=[],
            )
            session.commit()

            response = client.get("/api/photobooks?tour_date_from=2026-04-01&tour_date_to=2026-05-01")
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 1
            assert data["photobooks"][0]["photobook_size"] == "normal"
            assert data["photobooks"][0]["page_count"] == 10
            assert "html_content" not in data["photobooks"][0]

            session.close()
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)


class TestPhotobookDetail:
    def test_get_by_valid_id(self, monkeypatch):
        import os
        import tempfile
        from app.db import connection as conn_module
        from app.db.models import Base
        from app.db.photobook_repository import PhotobookRepository
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session, sessionmaker as sm

        tmp = tempfile.mktemp(suffix=".db")
        try:
            engine = create_engine(f"sqlite:///{tmp}", echo=False)
            Base.metadata.create_all(engine)
            session = Session(engine)

            factory = sm(bind=engine)
            monkeypatch.setattr(conn_module, "_engine", engine)
            monkeypatch.setattr(conn_module, "_SessionLocal", factory)
            monkeypatch.setattr(conn_module, "get_session", factory)

            from app.api.server import create_app
            from fastapi.testclient import TestClient
            app = create_app()
            import app.api.routes as routes_mod
            monkeypatch.setattr(routes_mod, "get_session", factory)
            client = TestClient(app)

            repo = PhotobookRepository(session)
            pb_id = repo.insert(
                photobook_data={
                    "title": "Detail Test",
                    "html_content": "<h1>Detail</h1><p>Content</p>",
                    "html_path": "output/test/html.html",
                    "photobook_size": "short",
                },
                images=[
                    {"image_path": "./images/01.jpg", "is_map": False, "is_elevation_profile": False},
                ],
            )
            session.commit()

            response = client.get(f"/api/photobooks/{pb_id}")
            assert response.status_code == 200
            data = response.json()
            assert data["photobook"]["id"] == pb_id
            assert data["photobook"]["photobook_size"] == "short"
            assert len(data["photobook"]["images"]) == 1

            session.close()
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def test_get_by_invalid_id_returns_404(self, client):
        response = client.get("/api/photobooks/99999")
        assert response.status_code == 404


class TestPhotobookDelete:
    def test_delete_existing(self, monkeypatch):
        import os
        import tempfile
        from app.db import connection as conn_module
        from app.db.models import Base
        from app.db.photobook_repository import PhotobookRepository
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session, sessionmaker as sm

        tmp = tempfile.mktemp(suffix=".db")
        try:
            engine = create_engine(f"sqlite:///{tmp}", echo=False)
            Base.metadata.create_all(engine)
            session = Session(engine)

            factory = sm(bind=engine)
            monkeypatch.setattr(conn_module, "_engine", engine)
            monkeypatch.setattr(conn_module, "_SessionLocal", factory)
            monkeypatch.setattr(conn_module, "get_session", factory)

            from app.api.server import create_app
            from fastapi.testclient import TestClient
            app = create_app()
            import app.api.routes as routes_mod
            monkeypatch.setattr(routes_mod, "get_session", factory)
            client = TestClient(app)

            repo = PhotobookRepository(session)
            pb_id = repo.insert(
                photobook_data={"html_path": "output/test/html.html"},
                images=[],
            )
            session.commit()

            response = client.delete(f"/api/photobooks/{pb_id}")
            assert response.status_code == 200
            assert response.json()["deleted"] == pb_id

            response2 = client.get(f"/api/photobooks/{pb_id}")
            assert response2.status_code == 404

            session.close()
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def test_delete_nonexistent_returns_404(self, client):
        response = client.delete("/api/photobooks/99999")
        assert response.status_code == 404


class TestPhotobookPdf:
    def test_pdf_endpoint_returns_404_for_missing(self, client):
        response = client.get("/api/photobooks/99999/pdf")
        assert response.status_code == 404

    def test_pdf_endpoint_with_valid_photobook(self, monkeypatch, tmp_path):
        import os
        import tempfile
        from app.db import connection as conn_module
        from app.db.models import Base
        from app.db.photobook_repository import PhotobookRepository
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session, sessionmaker as sm

        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 mock")

        tmp = tempfile.mktemp(suffix=".db")
        try:
            engine = create_engine(f"sqlite:///{tmp}", echo=False)
            Base.metadata.create_all(engine)
            session = Session(engine)

            factory = sm(bind=engine)
            monkeypatch.setattr(conn_module, "_engine", engine)
            monkeypatch.setattr(conn_module, "_SessionLocal", factory)
            monkeypatch.setattr(conn_module, "get_session", factory)

            from app.api.server import create_app
            from fastapi.testclient import TestClient
            app = create_app()
            import app.api.routes as routes_mod
            monkeypatch.setattr(routes_mod, "get_session", factory)
            client = TestClient(app)

            repo = PhotobookRepository(session)
            pb_id = repo.insert(
                photobook_data={
                    "html_path": "output/test/html.html",
                    "pdf_path": str(pdf_file),
                },
                images=[],
            )
            session.commit()

            response = client.get(f"/api/photobooks/{pb_id}/pdf")
            assert response.status_code == 200
            assert response.headers["content-type"] == "application/pdf"
            assert response.content == b"%PDF-1.4 mock"

            session.close()
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def test_pdf_endpoint_with_no_pdf_returns_400(self, monkeypatch):
        import os
        import tempfile
        from app.db import connection as conn_module
        from app.db.models import Base
        from app.db.photobook_repository import PhotobookRepository
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session, sessionmaker as sm

        tmp = tempfile.mktemp(suffix=".db")
        try:
            engine = create_engine(f"sqlite:///{tmp}", echo=False)
            Base.metadata.create_all(engine)
            session = Session(engine)

            factory = sm(bind=engine)
            monkeypatch.setattr(conn_module, "_engine", engine)
            monkeypatch.setattr(conn_module, "_SessionLocal", factory)
            monkeypatch.setattr(conn_module, "get_session", factory)

            from app.api.server import create_app
            from fastapi.testclient import TestClient
            app = create_app()
            import app.api.routes as routes_mod
            monkeypatch.setattr(routes_mod, "get_session", factory)
            client = TestClient(app)

            repo = PhotobookRepository(session)
            pb_id = repo.insert(photobook_data={"html_path": "output/test/html.html"}, images=[])
            session.commit()

            response = client.get(f"/api/photobooks/{pb_id}/pdf")
            assert response.status_code == 400

            session.close()
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
```

- [ ] **Step 2: Run tests**

Run: `uv run pytest tests/test_api_endpoints.py -v`
Expected: All tests pass (including new photobook tests)

- [ ] **Step 3: Commit**

```bash
git add tests/test_api_endpoints.py
git commit -m "test: add photobook API endpoint tests, replace transient endpoint tests"
```

---

### Task 8: Add frontend routing for photobooks

**Files:**
- Modify: `frontend/src/lib/stores/router.ts`

- [ ] **Step 1: Extend Route type and parsing**

Replace the `Route` type (line 3-6):
```typescript
export type Route =
  | { page: "pipeline" }
  | { page: "articles" }
  | { page: "article"; id: number };
```

with:
```typescript
export type Route =
  | { page: "pipeline" }
  | { page: "articles" }
  | { page: "article"; id: number }
  | { page: "photobooks" }
  | { page: "photobook"; id: number };
```

In `parseHash`, add photobook route parsing before the final fallback (before line 24 `return { page: "pipeline" };`):

```typescript
  const photobooksMatch = path.match(/^photobooks\/(\d+)$/);
  if (photobooksMatch) {
    return { page: "photobook", id: parseInt(photobooksMatch[1], 10) };
  }

  if (path === "photobooks") {
    return { page: "photobooks" };
  }
```

In `navigateTo`, add cases for photobook routes:

```typescript
    case "photobooks":
      hash = "#/photobooks";
      break;
    case "photobook":
      hash = `#/photobooks/${route.id}`;
      break;
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/stores/router.ts
git commit -m "feat: add photobook routes to frontend router"
```

---

### Task 9: Add PhotobookList Svelte component

**Files:**
- Create: `frontend/src/lib/PhotobookList.svelte`

- [ ] **Step 1: Create component**

Create `frontend/src/lib/PhotobookList.svelte`:

```svelte
<svelte:options runes />

<script lang="ts">
  import { navigateTo } from "./stores/router";

  interface PhotobookSummary {
    id: number;
    title: string | null;
    tour_date: string | null;
    tour_duration_hours: number | null;
    total_distance_km: number | null;
    elevation_gain_m: number | null;
    image_count: number | null;
    photobook_size: string | null;
    page_count: number | null;
    generation_timestamp: string | null;
  }

  let photobooks: PhotobookSummary[] = $state([]);
  let total: number = $state(0);
  let loading: boolean = $state(true);
  let error: string | null = $state(null);

  let tourDateFrom: string = $state("");
  let tourDateTo: string = $state("");
  let durationMin: string = $state("");
  let durationMax: string = $state("");

  let selectedIds: Set<number> = $state(new Set());
  let dialogOpen: boolean = $state(false);
  let dialogMode: "single" | "batch" = $state("single");
  let dialogItemId: number | null = $state(null);
  let deleting: boolean = $state(false);

  function toggleSelect(id: number) {
    const next = new Set(selectedIds);
    if (next.has(id)) {
      next.delete(id);
    } else {
      next.add(id);
    }
    selectedIds = next;
  }

  function toggleSelectAll() {
    if (selectedIds.size === photobooks.length) {
      selectedIds = new Set();
    } else {
      selectedIds = new Set(photobooks.map(a => a.id));
    }
  }

  async function fetchPhotobooks() {
    loading = true;
    error = null;

    try {
      const params = new URLSearchParams();
      if (tourDateFrom) params.set("tour_date_from", tourDateFrom);
      if (tourDateTo) params.set("tour_date_to", tourDateTo);
      if (durationMin) params.set("duration_min", durationMin);
      if (durationMax) params.set("duration_max", durationMax);
      params.set("limit", "50");

      const res = await fetch(`/api/photobooks?${params.toString()}`);
      if (!res.ok) throw new Error(`API error: ${res.status}`);
      const data = await res.json();
      photobooks = data.photobooks;
      total = data.total;
      selectedIds = new Set();
    } catch (e: any) {
      error = e.message;
    } finally {
      loading = false;
    }
  }

  function formatDate(iso: string | null): string {
    if (!iso) return "\u2014";
    return new Date(iso).toLocaleDateString("de-DE");
  }

  function formatDuration(hours: number | null): string {
    if (hours === null || hours === undefined) return "\u2014";
    const h = Math.floor(hours);
    const m = Math.round((hours - h) * 60);
    return `${h}h ${m}m`;
  }

  function formatSize(size: string | null): string {
    if (!size) return "\u2014";
    const map: Record<string, string> = { short: "Klein", normal: "Normal", detailed: "Gross" };
    return map[size] || size;
  }

  function handleView(id: number) {
    navigateTo({ page: "photobook", id });
  }

  function openSingleDelete(id: number) {
    dialogMode = "single";
    dialogItemId = id;
    dialogOpen = true;
  }

  function openBatchDelete() {
    if (selectedIds.size === 0) return;
    dialogMode = "batch";
    dialogItemId = null;
    dialogOpen = true;
  }

  function closeDialog() {
    dialogOpen = false;
    dialogItemId = null;
  }

  async function confirmDelete() {
    deleting = true;
    try {
      if (dialogMode === "single" && dialogItemId !== null) {
        const res = await fetch(`/api/photobooks/${dialogItemId}`, { method: "DELETE" });
        if (!res.ok) throw new Error(`Delete failed: ${res.status}`);
      } else {
        const res = await fetch("/api/photobooks/delete-batch", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ ids: [...selectedIds] }),
        });
        if (!res.ok) throw new Error(`Batch delete failed: ${res.status}`);
      }
      closeDialog();
      await fetchPhotobooks();
    } catch (e: any) {
      error = e.message;
    } finally {
      deleting = false;
    }
  }

  $effect(() => {
    fetchPhotobooks();
  });
</script>

<div class="photobook-list">
  <div class="header">
    <h2>Gespeicherte Fotobücher ({total})</h2>
    <button
      class="batch-delete-btn"
      disabled={selectedIds.size === 0}
      onclick={openBatchDelete}
    >
      Auswahl löschen ({selectedIds.size})
    </button>
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
    <button class="filter-btn" onclick={fetchPhotobooks}>Filtern</button>
  </div>

  {#if loading}
    <p class="status">Lade Fotobücher...</p>
  {:else if error}
    <p class="status error">Fehler: {error}</p>
  {:else if photobooks.length === 0}
    <p class="status">Keine Fotobücher gefunden.</p>
  {:else}
    <div class="table-container">
      <table>
        <thead>
          <tr>
            <th class="th-check">
              <input
                type="checkbox"
                checked={selectedIds.size === photobooks.length && photobooks.length > 0}
                onchange={toggleSelectAll}
              />
            </th>
            <th>Titel</th>
            <th>Tour-Datum</th>
            <th>Dauer</th>
            <th>Distanz</th>
            <th>Höhenmeter</th>
            <th>Bilder</th>
            <th>Grösse</th>
            <th></th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {#each photobooks as p}
            <tr>
              <td class="td-check">
                <input
                  type="checkbox"
                  checked={selectedIds.has(p.id)}
                  onchange={() => toggleSelect(p.id)}
                />
              </td>
              <td>{p.title || "Ohne Titel"}</td>
              <td>{formatDate(p.tour_date)}</td>
              <td>{formatDuration(p.tour_duration_hours)}</td>
              <td>{p.total_distance_km ? `${p.total_distance_km} km` : "\u2014"}</td>
              <td>{p.elevation_gain_m ? `${p.elevation_gain_m} m` : "\u2014"}</td>
              <td>{p.image_count ?? "\u2014"}</td>
              <td>{formatSize(p.photobook_size)}</td>
              <td>
                <button class="view-btn" onclick={() => handleView(p.id)}>Ansehen</button>
              </td>
              <td>
                <button class="delete-btn" onclick={() => openSingleDelete(p.id)}>Löschen</button>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>

{#if dialogOpen}
  <div class="dialog-overlay" onclick={closeDialog}>
    <div class="dialog" onclick={(e: MouseEvent) => e.stopPropagation()}>
      <p>
        {dialogMode === "single"
          ? "Dieses Fotobuch wirklich löschen? Dies entfernt auch die Dateien."
          : `${selectedIds.size} Fotobücher wirklich löschen? Dies entfernt auch die Dateien.`}
      </p>
      <div class="dialog-actions">
        <button class="cancel-btn" onclick={closeDialog} disabled={deleting}>Abbrechen</button>
        <button class="confirm-btn" onclick={confirmDelete} disabled={deleting}>
          {deleting ? "Lösche..." : "Löschen"}
        </button>
      </div>
    </div>
  </div>
{/if}

<style>
  .photobook-list {
    padding: 1rem;
    height: 100%;
    overflow-y: auto;
  }
  .header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1rem;
  }
  .batch-delete-btn {
    padding: 0.4rem 0.75rem;
    font-size: 0.8rem;
    background: var(--error);
    color: white;
    white-space: nowrap;
  }
  .batch-delete-btn:disabled {
    opacity: 0.35;
    cursor: not-allowed;
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
  .th-check {
    width: 2rem;
  }
  td {
    padding: 0.5rem;
    border-bottom: 1px solid var(--border);
    white-space: nowrap;
  }
  .td-check {
    width: 2rem;
  }
  .td-check input {
    cursor: pointer;
  }
  tr:hover {
    background: var(--panel-2);
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
  .delete-btn {
    padding: 0.3rem 0.6rem;
    background: var(--error);
    color: white;
    font-size: 0.75rem;
  }
  .delete-btn:hover {
    opacity: 0.85;
  }
  .dialog-overlay {
    position: fixed;
    inset: 0;
    background: var(--overlay-bg);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 100;
  }
  .dialog {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 1.5rem;
    max-width: 400px;
    width: 90%;
  }
  .dialog p {
    margin: 0 0 1.25rem 0;
    font-size: 0.9rem;
  }
  .dialog-actions {
    display: flex;
    gap: 0.75rem;
    justify-content: flex-end;
  }
  .cancel-btn {
    padding: 0.4rem 0.75rem;
    background: var(--surface-alt);
    color: var(--text);
    font-size: 0.8rem;
  }
  .cancel-btn:hover {
    background: var(--accent);
  }
  .confirm-btn {
    padding: 0.4rem 0.75rem;
    background: var(--error);
    color: white;
    font-size: 0.8rem;
  }
  .confirm-btn:disabled, .cancel-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
</style>
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/PhotobookList.svelte
git commit -m "feat: add PhotobookList frontend component"
```

---

### Task 10: Add PhotobookDetail Svelte component

**Files:**
- Create: `frontend/src/lib/PhotobookDetail.svelte`

- [ ] **Step 1: Create component**

Create `frontend/src/lib/PhotobookDetail.svelte`:

```svelte
<svelte:options runes />

<script lang="ts">
  import { navigateTo } from "./stores/router";

  let { id }: { id: number } = $props();

  interface PhotobookFull {
    id: number;
    title: string | null;
    tour_date: string | null;
    tour_duration_hours: number | null;
    generation_timestamp: string | null;
    total_distance_km: number | null;
    elevation_gain_m: number | null;
    elevation_loss_m: number | null;
    html_content: string | null;
    html_path: string | null;
    pdf_path: string | null;
    gpx_file: string | null;
    model_used: string | null;
    notes: string | null;
    photobook_size: string | null;
    page_count: number | null;
    images: { image_path: string; is_map: boolean; is_elevation_profile: boolean }[];
  }

  let photobook: PhotobookFull | null = $state(null);
  let loading: boolean = $state(true);
  let error: string | null = $state(null);
  let deleting: boolean = $state(false);

  async function fetchPhotobook() {
    loading = true;
    error = null;
    try {
      const res = await fetch(`/api/photobooks/${id}`);
      if (!res.ok) {
        if (res.status === 404) throw new Error("Fotobuch nicht gefunden.");
        throw new Error(`API error: ${res.status}`);
      }
      const data = await res.json();
      photobook = data.photobook;
    } catch (e: any) {
      error = e.message;
    } finally {
      loading = false;
    }
  }

  async function handleDelete() {
    if (!confirm("Fotobuch wirklich löschen? Dies entfernt auch die Dateien.")) return;
    deleting = true;
    try {
      const res = await fetch(`/api/photobooks/${id}`, { method: "DELETE" });
      if (!res.ok) throw new Error(`Delete failed: ${res.status}`);
      navigateTo({ page: "photobooks" });
    } catch (e: any) {
      error = e.message;
      deleting = false;
    }
  }

  function handlePdfExport() {
    window.open(`/api/photobooks/${id}/pdf`, "_blank");
  }

  function formatDate(iso: string | null): string {
    if (!iso) return "\u2014";
    return new Date(iso).toLocaleDateString("de-DE");
  }

  function formatDuration(hours: number | null): string {
    if (hours === null || hours === undefined) return "\u2014";
    const h = Math.floor(hours);
    const m = Math.round((hours - h) * 60);
    return `${h}h ${m}m`;
  }

  function formatSize(size: string | null): string {
    if (!size) return "\u2014";
    const map: Record<string, string> = { short: "Klein", normal: "Normal", detailed: "Gross" };
    return map[size] || size;
  }

  $effect(() => {
    fetchPhotobook();
  });
</script>

<div class="photobook-detail">
  <div class="toolbar">
    <button class="back-btn" onclick={() => navigateTo({ page: "photobooks" })}>
      \u2190 Zurück zur Liste
    </button>
    {#if photobook}
      <div class="toolbar-right">
        <button class="pdf-btn" onclick={handlePdfExport}>Als PDF exportieren</button>
        <button class="delete-btn" onclick={handleDelete} disabled={deleting}>
          {deleting ? "Lösche..." : "\uD83D\uDDD1 Löschen"}
        </button>
      </div>
    {/if}
  </div>

  {#if loading}
    <p class="status">Lade Fotobuch...</p>
  {:else if error}
    <p class="status error">{error}</p>
  {:else if photobook}
    <h1 class="title">{photobook.title || "Fotobuch"}</h1>

    <div class="meta">
      {#if photobook.tour_date}
        <span>\uD83D\uDCC5 {formatDate(photobook.tour_date)}</span>
      {/if}
      {#if photobook.tour_duration_hours}
        <span>\u23F1 {formatDuration(photobook.tour_duration_hours)}</span>
      {/if}
      {#if photobook.total_distance_km}
        <span>\uD83D\uDCCF {photobook.total_distance_km} km</span>
      {/if}
      {#if photobook.elevation_gain_m}
        <span>\u26F0 {photobook.elevation_gain_m} m \u2191</span>
      {/if}
      {#if photobook.model_used}
        <span>\uD83E\uDD16 {photobook.model_used}</span>
      {/if}
      {#if photobook.photobook_size}
        <span>\uD83D\uDCD6 {formatSize(photobook.photobook_size)} ({photobook.page_count ?? "?"} Seiten)</span>
      {/if}
    </div>

    {#if photobook.notes}
      <details class="notes-section">
        <summary>Notizen</summary>
        <pre class="notes">{photobook.notes}</pre>
      </details>
    {/if}

    {#if photobook.html_content}
      <div class="content">
        {@html photobook.html_content}
      </div>
    {/if}
  {/if}
</div>

<style>
  .photobook-detail {
    padding: 1rem;
    height: 100%;
    overflow-y: auto;
    max-width: 1400px;
  }
  .toolbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1rem;
  }
  .toolbar-right {
    display: flex;
    gap: 0.5rem;
  }
  .back-btn, .delete-btn, .pdf-btn {
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
  .pdf-btn {
    background: var(--success);
    color: white;
  }
  .pdf-btn:hover {
    filter: brightness(0.9);
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
    line-height: 1.8;
    font-size: 1.05rem;
  }
  .content :global(h1) {
    font-size: 2rem;
    font-weight: 700;
    margin: 2rem 0 1rem;
    padding-bottom: 0.5rem;
    border-bottom: 2px solid var(--border);
  }
  .content :global(h2) {
    font-size: 1.4rem;
    font-weight: 600;
    margin: 1.8rem 0 0.8rem;
  }
  .content :global(h3) {
    font-size: 1.15rem;
    font-weight: 600;
    margin: 1.5rem 0 0.6rem;
  }
  .content :global(p) {
    margin: 0 0 1.2rem;
  }
  .content :global(img) {
    max-width: 100%;
    height: auto;
    display: block;
    border-radius: 4px;
  }
  .content :global(figure) {
    margin: 2rem auto;
    text-align: center;
  }
  .content :global(figure img) {
    margin: 0 auto;
  }
  .content :global(figcaption) {
    margin-top: 0.6rem;
    font-size: 0.9rem;
    color: var(--text-muted);
    font-style: italic;
    line-height: 1.5;
    max-width: 600px;
    margin-left: auto;
    margin-right: auto;
  }
  .content :global(blockquote) {
    margin: 1.5rem 0;
    padding: 0.8rem 1.5rem;
    border-left: 4px solid var(--accent);
    background: var(--surface);
    font-style: italic;
    color: var(--text-secondary);
  }
  .content :global(ul),
  .content :global(ol) {
    margin: 0 0 1.2rem 1.5rem;
    padding: 0;
  }
  .content :global(li) {
    margin-bottom: 0.4rem;
  }
  .content :global(a) {
    color: var(--accent);
    text-decoration: underline;
  }
  .content :global(hr) {
    border: none;
    border-top: 1px solid var(--border);
    margin: 2rem 0;
  }
  .content :global(table) {
    width: 100%;
    border-collapse: collapse;
    margin: 1.5rem 0;
    font-size: 0.9rem;
  }
  .content :global(th),
  .content :global(td) {
    padding: 0.5rem 0.8rem;
    border-bottom: 1px solid var(--border);
    text-align: left;
  }
  .content :global(th) {
    font-weight: 600;
    background: var(--surface);
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

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/PhotobookDetail.svelte
git commit -m "feat: add PhotobookDetail frontend component"
```

---

### Task 11: Update App.svelte with sub-tabs

**Files:**
- Modify: `frontend/src/App.svelte`

- [ ] **Step 1: Add imports, sub-tab state, and rendering logic**

Add imports (after line 15):
```svelte
  import PhotobookList from "./lib/PhotobookList.svelte";
  import PhotobookDetail from "./lib/PhotobookDetail.svelte";
```

Change `rightTab` derived and `switchRightTab` function (lines 18-26) to:

```svelte
  let rightTab = $derived(rt.page === "pipeline" ? "pipeline" : "datenbank");
  let dbSubTab: "articles" | "photobooks" = $state("articles");

  function switchRightTab(tab: "pipeline" | "datenbank") {
    if (tab === "pipeline") {
      navigateTo({ page: "pipeline" });
    } else {
      if (dbSubTab === "articles") {
        navigateTo({ page: "articles" });
      } else {
        navigateTo({ page: "photobooks" });
      }
    }
  }

  function switchDbSubTab(sub: "articles" | "photobooks") {
    dbSubTab = sub;
    if (sub === "articles") {
      navigateTo({ page: "articles" });
    } else {
      navigateTo({ page: "photobooks" });
    }
  }
```

Add sub-tab bar after the main `.right-tabs` nav (after line 91, before the `</nav>`):

```svelte
    {#if rightTab === "datenbank"}
      <div class="sub-tabs">
        <button
          class="sub-tab"
          class:active={dbSubTab === "articles"}
          onclick={() => switchDbSubTab("articles")}
        >
          Blogartikel
        </button>
        <button
          class="sub-tab"
          class:active={dbSubTab === "photobooks"}
          onclick={() => switchDbSubTab("photobooks")}
        >
          Fotobücher
        </button>
      </div>
    {/if}
```

Change the content rendering (lines 93-101) from:

```svelte
    <div class="right-content">
      {#if rightTab === "pipeline"}
        <OutputWindow />
      {:else if rt.page === "article"}
        <ArticleDetail id={rt.id} />
      {:else}
        <ArticleList />
      {/if}
    </div>
```

to:

```svelte
    <div class="right-content">
      {#if rightTab === "pipeline"}
        <OutputWindow />
      {:else if rt.page === "article"}
        <ArticleDetail id={rt.id} />
      {:else if rt.page === "photobook"}
        <PhotobookDetail id={rt.id} />
      {:else if dbSubTab === "photobooks"}
        <PhotobookList />
      {:else}
        <ArticleList />
      {/if}
    </div>
```

Add CSS for `.sub-tabs` and `.sub-tab` (add inside `<style>` block, after `.right-tab:hover:not(.active)`):

```css
  .sub-tabs {
    display: flex;
    gap: 0.25rem;
    margin-bottom: 0.75rem;
    flex-shrink: 0;
  }
  .sub-tab {
    padding: 0.35rem 0.75rem;
    background: var(--panel);
    color: var(--text-secondary);
    font-size: 0.75rem;
    font-weight: 500;
    border: 1px solid var(--border);
    border-radius: var(--radius);
    cursor: pointer;
  }
  .sub-tab.active {
    background: var(--accent);
    color: white;
    border-color: var(--accent);
  }
  .sub-tab:hover:not(.active) {
    background: var(--panel-2);
    color: var(--text-primary);
  }
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/App.svelte
git commit -m "feat: add sub-tabs for Blogartikel/Fotobücher under Datenbank"
```

---

## Verification

After all tasks are complete, run the full test suite:

```bash
uv run pytest tests/ -v
```

Expected: All tests pass.

Run type checking:
```bash
cd frontend && npx tsc --noEmit
```

Expected: No TypeScript errors.

