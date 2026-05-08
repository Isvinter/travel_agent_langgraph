# Blog Draft Review & Revision — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add optional draft review + revision workflow to blog generation: user reviews HTML draft, marks paragraphs/images for revision, sends instructions to LLM, iterates until satisfied, then publishes.

**Architecture:** Pipeline stops after `design_blogpost` when `review_enabled=true`, saves draft to DB. New REST endpoints `/api/articles/{id}/revise` and `/api/articles/{id}/publish` handle the interactive revision loop outside the LangGraph graph.

**Tech Stack:** Python 3.12, LangGraph, FastAPI, SQLAlchemy/SQLite, Svelte 5 (runes mode), TypeScript

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `app/state.py` | Modify | Add `review_enabled` to `OutputConfig` |
| `app/db/models.py` | Modify | Add `status`, `revision_round` to `Article` |
| `app/db/repository.py` | Modify | Add `status` filter to `ArticleFilters`, add `update()` method |
| `app/services/persist_article.py` | Modify | Accept optional `status` param |
| `app/services/revise_blogpost.py` | **Create** | LLM revision prompt + Ollama call |
| `app/nodes/save_draft.py` | **Create** | Thin node: persist as draft |
| `app/graph.py` | Modify | Conditional edge after `design_blogpost`, add `save_draft` node |
| `app/api/routes.py` | Modify | Add `review_enabled` to request, `/revise` + `/publish` endpoints, draft aware pipeline background |
| `app/api/events.py` | Modify | Add `draft_id` to `complete_run()` |
| `frontend/src/lib/stores/pipeline.ts` | Modify | Add `reviewEnabled`, `currentDraftId` stores; extend `RunResult` |
| `frontend/src/lib/stores/router.ts` | Modify | Add `draft` route type + hash parsing |
| `frontend/src/lib/ReviewCheckbox.svelte` | **Create** | Checkbox binding to `reviewEnabled` |
| `frontend/src/lib/DraftReview.svelte` | **Create** | Full draft review + revision UI |
| `frontend/src/lib/SettingsTabs.svelte` | Modify | Show `ReviewCheckbox` in blog mode |
| `frontend/src/lib/RunButton.svelte` | Modify | Send `review_enabled` in body |
| `frontend/src/App.svelte` | Modify | Mount `DraftReview` for `draft` route, navigate on draft_id |
| `frontend/src/lib/ArticleList.svelte` | Modify | Show "Entwurf" badge for drafts |
| `tests/test_revise_api.py` | **Create** | Backend tests for revise/publish |
| `tests/test_draft_persistence.py` | **Create** | Backend tests for save_draft node |

---

### Task 1: Add `review_enabled` to `OutputConfig`

**Files:**
- Modify: `app/state.py:64-75`

- [ ] **Step 1: Add field**

In `app/state.py`, add to the `OutputConfig` class after `pdf_export`:

```python
review_enabled: bool = False
```

The class should now look like:

```python
class OutputConfig(BaseModel):
    """Konfiguration für die Blog-Ausgabe — vom Benutzer vor Pipeline-Start gesetzt."""
    wildcard_max: int = Field(default=12, ge=1, le=50)
    article_length: Literal["short", "normal", "detailed"] = "normal"
    style_persona: Literal["mountain_veteran", "field_reporter"] = "mountain_veteran"
    pdf_export: bool = False
    review_enabled: bool = False
    mode: Literal["blog", "photobook"] = "blog"
    photobook: PhotobookConfig = PhotobookConfig()
    photobook_preset: Literal[
        "nature_outdoor", "culture_architecture", "people", "nature_collage", "mixed"
    ] = "mixed"
```

- [ ] **Step 2: Run existing state tests**

```bash
uv run pytest tests/test_state.py -v
```
Expected: 25 passed (no regressions)

- [ ] **Step 3: Commit**

```bash
git add app/state.py
git commit -m "feat: add review_enabled field to OutputConfig"
```

---

### Task 2: Add `status` and `revision_round` to Article DB model

**Files:**
- Modify: `app/db/models.py:11-33`

- [ ] **Step 1: Add columns**

In `app/db/models.py`, add to the `Article` class after `notes`:

```python
status = Column(String, default="published")
revision_round = Column(Integer, default=0)
```

The `Article` class should now include these as the last column definitions before `images`:

```python
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
    status = Column(String, default="published")
    revision_round = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.now)

    images = relationship("ArticleImage", back_populates="article", cascade="all, delete-orphan")
```

- [ ] **Step 2: Run DB model tests**

```bash
uv run pytest tests/test_db_models.py -v
```
Expected: All pass (columns with defaults don't break existing rows)

- [ ] **Step 3: Commit**

```bash
git add app/db/models.py
git commit -m "feat: add status and revision_round columns to Article"
```

---

### Task 3: Add `status` filter and `update()` method to repository

**Files:**
- Modify: `app/db/repository.py:12-93`

- [ ] **Step 1: Add `status` to `ArticleFilters`**

In `app/db/repository.py`, add to the `ArticleFilters` dataclass:

```python
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
```

- [ ] **Step 2: Apply `status` filter in `list()` method**

In the `list()` method of `ArticleRepository`, add after the `generated_to` filter check:

```python
if filters.status:
    q = q.where(Article.status == filters.status)
```

- [ ] **Step 3: Add `update()` method to `ArticleRepository`**

Add this method to the `ArticleRepository` class after `delete_batch()`:

```python
def update(self, article_id: int, updates: dict) -> Optional[Article]:
    """Aktualisiert Felder eines Artikels. Gibt den aktualisierten Artikel zurück."""
    article = self.get_by_id(article_id)
    if article is None:
        return None
    for key, value in updates.items():
        setattr(article, key, value)
    self.session.commit()
    return article
```

- [ ] **Step 4: Run repository tests**

```bash
uv run pytest tests/test_repository.py -v
```
Expected: All pass

- [ ] **Step 5: Commit**

```bash
git add app/db/repository.py
git commit -m "feat: add status filter and update method to ArticleRepository"
```

---

### Task 4: Add optional `status` param to `persist_article` service

**Files:**
- Modify: `app/services/persist_article.py:81-156`

- [ ] **Step 1: Add `status` parameter**

Modify the `persist_article()` function signature to accept an optional `status` parameter. Change line 81-88 from:

```python
def persist_article(
    blog_post: Dict[str, Any],
    gpx_stats: Any,
    images: list,
    gpx_file: str,
    model: str,
    notes: Optional[str] = None,
) -> Optional[int]:
```

To:

```python
def persist_article(
    blog_post: Dict[str, Any],
    gpx_stats: Any,
    images: list,
    gpx_file: str,
    model: str,
    notes: Optional[str] = None,
    status: str = "published",
) -> Optional[int]:
```

- [ ] **Step 2: Include `status` and `revision_round` in `article_data`**

In the `article_data` dict (around line 119), add:

```python
"status": status,
"revision_round": 0,
```

So the dict at that point reads:

```python
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
    "html_content": _sanitize_html(html),
    "markdown_path": file_paths.get("markdown", ""),
    "html_path": file_paths.get("html", ""),
    "model_used": model,
    "notes": notes,
    "status": status,
    "revision_round": 0,
}
```

- [ ] **Step 3: Run persist service tests**

```bash
uv run pytest tests/test_persist_service.py -v
```
Expected: All pass (default `status="published"` is backward-compatible)

- [ ] **Step 4: Commit**

```bash
git add app/services/persist_article.py
git commit -m "feat: add optional status parameter to persist_article service"
```

---

### Task 5: Create `save_draft` node

**Files:**
- Create: `app/nodes/save_draft.py`
- Modify: `app/state.py` (already done in Task 1)

- [ ] **Step 1: Write the `save_draft_node`**

Create `app/nodes/save_draft.py`:

```python
from app.state import AppState
from app.services.persist_article import persist_article


def save_draft_node(state: AppState) -> AppState:
    """Speichert den generierten Blogpost als Draft in der Datenbank."""
    blog_post = state.blog_post
    if not blog_post:
        return state

    article_id = persist_article(
        blog_post=blog_post,
        gpx_stats=state.gpx_stats,
        images=state.selected_images,
        gpx_file=state.gpx_file,
        model=state.model,
        notes=state.notes,
        status="draft",
    )

    if article_id:
        state.metadata["article_id"] = article_id

    return state
```

- [ ] **Step 2: Commit**

```bash
git add app/nodes/save_draft.py
git commit -m "feat: add save_draft node"
```

---

### Task 6: Add conditional edge + save_draft node to graph

**Files:**
- Modify: `app/graph.py:1-208`

- [ ] **Step 1: Import `save_draft_node`**

Add after line 14 (after `review_content_node` import):

```python
from app.nodes.save_draft import save_draft_node
```

- [ ] **Step 2: Add `save_draft` to `NODE_NAMES`**

Add after line 41 (`"persist_article"` entry):

```python
"save_draft": "Draft speichern",
```

- [ ] **Step 3: Create wrapped node for `save_draft`**

Add after line 120 (`pan = ...` and before the `builder.add_node` block), the `_wrap_node` call for `save_draft`:

```python
sdn = _wrap_node(save_draft_node, "save_draft", event_emitter) if event_emitter else save_draft_node
```

- [ ] **Step 4: Register `save_draft` node and fix graph edges**

Add the node registration after line 137 (`builder.add_node("generate_enriched_map", gem)`):

```python
builder.add_node("save_draft", sdn)
```

Replace the existing direct edge from `design_blogpost` to `persist_article` (line 194) with a conditional edge. Remove lines 193-194:

```python
builder.add_edge("generate_blog_post", "design_blogpost")
builder.add_edge("design_blogpost", "persist_article")
```

And replace with:

```python
builder.add_edge("generate_blog_post", "design_blogpost")

def _route_after_design(state: AppState) -> str:
    if state.output_config.review_enabled:
        return "save_draft"
    return "persist_article"

builder.add_conditional_edges(
    "design_blogpost",
    _route_after_design,
    {
        "save_draft": "save_draft",
        "persist_article": "persist_article",
    },
)

# save_draft ends the pipeline (no PDF in draft mode)
builder.add_edge("save_draft", END)
```

- [ ] **Step 5: Commit**

```bash
git add app/graph.py
git commit -m "feat: add save_draft conditional edge to blog pipeline"
```

---

### Task 7: Update events and pipeline background runner for draft support

**Files:**
- Modify: `app/api/events.py:37-50`
- Modify: `app/api/routes.py:260-444`

- [ ] **Step 1: Add `draft_id` to `complete_run()`**

In `app/api/events.py`, modify `complete_run()` to accept `draft_id`:

```python
def complete_run(self, run_id: str, status: str, output_dir: str = "",
                 article_id: int = None, photobook_id: int = None,
                 draft_id: int = None, pdf_available: bool = False):
    """Signal pipeline completion and store the result."""
    queue = self._runs.get(run_id)
    if queue is None or self._loop is None:
        return
    event = {"stage": "__done__", "status": status, "output_dir": output_dir}
    if article_id is not None:
        event["article_id"] = article_id
    if photobook_id is not None:
        event["photobook_id"] = photobook_id
    if draft_id is not None:
        event["draft_id"] = draft_id
    event["pdf_available"] = pdf_available
    self._loop.call_soon_threadsafe(queue.put_nowait, event)
```

- [ ] **Step 2: Add `review_enabled` to `RunPipelineRequest`**

Add after line 270 (`pdf_export` field) in `app/api/routes.py`:

```python
review_enabled: bool = False
```

- [ ] **Step 3: Wire `review_enabled` into `OutputConfig` in background runner**

In `_run_pipeline_in_background()`, add `review_enabled=body.review_enabled` to the `OutputConfig` constructor (around line 378-386):

```python
state = AppState(
    gpx_file=gpx_file,
    model=model,
    notes=combined_notes,
    output_config=OutputConfig(
        mode=body.mode,
        wildcard_max=body.wildcard_max,
        article_length=body.article_length,
        style_persona=body.style_persona,
        pdf_export=body.pdf_export,
        review_enabled=body.review_enabled,
        photobook=photobook_config,
        photobook_preset=body.photobook_preset,
    ),
)
```

- [ ] **Step 4: Send `draft_id` in done event when review mode**

In `_run_pipeline_in_background()`, replace the `event_manager.complete_run()` call (lines 431-436) with logic that checks for draft mode:

```python
article_id = None
photobook_id = None
draft_id = None
pdf_available = False
if hasattr(result, "metadata"):
    aid = result.metadata.get("article_id")
    if body.review_enabled:
        draft_id = aid
        article_id = None
    else:
        article_id = aid
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
    draft_id=draft_id,
    pdf_available=pdf_available,
)
```

Note: Remove the existing `article_id`/`photobook_id` extraction block on lines 418-429 and the `complete_run` call on lines 431-436, replacing with the above.

- [ ] **Step 5: Run API tests**

```bash
uv run pytest tests/test_api_endpoints.py -v -k "not ollama"
```
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add app/api/events.py app/api/routes.py
git commit -m "feat: add draft_id support to pipeline events and background runner"
```

---

### Task 8: Create revision service (`revise_blogpost.py`)

**Files:**
- Create: `app/services/revise_blogpost.py`

- [ ] **Step 1: Write `call_ollama_text()` helper**

Create `app/services/revise_blogpost.py`:

```python
"""Service für die LLM-basierte Überarbeitung von Blog-Drafts."""
import re
from typing import Dict, Any, List, Optional

from app.config import OLLAMA_BASE_URL


def _call_ollama_text(
    system_prompt: str,
    user_prompt: str,
    model: str = "gemma4:26b-ctx128k",
) -> Optional[str]:
    """Ruft Ollama mit reinem Text auf (keine Bilder)."""
    import requests

    url = f"{OLLAMA_BASE_URL.rstrip('/')}/api/chat"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
        "options": {
            "temperature": 0.7,
            "top_p": 0.9,
            "num_predict": 16384,
        },
        "keep_alive": "10m",
    }

    try:
        response = requests.post(url, json=payload, timeout=600)
        if response.status_code == 200:
            result = response.json()
            return result.get("message", {}).get("content", "")
        else:
            print(f"❌ Ollama API Error: {response.status_code}")
            print(f"Response: {response.text[:500]}")
            return None
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to Ollama. Is it running? (ollama serve)")
        return None
    except Exception as e:
        print(f"❌ Error calling Ollama: {e}")
        return None
```

- [ ] **Step 2: Write `_count_paragraphs()` helper**

```python
def _count_paragraphs(markdown: str) -> int:
    """Zählt Text-Absätze im Markdown (nicht-Überschrift, nicht-leer)."""
    paragraphs = 0
    for line in markdown.split("\n"):
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and not stripped.startswith("!"):
            paragraphs += 1
    return paragraphs
```

- [ ] **Step 3: Write `_build_revision_prompt()` helper**

```python
def _build_revision_prompt(
    current_markdown: str,
    changes: list[dict],
    full_context: dict,
    persona: str,
    length: str,
) -> str:
    """Baut den Revisions-Prompt für Ollama."""
    persona_descriptions = {
        "mountain_veteran": "Ein erfahrener Bergsteiger mit trockenem Humor und tiefer Naturverbundenheit. Schreibt in klarer, präziser Sprache.",
        "field_reporter": "Ein Reisejournalist mit lebendigem, atmosphärischem Schreibstil. Schreibt detailreich und einfühlsam.",
    }
    persona_text = persona_descriptions.get(persona, persona_descriptions["mountain_veteran"])

    length_hints = {
        "short": "Halte den Text knapp und fokussiert.",
        "normal": "Gute Balance zwischen Detail und Lesbarkeit.",
        "detailed": "Detaillierte Beschreibungen sind erwünscht.",
    }
    length_hint = length_hints.get(length, length_hints["normal"])

    context_lines = []
    notes = full_context.get("notes")
    if notes:
        context_lines.append(f"Notizen des Autors: {notes}")

    gpx = full_context.get("gpx_stats", {})
    if gpx:
        dist = gpx.get("total_distance_km")
        gain = gpx.get("elevation_gain_m")
        loss = gpx.get("elevation_loss_m")
        if dist:
            context_lines.append(f"Distanz: {dist} km")
        if gain:
            context_lines.append(f"Aufstieg: {gain} m")
        if loss:
            context_lines.append(f"Abstieg: {loss} m")

    context_block = "\n".join(context_lines) if context_lines else "Keine Zusatzinformationen verfügbar."

    changes_block = ""
    for i, change in enumerate(changes, 1):
        changes_block += f"""
### Änderung {i}
- **Element-Typ:** {change.get('element_type', 'paragraph')}
- **Index:** {change.get('element_index', '?')}
- **Original-Text:** {change.get('original_content', '')[:300]}
- **Anweisung:** {change.get('instruction', 'Bitte umschreiben/verbessern')}
"""

    prompt = f"""Du bist ein erfahrener Reiseblog-Autor. {persona_text} {length_hint}

## Zusätzlicher Kontext
{context_block}

## Dein Auftrag
Überarbeite den folgenden Blog-Artikel NUR an den unten markierten Stellen. Alle nicht markierten Absätze MÜSSEN unverändert bleiben. Achte darauf, dass die überarbeiteten Absätze stilistisch und inhaltlich perfekt zu den umgebenden, unveränderten Absätzen passen.

WICHTIG: Ändere NUR die markierten Absätze. Wenn ein Bild markiert ist und die Anweisung ein anderes Bild vorschlägt, beschreibe kurz welche Art von Bild besser passen würde. Lösche KEINE Absätze, füge KEINE neuen Absätze hinzu.

## Vollständiger Artikel

{current_markdown}

## Markierte Änderungen
{changes_block}

Gib den KOMPLETTEN überarbeiteten Artikel aus (alle Absätze, auch die unveränderten). Das Format muss exakt dem Original entsprechen (gleiche Anzahl Absätze, gleiche Bild-Referenzen wo nicht anders angegeben).
"""
    return prompt
```

- [ ] **Step 4: Write `revise_blog_post()` main function**

```python
def revise_blog_post(
    current_markdown: str,
    changes: list[dict],
    full_context: dict,
    available_images: list[str],
    output_config,
    model: str,
) -> dict:
    """Führt eine LLM-basierte Revision des Blogposts durch.

    Args:
        current_markdown: Der aktuelle Markdown-Text des Artikels
        changes: Liste von Dictionaries mit {element_type, element_index, original_content, instruction}
        full_context: Dictionary mit {notes, gpx_stats}
        available_images: Liste der verfügbaren Bild-Pfade
        output_config: OutputConfig mit style_persona und article_length
        model: Ollama-Modellname

    Returns:
        dict mit {success, markdown, html, paragraph_count_changed}
    """
    old_count = _count_paragraphs(current_markdown)

    system_prompt = "Du bist ein professioneller Reiseblog-Autor. Deine Aufgabe ist es, Blog-Artikel auf Anweisung punktuell zu überarbeiten."

    user_prompt = _build_revision_prompt(
        current_markdown,
        changes,
        full_context,
        output_config.style_persona,
        output_config.article_length,
    )

    response = _call_ollama_text(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        model=model,
    )

    if response is None:
        return {"success": False, "markdown": "", "html": "", "paragraph_count_changed": False}

    # Clean thinking tokens
    cleaned = re.sub(r'<thinking>.*?</thinking>', '', response, flags=re.DOTALL)
    cleaned = cleaned.strip()

    new_count = _count_paragraphs(cleaned)
    paragraph_count_changed = new_count != old_count

    return {
        "success": True,
        "markdown": cleaned,
        "html": "",
        "paragraph_count_changed": paragraph_count_changed,
    }
```

- [ ] **Step 5: Commit**

```bash
git add app/services/revise_blogpost.py
git commit -m "feat: add revise_blog_post service for LLM-based draft revision"
```

---

### Task 9: Add `/revise` and `/publish` API endpoints

**Files:**
- Modify: `app/api/routes.py` (add after existing article endpoints)

- [ ] **Step 1: Add `status` query param to `GET /api/articles`**

In `app/api/routes.py`, find the `get_articles` function (around line 449). Add `status` parameter:

```python
@router.get("/articles")
async def get_articles(
    tour_date_from: Optional[str] = None,
    tour_date_to: Optional[str] = None,
    duration_min: Optional[float] = None,
    duration_max: Optional[float] = None,
    status: Optional[str] = None,
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
```

And add the status filter to the `ArticleFilters` construction:

```python
filters = ArticleFilters(
    tour_date_from=...,
    ...
    status=status,
    limit=limit,
    offset=offset,
)
```

- [ ] **Step 2: Add `RevisionItem` and `RevisionRequest` Pydantic models + import**

Add at the top of the file in the imports section (around line 1-40), or near the `RunPipelineRequest`:

```python
from typing import Literal
```

Add after the `RunPipelineRequest` class (after line 276):

```python
class RevisionItem(BaseModel):
    element_type: Literal["paragraph", "image"]
    element_index: int
    original_content: str
    instruction: str = ""


class RevisionRequest(BaseModel):
    changes: list[RevisionItem]
```

- [ ] **Step 3: Add `POST /api/articles/{id}/revise` endpoint**

Add after the `delete_batch_articles` endpoint (around line 561):

```python
@router.post("/articles/{article_id}/revise")
async def revise_article(article_id: int, body: RevisionRequest):
    """Überarbeitet einen Draft-Artikel via LLM und speichert die neue Version."""
    from app.db.connection import get_session
    from app.db.repository import ArticleRepository
    from app.services.revise_blogpost import revise_blog_post
    from app.services.design_blogpost import design_blogpost_service
    from app.state import OutputConfig

    session = get_session()
    try:
        repo = ArticleRepository(session)
        article = repo.get_by_id(article_id)
        if article is None:
            raise HTTPException(status_code=404, detail="Article not found")
        if article.status != "draft":
            raise HTTPException(status_code=400, detail="Article is not a draft")

        # Kontext aus DB-Daten zusammenbauen
        full_context = {
            "notes": article.notes,
            "gpx_stats": {
                "total_distance_km": article.total_distance_km,
                "elevation_gain_m": article.elevation_gain_m,
                "elevation_loss_m": article.elevation_loss_m,
            },
        }

        # OutputConfig für Stil-Informationen rekonstruieren
        output_config = OutputConfig(
            style_persona="mountain_veteran",
            article_length="normal",
        )

        changes_dicts = [c.model_dump() for c in body.changes]

        result = revise_blog_post(
            current_markdown=article.markdown_content or "",
            changes=changes_dicts,
            full_context=full_context,
            available_images=[],
            output_config=output_config,
            model=article.model_used or "gemma4:26b-ctx128k",
        )

        if not result["success"]:
            raise HTTPException(status_code=500, detail="LLM revision failed")

        # Design anwenden
        try:
            html = design_blogpost_service(result["markdown"])
        except Exception:
            html = result["markdown"]

        # Draft in DB aktualisieren
        new_round = (article.revision_round or 0) + 1
        repo.update(article_id, {
            "markdown_content": result["markdown"],
            "html_content": html,
            "revision_round": new_round,
        })

        return {
            "markdown": result["markdown"],
            "html": html,
            "revision_round": new_round,
            "paragraph_count_changed": result.get("paragraph_count_changed", False),
        }
    finally:
        session.close()


@router.post("/articles/{article_id}/publish")
async def publish_article(article_id: int):
    """Veröffentlicht einen Draft-Artikel (status: draft -> published)."""
    from app.db.connection import get_session
    from app.db.repository import ArticleRepository

    session = get_session()
    try:
        repo = ArticleRepository(session)
        article = repo.get_by_id(article_id)
        if article is None:
            raise HTTPException(status_code=404, detail="Article not found")
        if article.status != "draft":
            raise HTTPException(status_code=400, detail="Article is not a draft")

        repo.update(article_id, {"status": "published"})
        return {"status": "published", "article_id": article_id}
    finally:
        session.close()
```

- [ ] **Step 4: Commit**

```bash
git add app/api/routes.py
git commit -m "feat: add /revise and /publish API endpoints for draft workflow"
```

---

### Task 10: Add frontend stores + update RunResult type

**Files:**
- Modify: `frontend/src/lib/stores/pipeline.ts:1-130`

- [ ] **Step 1: Add `draft_id` to `RunResult`**

In `frontend/src/lib/stores/pipeline.ts`, extend `RunResult`:

```typescript
export interface RunResult {
  success: boolean;
  markdown?: string;
  html?: string;
  file_paths?: Record<string, string>;
  error?: string;
  draft_id?: number;
  article_id?: number;
}
```

- [ ] **Step 2: Add new stores**

After line 52 (after `photobookPreset` store):

```typescript
export const reviewEnabled = writable<boolean>(false);
export const currentDraftId = writable<number | null>(null);
```

- [ ] **Step 3: Handle `draft_id` in SSE done event + auto-fetch result**

In the SSE `done` event listener (around line 85-109), modify to handle `draft_id`:

Replace the `done` event handler body (inside `addEventListener("done", ...)`) with:

```typescript
eventSource.addEventListener("done", async (e: MessageEvent) => {
    eventSource?.close();
    const data = JSON.parse(e.data);
    const isSuccess = data.status === "success";
    addLine("__done__", data.status, `Pipeline ${isSuccess ? "erfolgreich" : "fehlgeschlagen"}.`);
    runState.set(isSuccess ? "done" : "failed");

    if (data.pdf_available) {
      if (data.article_id) {
        window.open(`/api/articles/${data.article_id}/pdf`, "_blank");
      } else if (data.photobook_id) {
        window.open(`/api/photobooks/${data.photobook_id}/pdf`, "_blank");
      }
    }

    if (data.draft_id) {
      currentDraftId.set(data.draft_id);
      result.set({
        success: true,
        draft_id: data.draft_id,
      });
    } else {
      try {
        const res = await fetch(`/api/pipeline/result/${runId}`);
        if (res.ok) {
          result.set(await res.json());
        }
      } catch (err) {
        console.error("Failed to fetch result:", err);
      }
    }
  });
```

- [ ] **Step 4: Add `currentDraftId` to `resetPipeline`**

In `resetPipeline()` (line 124), add:

```typescript
currentDraftId.set(null);
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/stores/pipeline.ts
git commit -m "feat: add reviewEnabled, currentDraftId stores and draft_id to RunResult"
```

---

### Task 11: Update frontend router for draft routes

**Files:**
- Modify: `frontend/src/lib/stores/router.ts:1-71`

- [ ] **Step 1: Add `draft` route type**

In `frontend/src/lib/stores/router.ts`, modify the `Route` type:

```typescript
export type Route =
  | { page: "pipeline" }
  | { page: "articles" }
  | { page: "article"; id: number }
  | { page: "draft"; id: number }
  | { page: "photobooks" }
  | { page: "photobook"; id: number };
```

- [ ] **Step 2: Add hash parsing for `draft/{id}`**

In `parseHash()`, add after the `article` match:

```typescript
const draftMatch = path.match(/^draft\/(\d+)$/);
if (draftMatch) {
  return { page: "draft", id: parseInt(draftMatch[1], 10) };
}
```

- [ ] **Step 3: Add `navigateTo` case for `draft`**

In `navigateTo()`, add:

```typescript
case "draft":
  hash = `#/draft/${route.id}`;
  break;
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/lib/stores/router.ts
git commit -m "feat: add draft route type to frontend router"
```

---

### Task 12: Create `ReviewCheckbox.svelte`

**Files:**
- Create: `frontend/src/lib/ReviewCheckbox.svelte`

- [ ] **Step 1: Write the component**

```svelte
<svelte:options runes />

<script lang="ts">
  import { reviewEnabled } from "./stores/pipeline";

  let enabled = $derived($reviewEnabled);

  function toggle() {
    reviewEnabled.set(!$reviewEnabled);
  }
</script>

<div class="review-checkbox">
  <label class="checkbox-label">
    <input
      type="checkbox"
      checked={enabled}
      onchange={toggle}
    />
    <span class="checkbox-text">Entwurf vor Veröffentlichung prüfen</span>
  </label>
</div>

<style>
  .review-checkbox {
    padding: 0.25rem 0;
  }
  .checkbox-label {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    cursor: pointer;
    font-size: 0.72rem;
    color: var(--text-secondary);
  }
  .checkbox-label input[type="checkbox"] {
    accent-color: var(--accent);
    width: 14px;
    height: 14px;
    cursor: pointer;
  }
  .checkbox-text {
    user-select: none;
  }
</style>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/lib/ReviewCheckbox.svelte
git commit -m "feat: add ReviewCheckbox component"
```

---

### Task 13: Add `ReviewCheckbox` to `SettingsTabs`

**Files:**
- Modify: `frontend/src/lib/SettingsTabs.svelte:1-108`

- [ ] **Step 1: Import and add to blog mode**

In `SettingsTabs.svelte`, add the import:

```svelte
import ReviewCheckbox from "./ReviewCheckbox.svelte";
```

In the blog mode section (around line 40-44), add `<ReviewCheckbox />` after `<PdfExportCheckbox />`:

```svelte
{#if current === "blog"}
  <WildcardCount />
  <LengthSelector />
  <StyleSelector />
  <PdfExportCheckbox />
  <ReviewCheckbox />
{:else}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/lib/SettingsTabs.svelte
git commit -m "feat: add ReviewCheckbox to blog settings"
```

---

### Task 14: Send `review_enabled` from `RunButton`

**Files:**
- Modify: `frontend/src/lib/RunButton.svelte:1-144`

- [ ] **Step 1: Import and include in request body**

In `RunButton.svelte`, add `reviewEnabled` to the imports:

```typescript
import {
  runState,
  addLine,
  startStream,
  resetPipeline,
  selectedModel,
  pipelineFiles,
  outputDir,
  notesField,
  wildcardCount,
  articleLength,
  stylePersona,
  pdfExport,
  reviewEnabled,
  photobookSize,
  photobookPreset,
  pipelineMode,
} from "./stores/pipeline";
```

In the blog mode section (around line 49-57), add `review_enabled`:

```typescript
if (mode === "blog") {
  const wc = get(wildcardCount);
  const length = get(articleLength);
  const persona = get(stylePersona);
  const pdf = get(pdfExport);
  const review = get(reviewEnabled);
  body.wildcard_max = wc;
  body.article_length = length;
  body.style_persona = persona;
  body.pdf_export = pdf;
  body.review_enabled = review;
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/lib/RunButton.svelte
git commit -m "feat: send review_enabled in pipeline run request"
```

---

### Task 15: Create `DraftReview.svelte` component

**Files:**
- Create: `frontend/src/lib/DraftReview.svelte`

This is the largest new component. It:
1. Loads article HTML + markdown
2. Segments HTML into clickable paragraphs/figures
3. Manages marked items with text instruction inputs
4. Sends revision requests
5. Handles publish and delete

- [ ] **Step 1: Write the component**

```svelte
<svelte:options runes />

<script lang="ts">
  import { currentDraftId } from "./stores/pipeline";
  import { navigateTo } from "./stores/router";

  let { id }: { id: number } = $props();

  interface MarkedItem {
    element_type: "paragraph" | "image";
    element_index: number;
    original_content: string;
    instruction: string;
  }

  let articleHtml: string = $state("");
  let title: string = $state("");
  let revisionRound: number = $state(0);
  let marked: MarkedItem[] = $state([]);
  let loading: boolean = $state(true);
  let sending: boolean = $state(false);
  let errorMsg: string = $state("");
  let paragraphWarning: string = $state("");
  let previewEl: HTMLDivElement | undefined = $state();

  async function loadDraft() {
    loading = true;
    errorMsg = "";
    try {
      const res = await fetch(`/api/articles/${id}`);
      if (!res.ok) throw new Error("Draft nicht gefunden");
      const article = await res.json();
      articleHtml = article.html_content || "";
      title = article.title || "Draft";
      revisionRound = article.revision_round || 0;
    } catch (e: any) {
      errorMsg = e.message;
    } finally {
      loading = false;
    }
  }

  function attachClickHandlers() {
    if (!previewEl) return;
    const blocks = previewEl.querySelectorAll("p, figure");
    blocks.forEach((block, idx) => {
      block.setAttribute("data-block-index", String(idx));
      const handler = (e: Event) => {
        e.stopPropagation();
        toggleMark(idx, block);
      };
      (block as any).__draftClickHandler = handler;
      block.addEventListener("click", handler);
    });
  }

  function toggleMark(index: number, block: Element) {
    const existingIdx = marked.findIndex((m) => m.element_index === index);
    if (existingIdx >= 0) {
      marked = marked.filter((m) => m.element_index !== index);
      block.classList.remove("marked");
    } else {
      const isFigure = block.tagName === "FIGURE";
      const content = isFigure
        ? (block.querySelector("img")?.getAttribute("src") || block.textContent?.trim() || "")
        : block.textContent?.trim() || "";
      marked = [...marked, {
        element_type: isFigure ? "image" : "paragraph",
        element_index: index,
        original_content: content.slice(0, 500),
        instruction: "",
      }];
      block.classList.add("marked");
    }
  }

  function removeMark(index: number) {
    marked = marked.filter((m) => m.element_index !== index);
    if (previewEl) {
      const block = previewEl.querySelector(`[data-block-index="${index}"]`);
      block?.classList.remove("marked");
    }
  }

  async function handleRevise() {
    if (marked.length === 0 || sending) return;
    sending = true;
    paragraphWarning = "";
    errorMsg = "";
    try {
      const res = await fetch(`/api/articles/${id}/revise`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ changes: marked }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Revision fehlgeschlagen");
      }
      const data = await res.json();
      articleHtml = data.html;
      revisionRound = data.revision_round;
      marked = [];
      if (data.paragraph_count_changed) {
        paragraphWarning = "Achtung: Das LLM hat die Absatz-Anzahl verändert. Bitte den Artikel prüfen.";
      }
    } catch (e: any) {
      errorMsg = e.message;
    } finally {
      sending = false;
    }
  }

  async function handlePublish() {
    try {
      const res = await fetch(`/api/articles/${id}/publish`, { method: "POST" });
      if (!res.ok) throw new Error("Veröffentlichung fehlgeschlagen");
      currentDraftId.set(null);
      navigateTo({ page: "article", id });
    } catch (e: any) {
      errorMsg = e.message;
    }
  }

  async function handleDelete() {
    if (!confirm("Draft wirklich verwerfen?")) return;
    try {
      await fetch(`/api/articles/${id}`, { method: "DELETE" });
      currentDraftId.set(null);
      navigateTo({ page: "pipeline" });
    } catch (e: any) {
      errorMsg = e.message;
    }
  }

  loadDraft();

  $effect(() => {
    if (articleHtml && previewEl) {
      previewEl.innerHTML = articleHtml;
      attachClickHandlers();
    }
  });
</script>

{#if loading}
  <div class="draft-status">Draft wird geladen…</div>
{:else if errorMsg}
  <div class="draft-error">Fehler: {errorMsg}</div>
{:else}
  <div class="draft-layout">
    <div class="draft-header">
      <h2>{title} <span class="revision-badge">Revision {revisionRound}</span></h2>
      {#if paragraphWarning}
        <div class="warning">{paragraphWarning}</div>
      {/if}
      {#if errorMsg}
        <div class="draft-error">{errorMsg}</div>
      {/if}
    </div>

    <div class="draft-split">
      <div class="draft-preview" bind:this={previewEl}></div>

      <div class="draft-sidebar">
        <h3>Änderungen</h3>

        {#if marked.length === 0}
          <p class="hint">Klicke auf einen Absatz oder ein Bild im Artikel, um es zu markieren.</p>
        {:else}
          {#each marked as item, i (item.element_index)}
            <div class="marked-item">
              <div class="marked-header">
                <span class="badge">Markiert #{i + 1} — {item.element_type === "image" ? "Bild" : "Absatz"} {item.element_index}</span>
              </div>
              <div class="marked-preview">{item.original_content.slice(0, 150)}…</div>
              <label>
                <span class="field-label">Anweisung:</span>
                <textarea
                  bind:value={item.instruction}
                  placeholder="z.B. Kürzer fassen, mehr Details zur Aussicht..."
                  rows={3}
                ></textarea>
              </label>
              <button class="btn-remove" onclick={() => removeMark(item.element_index)}>
                Markierung entfernen
              </button>
            </div>
          {/each}
        {/if}

        <div class="actions">
          <button
            class="btn btn-publish"
            onclick={handlePublish}
          >
            ✓ Beitrag übernehmen
          </button>
          <button
            class="btn btn-revise"
            disabled={marked.length === 0 || sending}
            onclick={handleRevise}
          >
            {sending ? "Überarbeite…" : "↻ Änderungen senden"}
          </button>
          <button
            class="btn btn-delete"
            onclick={handleDelete}
          >
            ✗ Verwerfen
          </button>
        </div>
      </div>
    </div>
  </div>
{/if}

<style>
  .draft-layout { display: flex; flex-direction: column; height: 100%; min-height: 0; }
  .draft-header { flex-shrink: 0; margin-bottom: 1rem; }
  .draft-header h2 { font-size: 1.2rem; margin: 0; color: var(--text-primary); }
  .revision-badge { font-size: 0.7rem; background: var(--accent); color: white; padding: 2px 8px; border-radius: 10px; margin-left: 0.5rem; }
  .draft-status { padding: 2rem; color: var(--text-muted); text-align: center; }
  .draft-error { padding: 0.5rem; background: #fef2f2; color: #dc2626; border-radius: 4px; font-size: 0.8rem; margin-bottom: 0.5rem; }
  .warning { padding: 0.5rem; background: #fffbeb; color: #d97706; border-radius: 4px; font-size: 0.8rem; margin-bottom: 0.5rem; }

  .draft-split { display: flex; gap: 1.5rem; flex: 1; min-height: 0; overflow: hidden; }
  .draft-preview { flex: 3; overflow-y: auto; padding: 1.5rem; background: var(--panel); border: 1px solid var(--border); border-radius: 6px; font-family: Georgia, serif; line-height: 1.7; }
  .draft-preview :global(p), .draft-preview :global(figure) { padding: 8px; margin: 8px 0; border-radius: 4px; cursor: pointer; transition: background 0.15s; border: 2px solid transparent; }
  .draft-preview :global(p:hover), .draft-preview :global(figure:hover) { background: var(--surface-alt); border-color: var(--border); }
  .draft-preview :global(.marked) { background: #e8f0fe !important; border-color: #4a90d9 !important; }

  .draft-sidebar { flex: 2; overflow-y: auto; padding: 1rem; background: var(--panel); border: 1px solid var(--border); border-radius: 6px; display: flex; flex-direction: column; gap: 0.75rem; }
  .draft-sidebar h3 { font-size: 0.85rem; color: var(--text-secondary); margin: 0; text-transform: uppercase; letter-spacing: 0.05em; }
  .hint { font-size: 0.75rem; color: var(--text-muted); text-align: center; padding: 1rem 0; }

  .marked-item { background: #f0f7ff; border: 1px solid #4a90d9; border-radius: 6px; padding: 0.75rem; }
  .badge { font-size: 0.65rem; color: #4a90d9; font-weight: 600; }
  .marked-preview { font-size: 0.7rem; color: #666; font-style: italic; margin: 0.3rem 0; }
  .field-label { font-size: 0.65rem; font-weight: 600; display: block; margin-bottom: 0.2rem; color: var(--text-secondary); }
  textarea { width: 100%; padding: 0.4rem; border: 1px solid var(--border); border-radius: 4px; font-size: 0.72rem; resize: vertical; background: var(--bg); color: var(--text-primary); box-sizing: border-box; }
  .btn-remove { background: none; border: none; color: #ef4444; font-size: 0.65rem; cursor: pointer; padding: 0; margin-top: 0.4rem; }

  .actions { display: flex; flex-direction: column; gap: 0.5rem; margin-top: auto; padding-top: 0.75rem; border-top: 1px solid var(--border); }
  .btn { width: 100%; padding: 0.5rem; border-radius: 4px; font-size: 0.75rem; font-weight: 600; cursor: pointer; border: 1px solid var(--border); transition: opacity 0.15s; }
  .btn:disabled { opacity: 0.5; cursor: not-allowed; }
  .btn-publish { background: #16a34a; color: white; border-color: #16a34a; }
  .btn-publish:hover:not(:disabled) { background: #15803d; }
  .btn-revise { background: var(--accent); color: white; border-color: var(--accent); }
  .btn-revise:hover:not(:disabled) { background: var(--accent-hover); }
  .btn-delete { background: transparent; color: var(--text-muted); }
  .btn-delete:hover { color: #ef4444; border-color: #ef4444; }
</style>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/lib/DraftReview.svelte
git commit -m "feat: add DraftReview component with mark/revision/publish workflow"
```

---

### Task 16: Integrate DraftReview into App.svelte

**Files:**
- Modify: `frontend/src/App.svelte:1-330`

- [ ] **Step 1: Import DraftReview and draft stores**

Add imports:

```svelte
import DraftReview from "./lib/DraftReview.svelte";
import { currentDraftId } from "./lib/stores/pipeline";
```

- [ ] **Step 2: Navigate to draft view on done event**

Replace the auto-navigate effect (line 44-48) with:

```svelte
$effect(() => {
  if ($runState === "running" && rt.page !== "pipeline") {
    navigateTo({ page: "pipeline" });
  }
  if ($currentDraftId !== null && rt.page !== "draft") {
    navigateTo({ page: "draft", id: $currentDraftId });
  }
});
```

- [ ] **Step 3: Render DraftReview for draft route**

In the right-content section (line 138-150), add the `draft` route case:

```svelte
<div class="right-content">
  {#if rightTab === "pipeline"}
    <OutputWindow />
  {:else if rt.page === "draft"}
    <DraftReview id={rt.id} />
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

- [ ] **Step 4: Also handle draft route in tab navigation logic (pipeline tab)**

Update the rightTab logic at line 20:

```svelte
let rightTab = $derived(rt.page === "pipeline" || rt.page === "draft" ? "pipeline" : "datenbank");
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/App.svelte
git commit -m "feat: integrate DraftReview into App layout and routing"
```

---

### Task 17: Show draft status in ArticleList

**Files:**
- Modify: `frontend/src/lib/ArticleList.svelte` (find the card/title rendering area)

- [ ] **Step 1: Add draft badge in article list cards**

Find the article title rendering in `ArticleList.svelte` and add a draft badge. If the article has a `status` field set to `"draft"`, show a badge:

In the template where each article card's title is rendered, add:

```svelte
{#if article.status === "draft"}
  <span class="draft-badge">Entwurf</span>
{/if}
```

And add the CSS:

```css
.draft-badge {
  font-size: 0.6rem;
  background: #fef3c7;
  color: #92400e;
  padding: 1px 6px;
  border-radius: 3px;
  margin-left: 0.4rem;
  font-weight: 500;
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/lib/ArticleList.svelte
git commit -m "feat: show draft status badge in article list"
```

---

### Task 18: Backend tests

**Files:**
- Create: `tests/test_draft_persistence.py`
- Create: `tests/test_revise_api.py`

- [ ] **Step 1: Write `tests/test_draft_persistence.py`**

```python
"""Tests für Draft-Persistenz (save_draft Node + status-Feld)."""
import pytest
from unittest.mock import MagicMock, patch
from app.state import AppState, OutputConfig
from app.services.persist_article import persist_article


class TestPersistArticleStatus:
    def test_persist_article_default_status_is_published(self):
        """Bei Aufruf ohne status-Parameter wird 'published' verwendet."""
        blog_post = {
            "success": True,
            "markdown": "# Test\n\nEin Absatz.",
            "html": "<h1>Test</h1><p>Ein Absatz.</p>",
            "file_paths": {"markdown": "out/test.md", "html": "out/test.html"},
            "selected_images": [],
        }

        with patch("app.services.persist_article.get_session") as mock_session:
            mock_repo = MagicMock()
            mock_repo.insert.return_value = 42
            mock_session.return_value.__enter__.return_value = None
            with patch("app.services.persist_article.ArticleRepository", return_value=mock_repo):
                result = persist_article(
                    blog_post=blog_post,
                    gpx_stats=None,
                    images=[],
                    gpx_file="test.gpx",
                    model="test-model",
                    notes=None,
                )
                assert result == 42
                call_data = mock_repo.insert.call_args[0][0]
                assert call_data["status"] == "published"
                assert call_data["revision_round"] == 0

    def test_persist_article_draft_status(self):
        """Bei Aufruf mit status='draft' wird dieser Status persistiert."""
        blog_post = {
            "success": True,
            "markdown": "# Test\n\nEin Absatz.",
            "html": "<h1>Test</h1><p>Ein Absatz.</p>",
            "file_paths": {},
            "selected_images": [],
        }

        with patch("app.services.persist_article.get_session") as mock_session:
            mock_repo = MagicMock()
            mock_repo.insert.return_value = 42
            mock_session.return_value.__enter__.return_value = None
            with patch("app.services.persist_article.ArticleRepository", return_value=mock_repo):
                result = persist_article(
                    blog_post=blog_post,
                    gpx_stats=None,
                    images=[],
                    gpx_file="test.gpx",
                    model="test-model",
                    notes=None,
                    status="draft",
                )
                assert result == 42
                call_data = mock_repo.insert.call_args[0][0]
                assert call_data["status"] == "draft"

    def test_persist_article_unsuccessful_blog_post_returns_none(self):
        result = persist_article(
            blog_post={"success": False},
            gpx_stats=None,
            images=[],
            gpx_file="",
            model="",
            notes=None,
        )
        assert result is None
```

- [ ] **Step 2: Run the draft persistence tests**

```bash
uv run pytest tests/test_draft_persistence.py -v
```
Expected: 3 passed

- [ ] **Step 3: Write `tests/test_revise_api.py`**

```python
"""Tests für die /revise und /publish API-Endpoints."""
import pytest
from unittest.mock import MagicMock, patch


class TestReviseApi:
    def test_revise_article_not_found(self, test_client):
        res = test_client.post("/api/articles/99999/revise", json={"changes": []})
        assert res.status_code == 404

    def test_revise_article_not_a_draft(self, test_client, test_session):
        """Artikel mit status='published' kann nicht revidiert werden."""
        from app.db.repository import ArticleRepository
        repo = ArticleRepository(test_session)
        article_id = repo.insert(
            {"title": "Test", "status": "published", "model_used": "gemma4", "revision_round": 0},
            []
        )
        try:
            res = test_client.post(
                f"/api/articles/{article_id}/revise",
                json={"changes": [{"element_type": "paragraph", "element_index": 0, "original_content": "test", "instruction": "rewrite"}]}
            )
            assert res.status_code == 400
            data = res.json()
            assert "not a draft" in data["detail"].lower()
        finally:
            repo.delete(article_id)

    def test_publish_article_not_found(self, test_client):
        res = test_client.post("/api/articles/99999/publish")
        assert res.status_code == 404

    def test_publish_article_success(self, test_client, test_session):
        """Draft wird erfolgreich veröffentlicht."""
        from app.db.repository import ArticleRepository
        repo = ArticleRepository(test_session)
        article_id = repo.insert(
            {"title": "Test Draft", "status": "draft", "model_used": "gemma4", "revision_round": 0},
            []
        )
        try:
            res = test_client.post(f"/api/articles/{article_id}/publish")
            assert res.status_code == 200
            data = res.json()
            assert data["status"] == "published"
            assert data["article_id"] == article_id
        finally:
            repo.delete(article_id)
```

- [ ] **Step 4: Run the revise API tests**

```bash
uv run pytest tests/test_revise_api.py -v
```
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add tests/test_draft_persistence.py tests/test_revise_api.py
git commit -m "test: add tests for draft persistence and revise/publish API"
```

---

### Task 19: Final verification — regression tests

**Files:**
- None (verification only)

- [ ] **Step 1: Run state tests**

```bash
uv run pytest tests/test_state.py -v
```
Expected: 25 passed (OutputConfig still has all required fields with defaults)

- [ ] **Step 2: Run API endpoint tests**

```bash
uv run pytest tests/test_api_endpoints.py -v -k "not ollama"
```
Expected: All pass

- [ ] **Step 3: Run all new tests**

```bash
uv run pytest tests/test_draft_persistence.py tests/test_revise_api.py tests/test_repository.py -v
```
Expected: All pass

- [ ] **Step 4: Verify frontend compiles**

```bash
cd frontend && npm run check
```
Expected: No TypeScript / Svelte errors

- [ ] **Step 5: Commit**

```bash
git commit --allow-empty -m "verify: all tests pass, frontend compiles cleanly"
```

---
