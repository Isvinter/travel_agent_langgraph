# Photobook-Pipeline Robustness Refactor — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Die Photobook-Pipeline robuster machen durch Batch-basierte Content-Generierung (3 Seiten/Batch), Tour-Summary-Node, Thinking-Mode-Deaktivierung und Kontext-Reduktion in allen drei LLM-Pässen.

**Architecture:** Neuer Shared Node `summarize_context` generiert kompakte Tour-Zusammenfassung vor der blog/photobook-Verzweigung. Pass 0/1 nutzen die Summary statt roher Notizen. Pass 2 teilt Seiten in Batches à 3, sendet nur Batch-Bilder ans LLM mit deaktiviertem Thinking Mode. Batch-Größe in `config.py` konfigurierbar.

**Tech Stack:** Python 3.12, LangGraph, Pydantic, Ollama API, pytest

---

### Task 1: ollama_client.py — `disable_thinking` Parameter

**Files:**
- Modify: `app/services/ollama_client.py`

- [ ] **Step 1: Füge `disable_thinking` Parameter zur Signatur hinzu**

In `call_ollama()`, nach `strip_thinking: bool = False` einfügen:

```python
    disable_thinking: bool = False,
```

- [ ] **Step 2: Füge `thinking` ins Request-Payload ein**

Nach der `options`-Definition (ca. Zeile 76-78) und vor der `payload`-Konstruktion:

```python
    payload: dict = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": options,
        "keep_alive": keep_alive,
    }
    if disable_thinking:
        payload["thinking"] = {"type": "disabled"}
```

*Hinweis:* Der existierende Code setzt `payload` in Zeile 80-86. Das `if disable_thinking` nach der `payload`-Definition einfügen, vor dem `try`-Block.

- [ ] **Step 3: Verifiziere, dass existierende Calls nicht brechen**

Run: `uv run pytest tests/test_photobook/test_generate.py tests/test_photobook/test_plan.py -v`
Expected: Alle existierenden Tests passen (Mock ignoriert den neuen Parameter).

- [ ] **Step 4: Commit**

```bash
git add app/services/ollama_client.py
git commit -m "feat: add disable_thinking parameter to call_ollama"
```

---

### Task 2: state.py — `tour_summary` Feld

**Files:**
- Modify: `app/state.py`

- [ ] **Step 1: Füge `tour_summary` zu `AppState` hinzu**

In `class AppState`, nach `notes: Optional[str] = None` einfügen:

```python
    tour_summary: Optional[str] = None
```

- [ ] **Step 2: Verifiziere State-Konstruktion**

Run: `uv run pytest tests/test_state.py -v`
Expected: State-Tests passen unverändert (neues Optional-Feld bricht nichts).

- [ ] **Step 3: Commit**

```bash
git add app/state.py
git commit -m "feat: add tour_summary field to AppState"
```

---

### Task 3: config.py — `PHOTOBOOK_BATCH_SIZE`

**Files:**
- Modify: `app/config.py`

- [ ] **Step 1: Füge Konstante hinzu**

Am Ende von `app/config.py` (vor dem letzten Kommentar oder als letzte Zeile):

```python
# Batch-Grösse für die Fotobuch-Generierung (Pass 2). Reduzieren bei Kontext-Problemen.
PHOTOBOOK_BATCH_SIZE = 3
```

- [ ] **Step 2: Commit**

```bash
git add app/config.py
git commit -m "feat: add PHOTOBOOK_BATCH_SIZE config constant"
```

---

### Task 4: summarize_context Service + Tests

**Files:**
- Create: `app/services/summarize_context.py`
- Create: `tests/test_services/test_summarize_context.py`

- [ ] **Step 1: Schreibe den Test für den deterministischen Fallback**

Create `tests/test_services/test_summarize_context.py`:

```python
"""Tests fuer den Tour-Summary-Service."""
import pytest
from unittest.mock import patch
from app.services.summarize_context import summarize_context


class TestSummarizeContext:
    def test_returns_summary_when_llm_succeeds(self):
        with patch("app.services.summarize_context.call_ollama") as mock_call:
            mock_call.return_value = "Eine 14km Wanderung im Allgäu im Herbst. Familienausflug."
            result = summarize_context(
                notes="Schöne Herbsttour mit der Familie.",
                gpx_distance_km=14.3,
                gpx_elevation_m=520,
                preset="nature_outdoor",
                model="test-model",
            )
            assert result is not None
            assert "14" in result or "Wanderung" in result
            assert mock_call.called

    def test_fallback_when_llm_fails(self):
        with patch("app.services.summarize_context.call_ollama", return_value=None):
            result = summarize_context(
                notes="Beliebiger Text.",
                gpx_distance_km=14.3,
                gpx_elevation_m=520,
                preset="nature_outdoor",
                model="test-model",
            )
            assert result is not None
            assert "14.3" in result
            assert "km" in result

    def test_fallback_when_no_notes_no_gpx(self):
        result = summarize_context(
            notes=None,
            gpx_distance_km=None,
            gpx_elevation_m=None,
            preset="mixed",
            model="test-model",
        )
        assert result is not None
        # Minimal-Summary soll trotzdem nicht leer sein
        assert len(result) > 0

    def test_prompt_includes_tour_data(self):
        with patch("app.services.summarize_context.call_ollama") as mock_call:
            mock_call.return_value = "Test-Summary"
            summarize_context(
                notes="Lange Tour durch die Berge.",
                gpx_distance_km=25.0,
                gpx_elevation_m=1200,
                preset="nature_outdoor",
                model="test-model",
            )
            prompt = mock_call.call_args[0][0]
            assert "25.0" in prompt
            assert "1200" in prompt
            assert "Lange Tour" in prompt or "Berge" in prompt

    def test_prompt_handles_none_notes(self):
        with patch("app.services.summarize_context.call_ollama") as mock_call:
            mock_call.return_value = "Test-Summary"
            summarize_context(
                notes=None,
                gpx_distance_km=5.0,
                gpx_elevation_m=200,
                preset="nature_outdoor",
                model="test-model",
            )
            prompt = mock_call.call_args[0][0]
            assert "5.0" in prompt
            assert "200" in prompt
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_services/test_summarize_context.py -v`
Expected: FAIL — Module nicht gefunden.

- [ ] **Step 3: Implementiere den Service**

Create `app/services/summarize_context.py`:

```python
"""Tour-Summary-Service: Erzeugt kompakte Tour-Zusammenfassung via LLM."""

import logging
from typing import Optional
from app.services.ollama_client import call_ollama

logger = logging.getLogger(__name__)

PRESET_TOUR_TYPE = {
    "nature_outdoor": "Wanderung",
    "nature_collage": "Naturtour",
    "culture_architecture": "Städtetrip",
    "people": "Gruppenausflug",
    "mixed": "Tour",
}

SUMMARIZE_PROMPT = """Erstelle eine kurze Zusammenfassung dieser Tour (max. 150 Wörter).
Enthalte: Tourtyp (Wanderung/Radtour/Städtetrip), Region/Gebiet,
Jahreszeit, besonderer Anlass (falls erkennbar).
Keine detaillierten Wegbeschreibungen.

TOURDATEN: {distance}km, {elevation}m Aufstieg
TOURNOTIZEN: {notes}"""


def _build_summary_prompt(
    notes: Optional[str],
    distance_km: Optional[float],
    elevation_m: Optional[float],
) -> str:
    dist_str = f"{distance_km:.1f}" if distance_km is not None else "?"
    elev_str = f"{elevation_m:.0f}" if elevation_m is not None else "?"
    notes_str = notes if notes else "Keine Notizen vorhanden."
    return SUMMARIZE_PROMPT.format(distance=dist_str, elevation=elev_str, notes=notes_str)


def _build_fallback_summary(
    distance_km: Optional[float],
    elevation_m: Optional[float],
    preset: str,
) -> str:
    tour_type = PRESET_TOUR_TYPE.get(preset, "Tour")
    parts = []
    if distance_km is not None:
        parts.append(f"{distance_km:.1f}km")
    parts.append(tour_type)
    if elevation_m is not None and elevation_m > 0:
        parts.append(f"mit {elevation_m:.0f}m Aufstieg")
    return " ".join(parts) + "."


def summarize_context(
    notes: Optional[str],
    gpx_distance_km: Optional[float],
    gpx_elevation_m: Optional[float],
    preset: str,
    model: str = "gemma4:26b-ctx128k",
) -> str:
    prompt = _build_summary_prompt(notes, gpx_distance_km, gpx_elevation_m)
    try:
        content = call_ollama(
            prompt,
            model=model,
            temperature=0.0,
            num_predict=1024,
            timeout=60,
            disable_thinking=True,
        )
        if content and content.strip():
            return content.strip()
    except Exception as e:
        logger.warning("Summarize-LLM fehlgeschlagen: %s", e)

    return _build_fallback_summary(gpx_distance_km, gpx_elevation_m, preset)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_services/test_summarize_context.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add app/services/summarize_context.py tests/test_services/test_summarize_context.py
git commit -m "feat: add summarize_context service with LLM + deterministic fallback"
```

---

### Task 5: summarize_context Node

**Files:**
- Create: `app/nodes/summarize_context_node.py`

- [ ] **Step 1: Implementiere den Node**

Create `app/nodes/summarize_context_node.py`:

```python
import logging
from app.state import AppState
from app.services.summarize_context import summarize_context

logger = logging.getLogger(__name__)


def summarize_context_node(state: AppState) -> AppState:
    logger.info("Erstelle Tour-Zusammenfassung...")
    distance_km = None
    elevation_m = None
    if state.gpx_stats:
        distance_km = state.gpx_stats.total_distance_m / 1000.0
        elevation_m = state.gpx_stats.elevation_gain_m

    state.tour_summary = summarize_context(
        notes=state.notes,
        gpx_distance_km=distance_km,
        gpx_elevation_m=elevation_m,
        preset=state.output_config.photobook_preset,
        model=state.model,
    )
    logger.info("Tour-Summary: %s", state.tour_summary[:100] if state.tour_summary else "None")
    return state
```

- [ ] **Step 2: Commit**

```bash
git add app/nodes/summarize_context_node.py
git commit -m "feat: add summarize_context node"
```

---

### Task 6: graph.py — summarize_context Node integrieren

**Files:**
- Modify: `app/graph.py`

- [ ] **Step 1: Füge den Import hinzu**

In `app/graph.py`, nach den existierenden Node-Imports:

```python
from app.nodes.summarize_context_node import summarize_context_node
```

- [ ] **Step 2: Füge den Node zum Builder hinzu**

Nach `builder.add_node("load_tour_notes", load_tour_notes_node)` (ca. Zeile 149):

```python
    builder.add_node("summarize_context", summarize_context_node)
```

- [ ] **Step 3: Ändere die Edges**

Zeige `generate_map_image → load_tour_notes → summarize_context → [blog oder photobook]`:

```python
    builder.add_edge("generate_map_image", "load_tour_notes")
    builder.add_edge("load_tour_notes", "summarize_context")

    # Mode-abhaengiges Routing NACH summarize_context:
    def _route_after_summary(state: AppState) -> str:
        if state.output_config.mode == "photobook":
            return "select_photobook_images"
        return "enrich_weather"

    builder.add_conditional_edges(
        "summarize_context",
        _route_after_summary,
        {
            "select_photobook_images": "select_photobook_images",
            "enrich_weather": "enrich_weather",
        },
    )
```

**Wichtig:** Die alte `_route_after_notes` Funktion sowie die alte `builder.add_conditional_edges("load_tour_notes", ...)` müssen ersetzt/entfernt werden. Alle anderen Edges (Blog-Pfad, Photobook-Pfad) bleiben unverändert.

- [ ] **Step 4: Verifiziere Graph-Kompilierung**

Run: `uv run python -c "from app.graph import build_graph; g = build_graph(); print('Graph OK:', len(g.nodes))"`
Expected: Graph OK: N (N > 10, neue Node-Anzahl)

- [ ] **Step 5: Commit**

```bash
git add app/graph.py
git commit -m "feat: integrate summarize_context node into graph, route after summary"
```

---

### Task 7: image_selector.py + Node — tour_summary nutzen, disable_thinking

**Files:**
- Modify: `app/photobook/image_selector.py`
- Modify: `app/nodes/select_photobook_images_node.py`

- [ ] **Step 1: `_build_batch_prompt` um `tour_summary` erweitern**

In `app/photobook/image_selector.py`, ändere die Signatur und den Prompt:

```python
def _build_batch_prompt(batch_size: int, select_count: int, preset: PhotobookPreset, tour_summary: Optional[str] = None) -> str:
    criteria = preset.selection_criteria if preset.selection_criteria else (
        "starke Motive, gute Belichtung, landschaftliche Vielfalt, "
        "verschiedene Perspektiven, Details und Porträts mischen."
    )
    header = ""
    if tour_summary:
        header = f"TOUR: {tour_summary}\n\n"
    return (
        f"{header}"
        f"Du erhältst {batch_size} Fotos aus dieser Tour.\n"
        f"Wähle die {select_count} besten Bilder für ein A4-Fotobuch "
        f"({preset.name}).\n"
        f"Kriterien: {criteria}\n"
        "Antworte NUR mit den 0-basierten Indexnummern, kommagetrennt, aufsteigend. "
        "Keine Erklärung.\n\n"
        + "\n".join(f"--- Bild {i} ---" for i in range(batch_size))
    )
```

- [ ] **Step 2: `_select_batch` um `tour_summary` erweitern und `disable_thinking` setzen**

```python
def _select_batch(
    batch_images: List[ImageData],
    select_count: int,
    model: str,
    base_url: str,
    preset: PhotobookPreset,
    tour_summary: Optional[str] = None,
) -> List[int]:
```

Prompt-Erstellung in `_select_batch`:
```python
    prompt = _build_batch_prompt(len(encoded), select_count, preset, tour_summary=tour_summary)
```

LLM-Call:
```python
    response = call_ollama(
        prompt,
        model=model,
        base_url=base_url,
        images=encoded,
        temperature=0.0,
        top_p=0.1,
        num_predict=16384,
        timeout=120,
        disable_thinking=True,
    )
```

- [ ] **Step 3: `select_photobook_images` Signatur anpassen**

```python
def select_photobook_images(
    images: List[ImageData],
    tour_summary: Optional[str] = None,
    model: str = "gemma4:26b-ctx128k",
    photo_count: int = 16,
    base_url: str = OLLAMA_BASE_URL,
    preset: Optional[PhotobookPreset] = None,
) -> List[ImageData]:
```

Entferne `gpx_stats` und `notes` aus der Signatur, ersetze durch `tour_summary`.

Passe die Aufrufe von `_select_batch` an (2 Stellen: Zeile 123 und Zeile 138):

```python
        batch_indices = _select_batch(batch, select, model, base_url, preset, tour_summary=tour_summary)
```

und

```python
    final_indices = _select_batch(selected, target, model, base_url, preset, tour_summary=tour_summary)
```

- [ ] **Step 4: Node anpassen**

In `app/nodes/select_photobook_images_node.py`:

```python
def select_photobook_images_node(state: AppState) -> AppState:
    logger.info("Waehle Bilder fuer das Fotobuch aus...")
    if not state.images:
        logger.warning("Keine Bilder fuer Fotobuch-Auswahl vorhanden.")
        return state
    gpx_dict, preset = _get_photobook_context(state)
    try:
        selected = select_photobook_images(
            images=state.images,
            tour_summary=state.tour_summary,
            model=state.model,
            photo_count=state.output_config.photobook.photo_count,
            preset=preset,
        )
        state.photobook_images = selected
        logger.info("%s Bilder fuer das Fotobuch ausgewaehlt.", len(selected))
    except Exception as e:
        logger.error("Fotobuch-Bildauswahl fehlgeschlagen: %s — verwende alle Bilder", e)
        max_count = state.output_config.photobook.photo_count
        state.photobook_images = state.images[:max_count]
    return state
```

- [ ] **Step 5: Tests verifizieren**

Run: `uv run pytest tests/test_photobook/test_image_selector.py -v`
Expected: Tests passen (ggf. anpassen wenn sie `gpx_stats` oder `notes` übergeben).

- [ ] **Step 6: Commit**

```bash
git add app/photobook/image_selector.py app/nodes/select_photobook_images_node.py
git commit -m "feat: use tour_summary in image selector, disable thinking mode"
```

---

### Task 8: plan.py + Node — tour_summary, reduzierter Kontext, disable_thinking

**Files:**
- Modify: `app/photobook/plan.py`
- Modify: `app/nodes/plan_photobook_node.py`

- [ ] **Step 1: `_build_plan_prompt` Signatur ändern**

```python
def _build_plan_prompt(
    image_count: int,
    gpx_stats_d: Optional[Dict[str, Any]],
    tour_summary: Optional[str],
    page_range: Optional[str] = None,
    preset: Optional[PhotobookPreset] = None,
) -> str:
```

Entferne `notes`, `weather`, `poi_count` Parameter.

- [ ] **Step 2: Prompt-Kontext umbauen**

Ersetze den gesamten `context_parts`-Block (Zeilen 50-61):

```python
    context_parts = [f"BILDER: {image_count} Fotos (chronologisch sortiert, Index 0-{image_count - 1})"]
    if gpx_stats_d:
        dist = gpx_stats_d.get("total_distance_m", 0) / 1000
        elev = gpx_stats_d.get("elevation_gain_m", 0)
        context_parts.append(f"TOURDATEN: {dist:.1f} km, {elev:.0f}m Hoehenmeter")
    if tour_summary:
        context_parts.append(f"TOUR: {tour_summary}")
    context = "\n".join(context_parts)
```

- [ ] **Step 3: `plan_photobook_layout` Signatur anpassen**

```python
def plan_photobook_layout(
    images: List[ImageData],
    gpx_stats: Optional[Dict[str, Any]],
    tour_summary: Optional[str],
    model: str = "gemma4:26b-ctx128k",
    base_url: str = OLLAMA_BASE_URL,
    page_range: str = "",
    preset: Optional[PhotobookPreset] = None,
) -> PhotobookPlan:
```

Entferne `notes`, `weather`, `poi_list` Parameter.

- [ ] **Step 4: `_build_plan_prompt` Aufruf in `plan_photobook_layout` anpassen**

```python
    prompt = _build_plan_prompt(
        len(images), gpx_stats, tour_summary,
        page_range=page_range if page_range else None,
        preset=preset,
    )
```

- [ ] **Step 5: LLM-Call mit `disable_thinking`**

```python
        content = call_ollama(
            prompt,
            model=model,
            base_url=base_url,
            temperature=0.3,
            num_predict=32768,
            timeout=300,
            disable_thinking=True,
        )
```

- [ ] **Step 6: Node anpassen**

In `app/nodes/plan_photobook_node.py`:

```python
def plan_photobook_node(state: AppState) -> AppState:
    logger.info("Plane Fotobuch-Layout (LLM Pass 1)...")
    if not state.photobook_images:
        logger.warning("Keine Bilder fuer Fotobuch-Planung vorhanden.")
        return state
    gpx_dict, preset = _get_photobook_context(state)
    try:
        plan = plan_photobook_layout(
            images=state.photobook_images,
            gpx_stats=gpx_dict,
            tour_summary=state.tour_summary,
            model=state.model,
            page_range=state.output_config.photobook.page_range,
            preset=preset,
        )
        state.photobook_plan = plan
        logger.info("Layout-Planung abgeschlossen: %s Seiten geplant.", len(plan.pages))
    except Exception as e:
        logger.error("Fotobuch-Planung fehlgeschlagen: %s", e)
        from app.state import PhotobookPlan
        state.photobook_plan = PhotobookPlan(pages=[])
    return state
```

- [ ] **Step 7: Tests verifizieren**

Run: `uv run pytest tests/test_photobook/test_plan.py -v`
Expected: Tests müssen ggf. angepasst werden (Signatur-Änderung). Bei Mock-Tests einfach neuen Parameter `tour_summary="Test"` ergänzen.

- [ ] **Step 8: Commit**

```bash
git add app/photobook/plan.py app/nodes/plan_photobook_node.py
git commit -m "feat: use tour_summary in layout planner, reduce context, disable thinking"
```

---

### Task 9: generate.py — Helper-Funktionen + Tests

**Files:**
- Modify: `app/photobook/generate.py`
- Modify: `tests/test_photobook/test_generate.py`

- [ ] **Step 1: Schreibe Tests für die drei Helper-Funktionen**

Füge zu `tests/test_photobook/test_generate.py` hinzu:

```python
from app.photobook.generate import _split_into_batches, _images_for_batch, calculate_num_predict
from app.state import PagePlan

SAMPLE_PAGES_16 = [
    PagePlan(position=i, preset_id="single_text_below", image_indices=[i], purpose=f"Seite {i}")
    for i in range(16)
]
SAMPLE_PAGES_16[0] = PagePlan(position=0, preset_id="cover_hero", image_indices=[0], purpose="Cover")


class TestBatchHelpers:
    def test_split_into_batches_exact(self):
        batches = _split_into_batches(SAMPLE_PAGES_16, batch_size=3)
        assert len(batches) == 6
        assert len(batches[0]) == 3
        assert len(batches[-1]) == 1  # 16 % 3 = 1 letzter Batch

    def test_split_first_batch_has_cover(self):
        batches = _split_into_batches(SAMPLE_PAGES_16, batch_size=3)
        assert batches[0][0].preset_id == "cover_hero"
        assert batches[0][0].position == 0

    def test_split_single_batch(self):
        pages = SAMPLE_PAGES_16[:2]
        batches = _split_into_batches(pages, batch_size=3)
        assert len(batches) == 1
        assert len(batches[0]) == 2

    def test_images_for_batch_extracts_correct_images(self):
        batch_pages = [
            PagePlan(position=0, preset_id="cover_hero", image_indices=[0]),
            PagePlan(position=1, preset_id="double_stacked", image_indices=[1, 2]),
            PagePlan(position=2, preset_id="single_text_below", image_indices=[3]),
        ]
        all_images = [ImageData(path=f"/tmp/img_{i}.jpg") for i in range(10)]
        result = _images_for_batch(batch_pages, all_images)
        assert len(result) == 4  # Indices 0, 1, 2, 3
        assert result[0].path == "/tmp/img_0.jpg"
        assert result[3].path == "/tmp/img_3.jpg"

    def test_images_for_batch_deduplicates(self):
        batch_pages = [
            PagePlan(position=0, preset_id="cover_hero", image_indices=[0]),
            PagePlan(position=1, preset_id="double_stacked", image_indices=[0, 1]),  # Index 0 doppelt
        ]
        all_images = [ImageData(path=f"/tmp/img_{i}.jpg") for i in range(5)]
        result = _images_for_batch(batch_pages, all_images)
        assert len(result) == 2  # Indices 0, 1 (dedupliziert)

    def test_images_for_batch_empty(self):
        result = _images_for_batch([], [])
        assert result == []


class TestCalculateNumPredict:
    def test_returns_minimum_for_small_batch(self):
        pages = [PagePlan(position=0, preset_id="cover_hero", image_indices=[0])]
        result = calculate_num_predict(pages, min_tokens=8192)
        assert result >= 8192

    def test_scales_with_text_slots(self):
        # Drei Seiten mit je 1400 char caption
        pages = [
            PagePlan(position=i, preset_id="single_text_below", image_indices=[i])
            for i in range(3)
        ]
        result = calculate_num_predict(pages, min_tokens=8192)
        assert result >= 8192
        # 4200 chars / 2.5 = 1680 tokens + 2000 overhead = 3680 * 1.5 = 5520 → capped at 8192
        assert result >= 5500

    def test_no_text_presets_return_minimum(self):
        pages = [
            PagePlan(position=i, preset_id="double_stacked", image_indices=[i, i+1])
            for i in range(3)
        ]
        result = calculate_num_predict(pages, min_tokens=8192)
        assert result == 8192  # Keine Text-Slots → Minimum
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_photobook/test_generate.py::TestBatchHelpers tests/test_photobook/test_generate.py::TestCalculateNumPredict -v`
Expected: FAIL — ImportError (Funktionen noch nicht definiert).

- [ ] **Step 3: Implementiere die Helper-Funktionen**

Füge in `app/photobook/generate.py` vor `generate_photobook_pages` ein (nach den Imports, vor Zeile 20):

```python
from app.config import PHOTOBOOK_BATCH_SIZE
from app.photobook.presets import get_preset_text_ranges

def _split_into_batches(pages: List[PagePlan], batch_size: int) -> List[List[PagePlan]]:
    """Teilt Seiten chronologisch in Batches. Cover (position=0) immer in Batch 0."""
    return [pages[i:i + batch_size] for i in range(0, len(pages), batch_size)]


def _images_for_batch(batch_pages: List[PagePlan], all_images: List[ImageData]) -> List[ImageData]:
    """Ermittelt die Menge der im Batch referenzierten Bilder (dedupliziert, sortiert)."""
    used_indices: set[int] = set()
    for page in batch_pages:
        used_indices.update(page.image_indices)
    return [all_images[i] for i in sorted(used_indices) if 0 <= i < len(all_images)]


def calculate_num_predict(
    batch_pages: List[PagePlan],
    safety_factor: float = 1.5,
    min_tokens: int = 8192,
) -> int:
    """Berechnet num_predict aus der Summe der char_limits aller Text-Slots im Batch."""
    max_chars = 0
    for page in batch_pages:
        text_ranges = get_preset_text_ranges(page.preset_id)
        for slot_id, (ch_min, ch_max) in text_ranges.items():
            max_chars += ch_max
    text_tokens = max_chars / 2.5
    json_overhead = 2000
    return max(min_tokens, int((text_tokens + json_overhead) * safety_factor))
```

*Wichtig:* Die `get_preset_text_ranges` Funktion returned ein Dict `{slot_id: (char_min, char_limit)}`. Stelle sicher, dass die Funktion auch mit unbekannten `preset_id` umgehen kann (sollte keine Exception werfen).

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_photobook/test_generate.py::TestBatchHelpers tests/test_photobook/test_generate.py::TestCalculateNumPredict -v`
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add app/photobook/generate.py tests/test_photobook/test_generate.py
git commit -m "feat: add batch helper functions and tests (split, images_for_batch, num_predict)"
```

---

### Task 10: generate.py — Batch-Prompt-Konstruktion + Tests

**Files:**
- Modify: `app/photobook/generate.py`
- Modify: `tests/test_photobook/test_generate.py`

- [ ] **Step 1: Schreibe Tests für `_build_batch_prompt`**

Füge zu `tests/test_photobook/test_generate.py` hinzu:

```python
from app.photobook.generate import _build_batch_prompt


class TestBuildBatchPrompt:
    def test_includes_tour_summary(self):
        batch_pages = [PagePlan(position=0, preset_id="cover_hero", image_indices=[0])]
        prompt = _build_batch_prompt(batch_pages, "Wanderung im Allgäu, Herbst.", "14.3", "520")
        assert "Wanderung im Allgäu" in prompt
        assert "14.3" in prompt
        assert "520" in prompt

    def test_includes_only_relevant_presets(self):
        batch_pages = [
            PagePlan(position=0, preset_id="cover_hero", image_indices=[0]),
            PagePlan(position=1, preset_id="single_text_below", image_indices=[1]),
        ]
        prompt = _build_batch_prompt(batch_pages, "Test-Tour", "10.0", "300")
        assert "cover_hero" in prompt
        assert "single_text_below" in prompt
        # double_stacked sollte NICHT vorkommen
        assert "double_stacked" not in prompt or "double_stacked" not in prompt.split(":")[0]

    def test_includes_batch_plan_json(self):
        batch_pages = [
            PagePlan(position=0, preset_id="cover_hero", image_indices=[0], purpose="Cover"),
        ]
        prompt = _build_batch_prompt(batch_pages, "Test", "5.0", "100")
        assert "cover_hero" in prompt
        assert "Cover" in prompt

    def test_handles_empty_summary(self):
        batch_pages = [PagePlan(position=0, preset_id="cover_hero", image_indices=[0])]
        prompt = _build_batch_prompt(batch_pages, None, None, None)
        # Sollte nicht crashen
        assert "cover_hero" in prompt
```

- [ ] **Step 2: Implementiere `_build_batch_prompt`**

Füge in `app/photobook/generate.py` nach den Helper-Funktionen ein:

```python
# ── Batch Prompt Template ──

BATCH_PROMPT_TEMPLATE = """Du befuellst die Slots der gewaehlten Presets mit Bildern und Text.

TOUR: {tour_summary}
TOURDATEN: {gpx_text}

SEITENPLAN (nur dieser Batch):
{plan_text}

VERWENDETE PRESETS (nur diese sind relevant):
{catalog}

AUFGABE PRO SEITE:{style_block}
1. Weise jedem Image-Slot ein Bild zu (image_index aus dem Plan).
2. TEXT-PFLICHT: Jeder in der Preset-Liste oben als "text" markierte Slot (title, caption, intro, ...) MUSS einen nicht-leeren text-Wert bekommen. Lass KEINEN Text-Slot leer. Ein Preset OHNE Text-Slots (Text=nein) braucht natuerlich keinen Text.
3. Textdimensionen: title max. 60 Zeichen. caption und intro: char_max siehe Preset-Liste oben ([min-maxZ]) — ueberschreite NIEMALS char_max. Die char_min-Angabe ist eine Empfehlung fuer ausfuehrlichen Text, keine harte Pflicht.
4. Generiere AUSFUEHRLICHE, lebendige Texte — beschreibe Landschaft, Stimmung, Farben, Details, Wetter. Je mehr Details desto besser.
{title_instruction}{multi_image_instruction}

VOR DER AUSGABE PRUEFEN:
- Hat JEDE Seite einen title-Slot mit nicht-leerem Text?
- Hat JEDE Seite fuer ALLE im Preset vorhandenen Text-Slots (caption, intro, ...) einen nicht-leeren text-Eintrag?
- Sind alle char_min/char_max eingehalten?

BEISPIELE:
- cover_hero: [{{"preset_id": "cover_hero", "slots": [{{"slot_id": "title", "text": "Aufbruch im Morgengrauen"}}, {{"slot_id": "main", "image_index": 0}}]}}]
- single_text_below: [{{"preset_id": "single_text_below", "slots": [{{"slot_id": "title", "text": "Alpenwiese"}}, {{"slot_id": "main", "image_index": 1}}, {{"slot_id": "caption", "text": "Ein atemberaubender Weitblick ueber das Tal..."}}]}}]"""


def _build_batch_prompt(
    batch_pages: List[PagePlan],
    tour_summary: Optional[str],
    gpx_distance: Optional[str],
    gpx_elevation: Optional[str],
    preset: Optional[PhotobookPreset] = None,
) -> str:
    if preset is None:
        preset = get_photobook_preset("mixed")

    # Nur die tatsächlich im Batch verwendeten Presets laden
    all_presets = load_all_presets()
    used_preset_ids = set()
    for pp in batch_pages:
        if pp.preset_id:
            used_preset_ids.add(pp.preset_id)

    # Nur relevante Presets anzeigen (mit Char-Ranges fuer Text-Slots)
    preset_summary = []
    for pid in sorted(used_preset_ids):
        p = all_presets.get(pid)
        if p:
            text_ranges = get_preset_text_ranges(pid)
            slot_info_parts = []
            for s in p.slots:
                slot_label = f"{s.id}({s.type},{s.text_role or s.priority or '-'})"
                if s.id in text_ranges:
                    ch_min, ch_max = text_ranges[s.id]
                    slot_label += f"[{ch_min}-{ch_max}Z]"
                slot_info_parts.append(slot_label)
            slot_info = ", ".join(slot_info_parts)
            preset_summary.append(f"  {pid} [{p.image_count} Bilder, Text={'ja' if p.has_text else 'nein'}]: {slot_info}")
    catalog = "\n".join(preset_summary)

    # Seitenplan serialisieren
    serializable_pages = [pp.model_dump() for pp in batch_pages]
    plan_text = json.dumps(serializable_pages, indent=2, ensure_ascii=False)

    # GPX-Text
    gpx_text = ""
    if gpx_distance and gpx_elevation:
        gpx_text = f"{gpx_distance} km, {gpx_elevation}m Hoehenmeter."
    elif gpx_distance:
        gpx_text = f"{gpx_distance} km."
    else:
        gpx_text = "Keine Daten."

    # Tour-Summary
    summary = tour_summary if tour_summary else "Keine Zusammenfassung verfuegbar."

    # Style-Block
    style_block = ""
    if preset.generation_instructions:
        style_block = f"\nSTILVORGABE ({preset.name}): {preset.generation_instructions}\n"

    title_instruction = "5. JEDE Seite MUSS einen title-Slot haben: " + '{"slot_id": "title", "text": "Einzeiliger Seitentitel"}' if preset.text_enabled else ""
    multi_image_instruction = "\n6. Bei Presets mit MEHREREN Bildern (quad_grid, double_stacked, triple_stacked): beschreibe den Gesamteindruck der Bildgruppe, nicht nur ein einzelnes Bild." if preset.text_enabled else ""

    return BATCH_PROMPT_TEMPLATE.format(
        tour_summary=summary,
        gpx_text=gpx_text,
        plan_text=plan_text,
        catalog=catalog,
        style_block=style_block,
        title_instruction=title_instruction,
        multi_image_instruction=multi_image_instruction,
    )
```

*Hinweis:* Die alte `GENERATE_PROMPT_TEMPLATE` und `_build_generate_prompt` bleiben zunächst erhalten (werden in Task 12 endgültig durch die neue `generate_photobook_pages` ersetzt). Der Klarheit halber: Die alte `_build_generate_prompt` soll als Fallback-Code verbleiben, bis die neue Batch-Pipeline vollständig ist.

- [ ] **Step 3: Run tests**

Run: `uv run pytest tests/test_photobook/test_generate.py::TestBuildBatchPrompt -v`
Expected: 4 passed. Wenn Presets geladen werden müssen, kann der Test-Verzeichnis-Import Probleme machen — ggf. `uv run pytest tests/test_photobook/test_generate.py::TestBuildBatchPrompt -v -s` verwenden.

- [ ] **Step 4: Commit**

```bash
git add app/photobook/generate.py tests/test_photobook/test_generate.py
git commit -m "feat: add batch prompt construction with tour_summary and filtered presets"
```

---

### Task 11: generate.py — Batch-Validierung + Fallback + Tests

**Files:**
- Modify: `app/photobook/generate.py`
- Modify: `tests/test_photobook/test_generate.py`

- [ ] **Step 1: Schreibe Tests für Validierung und Fallback**

Füge zu `tests/test_photobook/test_generate.py` hinzu:

```python
from app.photobook.generate import _validate_batch_result, _generate_fallback_for_batch


class TestValidateBatchResult:
    def test_valid_result_passes(self):
        batch_pages = [PagePlan(position=0, preset_id="cover_hero", image_indices=[0])]
        result_json = [{"preset_id": "cover_hero", "slots": [
            {"slot_id": "main", "image_index": 0},
            {"slot_id": "title", "text": "Cover"},
        ]}]
        ok, msg = _validate_batch_result(result_json, batch_pages)
        assert ok
        assert msg is None

    def test_missing_title_fails(self):
        batch_pages = [PagePlan(position=0, preset_id="cover_hero", image_indices=[0])]
        result_json = [{"preset_id": "cover_hero", "slots": [
            {"slot_id": "main", "image_index": 0},
        ]}]
        ok, msg = _validate_batch_result(result_json, batch_pages)
        assert not ok

    def test_wrong_page_count_fails(self):
        batch_pages = [PagePlan(position=0, preset_id="cover_hero", image_indices=[0])]
        result_json = []  # Empty, should have 1 page
        ok, msg = _validate_batch_result(result_json, batch_pages)
        assert not ok

    def test_empty_text_slot_fails(self):
        batch_pages = [PagePlan(position=0, preset_id="single_text_below", image_indices=[0])]
        result_json = [{"preset_id": "single_text_below", "slots": [
            {"slot_id": "main", "image_index": 0},
            {"slot_id": "title", "text": "Seite"},
            {"slot_id": "caption", "text": ""},  # Leerer Text-Slot
        ]}]
        ok, msg = _validate_batch_result(result_json, batch_pages)
        assert not ok


class TestFallbackForBatch:
    def test_generates_correct_page_count(self):
        batch_pages = [
            PagePlan(position=0, preset_id="cover_hero", image_indices=[0]),
            PagePlan(position=1, preset_id="single_text_below", image_indices=[1]),
        ]
        batch_images = [ImageData(path=f"/tmp/img_{i}.jpg") for i in range(2)]
        result = _generate_fallback_for_batch(batch_pages, batch_images)
        assert len(result) == 2
        assert result[0].template_id == "cover_hero"
        assert result[1].template_id == "single_text_below"

    def test_fallback_has_titles(self):
        batch_pages = [PagePlan(position=0, preset_id="cover_hero", image_indices=[0], purpose="MeinCover")]
        batch_images = [ImageData(path="/tmp/img_0.jpg")]
        result = _generate_fallback_for_batch(batch_pages, batch_images)
        assert len(result) == 1
        title_slot = next((s for s in result[0].slots if s.slot_id == "title"), None)
        assert title_slot is not None
        assert len(title_slot.text) > 0

    def test_fallback_unknown_preset(self):
        batch_pages = [PagePlan(position=0, preset_id="nonexistent", image_indices=[0, 1])]
        batch_images = [ImageData(path=f"/tmp/img_{i}.jpg") for i in range(2)]
        result = _generate_fallback_for_batch(batch_pages, batch_images)
        assert len(result) == 1
        # Sollte ein passendes Preset (2 Bilder) wählen
        from app.photobook.preset_loader import load_preset
        preset = load_preset(result[0].template_id)
        assert preset.image_count == 2
```

- [ ] **Step 2: Implementiere `_validate_batch_result` und `_generate_fallback_for_batch`**

Füge in `app/photobook/generate.py` nach `_build_batch_prompt` ein:

```python
def _validate_batch_result(
    result_json: list,
    batch_pages: List[PagePlan],
) -> tuple:
    """Validiert ein Batch-Ergebnis. Returns (ok: bool, error_message: Optional[str])."""
    if not isinstance(result_json, list):
        return False, "Kein JSON-Array"

    if len(result_json) != len(batch_pages):
        return False, f"Seitenanzahl ({len(result_json)}) != erwartet ({len(batch_pages)})"

    all_presets = load_all_presets()
    for i, page_data in enumerate(result_json):
        if not isinstance(page_data, dict):
            return False, f"Seite {i}: Kein Dictionary"
        preset_id = page_data.get("preset_id", "")
        preset = all_presets.get(preset_id)
        if not preset:
            return False, f"Seite {i}: Unbekanntes Preset '{preset_id}'"
        slots = page_data.get("slots", [])
        slot_map = {s.get("slot_id", ""): s for s in slots}

        # Jede Seite braucht einen title-Slot mit nicht-leerem Text
        title_slot = slot_map.get("title")
        if not title_slot or not title_slot.get("text", "").strip():
            return False, f"Seite {i}: Fehlender oder leerer title-Slot"

        # Alle Text-Slots des Presets prüfen
        for ps in preset.slots:
            if ps.type == "text":
                slot = slot_map.get(ps.id)
                if not slot:
                    return False, f"Seite {i}: Fehlender Text-Slot '{ps.id}'"
                if not slot.get("text", "").strip():
                    return False, f"Seite {i}: Leerer Text-Slot '{ps.id}'"

    return True, None


def _generate_fallback_for_batch(
    batch_pages: List[PagePlan],
    batch_images: List[ImageData],
) -> List[PageDescription]:
    """Generiert Fallback-Seiten fuer einen Batch (analog zur globalen Fallback-Logik)."""
    all_presets = load_all_presets()
    fallback = []
    for plan_page in batch_pages:
        preset_id = plan_page.preset_id or "quad_grid"
        preset = all_presets.get(preset_id)
        if preset is None:
            count = len(plan_page.image_indices)
            preset_id = get_any_preset(count)
            preset = all_presets.get(preset_id, all_presets["quad_grid"])

        indices = plan_page.image_indices
        image_slots = [s.id for s in preset.slots if s.type == "image"]
        slots = []
        for sid, idx in zip(image_slots, indices):
            if 0 <= idx < len(batch_images):
                slots.append({"slot_id": sid, "image_index": idx})

        purpose = plan_page.purpose
        position = plan_page.position
        if purpose and purpose.lower() not in ("cover", "einzelbild", "sammlung", "sequenz", "vergleich"):
            title = purpose[:60]
        elif position == 0:
            title = "Fotobuch"
        else:
            title = f"Seite {position + 1}"
        slots.append({"slot_id": "title", "text": title})

        for s in preset.slots:
            if s.type == "text" and s.text_role != "title":
                img_indices_str = ", ".join(str(i) for i in indices[:2])
                slot_text = f"Foto {img_indices_str} — Eindrücke der Tour"
                if s.char_limit and len(slot_text) > s.char_limit:
                    slot_text = slot_text[:s.char_limit]
                slots.append({"slot_id": s.id, "text": slot_text})

        fallback.append(PageDescription(
            template_id=preset_id,
            page_type="single",
            slots=[PageSlot(**s) for s in slots],
        ))
    return fallback
```

- [ ] **Step 3: Run tests**

Run: `uv run pytest tests/test_photobook/test_generate.py::TestValidateBatchResult tests/test_photobook/test_generate.py::TestFallbackForBatch -v`
Expected: 7 passed (3 validation + 3 fallback + 1 existing).

- [ ] **Step 4: Commit**

```bash
git add app/photobook/generate.py tests/test_photobook/test_generate.py
git commit -m "feat: add batch validation and per-batch fallback generation"
```

---

### Task 12: generate.py — Merge + Hauptfunktion + Tests

**Files:**
- Modify: `app/photobook/generate.py`
- Modify: `tests/test_photobook/test_generate.py`

- [ ] **Step 1: Schreibe Tests für `_merge_batch_results` und `generate_photobook_pages` (Batch-Modus)**

Füge zu `tests/test_photobook/test_generate.py` hinzu:

```python
from app.photobook.generate import _merge_batch_results

MOCK_BATCH_CONTENT_1 = json.dumps([
    {"preset_id": "cover_hero", "slots": [
        {"slot_id": "main", "image_index": 0},
        {"slot_id": "title", "text": "Cover"},
    ]},
    {"preset_id": "single_text_below", "slots": [
        {"slot_id": "main", "image_index": 1},
        {"slot_id": "title", "text": "Erste Etappe"},
        {"slot_id": "caption", "text": "Ein wunderschöner Morgen."},
    ]},
    {"preset_id": "double_stacked_text", "slots": [
        {"slot_id": "top", "image_index": 2},
        {"slot_id": "bottom", "image_index": 3},
        {"slot_id": "title", "text": "Aufstieg"},
        {"slot_id": "caption", "text": "Der steile Pfad durch den Wald."},
    ]},
])

MOCK_BATCH_CONTENT_2 = json.dumps([
    {"preset_id": "single_text_below", "slots": [
        {"slot_id": "main", "image_index": 4},
        {"slot_id": "title", "text": "Gipfel"},
        {"slot_id": "caption", "text": "Endlich oben angekommen."},
    ]},
    {"preset_id": "single_text_below", "slots": [
        {"slot_id": "main", "image_index": 5},
        {"slot_id": "title", "text": "Abstieg"},
        {"slot_id": "caption", "text": "Gemütlich zurück ins Tal."},
    ]},
])


class TestMergeBatchResults:
    def test_merges_two_batches(self):
        results = [
            json.loads(MOCK_BATCH_CONTENT_1),
            json.loads(MOCK_BATCH_CONTENT_2),
        ]
        merged = _merge_batch_results(results)
        assert len(merged) == 5

    def test_merge_empty_returns_empty(self):
        assert _merge_batch_results([]) == []

    def test_merge_single_batch(self):
        results = [json.loads(MOCK_BATCH_CONTENT_1)]
        merged = _merge_batch_results(results)
        assert len(merged) == 3


class TestBatchGenerateIntegration:
    @patch("app.photobook.generate.call_ollama")
    def test_batch_pipeline_produces_all_pages(self, mock_call):
        """Integrationstest: Batch-Pipeline generiert alle Seiten."""
        plan = PhotobookPlan(pages=[
            PagePlan(position=0, preset_id="cover_hero", image_indices=[0], purpose="Cover"),
            PagePlan(position=1, preset_id="single_text_below", image_indices=[1], purpose="Start"),
            PagePlan(position=2, preset_id="single_text_below", image_indices=[2], purpose="Ende"),
        ])
        images = [ImageData(path=f"/tmp/img_{i}.jpg") for i in range(3)]

        # Simuliere LLM-Antwort für den einen Batch
        mock_call.return_value = json.dumps([
            {"preset_id": "cover_hero", "slots": [
                {"slot_id": "main", "image_index": 0},
                {"slot_id": "title", "text": "Cover"},
            ]},
            {"preset_id": "single_text_below", "slots": [
                {"slot_id": "main", "image_index": 1},
                {"slot_id": "title", "text": "Start"},
                {"slot_id": "caption", "text": "Los geht's."},
            ]},
            {"preset_id": "single_text_below", "slots": [
                {"slot_id": "main", "image_index": 2},
                {"slot_id": "title", "text": "Ende"},
                {"slot_id": "caption", "text": "Geschafft."},
            ]},
        ])

        result = generate_photobook_pages(
            plan=plan,
            images=images,
            tour_summary="Test-Tour",
            gpx_distance="5.0",
            gpx_elevation="100",
            model="test-model",
            batch_size=3,
        )
        assert len(result) == 3
        assert all(isinstance(p, PageDescription) for p in result)

    @patch("app.photobook.generate.call_ollama")
    def test_batch_fallback_on_llm_error(self, mock_call):
        """Wenn LLM fehlschlägt, greift der Batch-Fallback."""
        mock_call.return_value = None
        plan = PhotobookPlan(pages=[
            PagePlan(position=0, preset_id="cover_hero", image_indices=[0], purpose="Cover"),
            PagePlan(position=1, preset_id="single_text_below", image_indices=[1], purpose="Bild"),
        ])
        images = [ImageData(path=f"/tmp/img_{i}.jpg") for i in range(2)]

        result = generate_photobook_pages(
            plan=plan,
            images=images,
            tour_summary="Test-Tour",
            gpx_distance="5.0",
            gpx_elevation="100",
            model="test-model",
            batch_size=3,
        )
        assert len(result) == 2
        # Fallback-Titel sollten gesetzt sein
        title_slots = [s for p in result for s in p.slots if s.slot_id == "title"]
        assert len(title_slots) == 2
        assert all(s.text and len(s.text) > 0 for s in title_slots)
```

- [ ] **Step 2: Implementiere `_merge_batch_results` und die neue `generate_photobook_pages`**

Ersetze die existierende `generate_photobook_pages` Funktion in `app/photobook/generate.py`:

```python
def _merge_batch_results(all_results: List[list]) -> List[PageDescription]:
    """Deterministisches Mergen aller Batch-Ergebnisse zu PageDescriptions."""
    merged = []
    for batch_result in all_results:
        for pd in batch_result:
            valid_slots = []
            for slot in pd.get("slots", []):
                idx = slot.get("image_index", -1)
                if idx >= 0:
                    valid_slots.append(slot)
                else:
                    cleansed = {k: v for k, v in slot.items() if k != "image_index"}
                    if cleansed.get("text") or cleansed.get("slot_id"):
                        valid_slots.append(cleansed)
            # Dedupliziere Slots
            deduped = []
            seen = set()
            for s in reversed(valid_slots):
                sid = s.get("slot_id", "")
                if sid not in seen:
                    seen.add(sid)
                    deduped.append(s)
            deduped.reverse()
            page_slots = [PageSlot(**s) for s in deduped]
            page = PageDescription(
                template_id=pd.get("preset_id", "quad_grid"),
                page_type="single",
                slots=page_slots,
            )
            merged.append(page)
    return merged


def generate_photobook_pages(
    plan: PhotobookPlan,
    images: List[ImageData],
    tour_summary: Optional[str] = None,
    gpx_distance: Optional[str] = None,
    gpx_elevation: Optional[str] = None,
    model: str = "gemma4:26b-ctx128k",
    base_url: str = OLLAMA_BASE_URL,
    preset: Optional[PhotobookPreset] = None,
    batch_size: int = PHOTOBOOK_BATCH_SIZE,
) -> List[PageDescription]:
    if preset is None:
        preset = get_photobook_preset("mixed")
    pages_plan = plan.pages
    if not pages_plan:
        return []

    # Seiten in Batches aufteilen
    batches = _split_into_batches(pages_plan, batch_size)
    logger.info("Generiere %s Seiten in %s Batches (batch_size=%s)...", len(pages_plan), len(batches), batch_size)

    all_results = []
    for batch_idx, batch_pages in enumerate(batches):
        logger.info("Batch %s/%s: %s Seiten", batch_idx + 1, len(batches), len(batch_pages))
        batch_images = _images_for_batch(batch_pages, images)

        # Prompt bauen
        prompt = _build_batch_prompt(
            batch_pages,
            tour_summary,
            gpx_distance,
            gpx_elevation,
            preset=preset,
        )

        # Bilder für diesen Batch encodieren
        encoded_images = []
        for img in batch_images:
            b64 = encode_image_base64(img.path)
            if b64:
                encoded_images.append(b64)

        # num_predict dynamisch berechnen
        num_pred = calculate_num_predict(batch_pages)

        # LLM-Call mit Retry
        batch_result = None
        for attempt in range(2):
            try:
                content = call_ollama(
                    prompt,
                    model=model,
                    base_url=base_url,
                    images=encoded_images,
                    temperature=0.3,
                    num_predict=num_pred,
                    timeout=120,
                    disable_thinking=True,
                )
                if content:
                    content = strip_thinking_tokens(content)
                    array_match = re.search(r'\[.*\]', content, re.DOTALL)
                    if array_match:
                        try:
                            pages_data = json.loads(array_match.group())
                            ok, err_msg = _validate_batch_result(pages_data, batch_pages)
                            if ok:
                                batch_result = pages_data
                                break
                            else:
                                logger.warning("Batch %s Validierung fehlgeschlagen (Versuch %s): %s", batch_idx + 1, attempt + 1, err_msg)
                        except json.JSONDecodeError as je:
                            logger.warning("Batch %s JSON-Parse-Fehler (Versuch %s): %s", batch_idx + 1, attempt + 1, je)
                    else:
                        logger.warning("Batch %s: Kein JSON-Array in LLM-Antwort (Versuch %s)", batch_idx + 1, attempt + 1)
                else:
                    logger.warning("Batch %s: Leere LLM-Antwort (Versuch %s)", batch_idx + 1, attempt + 1)
            except Exception as e:
                logger.warning("Batch %s LLM-Call fehlgeschlagen (Versuch %s): %s", batch_idx + 1, attempt + 1, e)

        if batch_result:
            all_results.append(batch_result)
        else:
            logger.warning("Batch %s: Verwende Fallback nach %s Versuchen", batch_idx + 1, 2)
            fallback = _generate_fallback_for_batch(batch_pages, batch_images)
            # Fallback als Dict-Liste formatieren für Merge
            all_results.append([{
                "preset_id": fb.template_id,
                "slots": [s.model_dump() for s in fb.slots],
            } for fb in fallback])

    return _merge_batch_results(all_results)
```

*Wichtig:* Die alte `generate_photobook_pages` und `_generate_fallback_pages` (global) können nach dem Ersetzen entfernt oder als `_generate_fallback_pages_global` umbenannt werden, falls sie noch irgendwo referenziert werden. Die alte `_build_generate_prompt` und `GENERATE_PROMPT_TEMPLATE` können ebenfalls entfernt werden.

- [ ] **Step 3: Run ALL generate tests**

Run: `uv run pytest tests/test_photobook/test_generate.py -v`
Expected: Alle neuen und existierenden Tests passen. Falls existierende Tests die alte Signatur nutzen (`gpx_stats`, `notes`), müssen sie auf die neue Signatur (`tour_summary`, `gpx_distance`, `gpx_elevation`) migriert werden.

*Hinweis:* Die existierenden Tests `TestGenerate` nutzen die alte Signatur. Da wir die Funktion ersetzt haben, müssen diese Tests aktualisiert werden:
- `test_generate_returns_page_descriptions` → `tour_summary="Test", gpx_distance="10", gpx_elevation="500"` statt `gpx_stats={}, notes="Test"`
- `test_fallback_on_empty_plan` → `tour_summary=None` statt `gpx_stats={}, notes=None`
- Usw.

- [ ] **Step 4: Aktualisiere existierende Tests auf neue Signatur**

Update `tests/test_photobook/test_generate.py` — ersetze alte Signatur-Aufrufe. Beispiel für `TestGenerate`:

```python
class TestGenerate:
    @patch("app.photobook.generate.call_ollama")
    def test_generate_returns_page_descriptions(self, mock_call):
        mock_call.return_value = MOCK_GENERATE_CONTENT
        result = generate_photobook_pages(
            plan=MOCK_PLAN, images=SAMPLE_IMAGES,
            tour_summary="Test-Tour", gpx_distance="10.0", gpx_elevation="500",
            model="test-model",
        )
        assert len(result) == 2
        # ...

    def test_fallback_on_empty_plan(self):
        result = generate_photobook_pages(
            plan=PhotobookPlan(pages=[]), images=SAMPLE_IMAGES[:4],
            tour_summary=None, model="test-model",
        )
        assert len(result) == 0
```

Aktualisiere analog alle anderen `generate_photobook_pages`-Aufrufe in diesem Test-File.

- [ ] **Step 5: Bereinige alte Templates und Funktionen**

Entferne aus `app/photobook/generate.py`:
- `GENERATE_PROMPT_TEMPLATE` (Zeilen 20-44)
- `_build_generate_prompt` (Zeilen 47-116)
- Die alte `_generate_fallback_pages` (Zeilen 247-296) — wird durch `_generate_fallback_for_batch` ersetzt

- [ ] **Step 6: Run ALL tests final**

Run: `uv run pytest tests/test_photobook/test_generate.py -v`
Expected: ALL tests pass (alte migriert + neue).

- [ ] **Step 7: Commit**

```bash
git add app/photobook/generate.py tests/test_photobook/test_generate.py
git commit -m "feat: implement batch-based page generation with merge and fallback"
```

---

### Task 13: generate_photobook_node.py — Node an neue Signatur anpassen

**Files:**
- Modify: `app/nodes/generate_photobook_node.py`

- [ ] **Step 1: Node aktualisieren**

```python
import logging

from app.state import AppState
from app.photobook.generate import generate_photobook_pages
from app.nodes.plan_photobook_node import _get_photobook_context

logger = logging.getLogger(__name__)


def generate_photobook_node(state: AppState) -> AppState:
    logger.info("Generiere Fotobuch-Seiten (LLM Pass 2, Batch-Modus)...")
    if not state.photobook_plan:
        logger.warning("Kein Layout-Plan vorhanden.")
        return state
    gpx_dict, preset = _get_photobook_context(state)

    gpx_distance = None
    gpx_elevation = None
    if gpx_dict:
        dist_m = gpx_dict.get("total_distance_m", 0)
        if dist_m:
            gpx_distance = f"{dist_m / 1000:.1f}"
        elev = gpx_dict.get("elevation_gain_m", 0)
        if elev:
            gpx_elevation = f"{elev:.0f}"

    try:
        pages = generate_photobook_pages(
            plan=state.photobook_plan,
            images=state.photobook_images,
            tour_summary=state.tour_summary,
            gpx_distance=gpx_distance,
            gpx_elevation=gpx_elevation,
            model=state.model,
            preset=preset,
        )
        state.photobook_pages = pages
        logger.info("%s Fotobuch-Seiten generiert.", len(pages))
    except Exception as e:
        logger.error("Fotobuch-Generierung fehlgeschlagen: %s", e)
        state.photobook_pages = []
    return state
```

- [ ] **Step 2: Verifiziere Import**

Run: `uv run python -c "from app.nodes.generate_photobook_node import generate_photobook_node; print('Import OK')"`
Expected: Import OK

- [ ] **Step 3: Commit**

```bash
git add app/nodes/generate_photobook_node.py
git commit -m "feat: update generate_photobook_node for batch-based generation"
```

---

### Task 14: Integration Test + Graph-Verifikation

**Files:**
- Modify: `tests/test_photobook/test_graph.py` (oder neu: `tests/test_photobook/test_pipeline_batch.py`)

- [ ] **Step 1: Schreibe Integrationstest**

Create `tests/test_photobook/test_pipeline_batch.py`:

```python
"""Integrationstest fuer die ueberarbeitete Photobook-Pipeline."""
import json
from unittest.mock import patch
import pytest
from app.state import AppState, ImageData, OutputConfig
from app.graph import build_graph

SAMPLE_IMAGES = [ImageData(path=f"/tmp/img_{i}.jpg") for i in range(20)]


@pytest.mark.integration
class TestPhotobookPipelineBatch:
    @patch("app.services.summarize_context.call_ollama")
    @patch("app.photobook.image_selector.call_ollama")
    @patch("app.photobook.plan.call_ollama")
    @patch("app.photobook.generate.call_ollama")
    @patch("app.services.gpx_analytics.analyze_track")
    def test_full_photobook_pipeline_with_mocks(
        self, mock_gpx, mock_generate, mock_plan, mock_selector, mock_summary,
        tmp_path,
    ):
        """End-to-End: Photobook-Pipeline mit gemockten LLM-Calls."""
        # Mock GPX-Analyse
        from app.services.gpx_analytics import GPXStats
        mock_gpx.return_value = GPXStats(
            total_distance_m=14300, elevation_gain_m=520,
            moving_time_s=14400, total_time_s=18000,
            start_time="2024-10-15T08:00:00",
        )

        # Mock Summary
        mock_summary.return_value = "14.3km Wanderung im Herbst."

        # Mock Image Selector (gibt erste N Bilder-Indices zurück)
        def mock_select_call(prompt, **kwargs):
            return "0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15"
        mock_selector.side_effect = mock_select_call

        # Mock Plan (gibt einfachen Plan zurück)
        plan_response = json.dumps({
            "pages": [
                {"position": i, "preset_id": "single_text_below", "image_indices": [i], "purpose": f"Seite {i}"}
                for i in range(16)
            ],
            "dramatic_arc": "Einfache chronologische Abfolge",
        })
        # Ersetze cover_hero
        plan_data = json.loads(plan_response)
        plan_data["pages"][0]["preset_id"] = "cover_hero"
        plan_data["pages"][0]["purpose"] = "Cover"
        mock_plan.return_value = json.dumps(plan_data)

        # Mock Generate (gibt einfache Seiten zurück)
        def mock_generate_call(prompt, **kwargs):
            # Extrahiere Seiten aus dem Prompt
            return json.dumps([
                {"preset_id": "single_text_below", "slots": [
                    {"slot_id": "main", "image_index": i},
                    {"slot_id": "title", "text": f"Seite {i}"},
                    {"slot_id": "caption", "text": f"Beschreibung Seite {i}."},
                ]}
                for i in range(3)  # Batch-Grösse = 3
            ])
        mock_generate.side_effect = mock_generate_call

        # GPX-Datei erstellen
        gpx_file = tmp_path / "test_tour.gpx"
        gpx_file.write_text("""<?xml version="1.0"?>
<gpx version="1.1"><trk><trkseg>
<trkpt lat="47.5" lon="10.5"><ele>800</ele><time>2024-10-15T08:00:00Z</time></trkpt>
<trkpt lat="47.6" lon="10.6"><ele>1320</ele><time>2024-10-15T12:00:00Z</time></trkpt>
</trkseg></trk></gpx>""")

        state = AppState(
            images=SAMPLE_IMAGES[:16],
            gpx_file=str(gpx_file),
            notes="Herbstliche Bergtour im Allgäu.",
            model="test-model",
            output_config=OutputConfig(mode="photobook", photobook_preset="nature_outdoor"),
        )

        graph = build_graph()
        result = graph.invoke(state)

        # Verifikation
        assert result["tour_summary"] is not None
        assert len(result["tour_summary"]) > 0
        assert len(result["photobook_images"]) > 0
        # photobook_plan und photobook_pages werden nur gesetzt wenn genug Bilder da sind
        # Bei 16 Bildern sollte der Plan funktionieren
```

- [ ] **Step 2: Run Integrationstest**

Run: `uv run pytest tests/test_photobook/test_pipeline_batch.py -v -m integration`
Expected: 1 passed (falls Integrationstests laufen). Hinweis: Der Test mockt `call_ollama` auf Modulebene, was in `generate.py` mehrfach pro Batch aufgerufen wird. Das `side_effect` muss ggf. eine Liste sein, die genug Werte für alle Batches liefert.

- [ ] **Step 3: Verifiziere existierende Photobook-Tests**

Run: `uv run pytest tests/test_photobook/ -v`
Expected: Alle existierenden Tests passen oder wurden bereits in vorherigen Tasks angepasst.

- [ ] **Step 4: Verifiziere Blog-Pfad ist nicht gebrochen**

Run: `uv run pytest tests/test_nodes/test_generate_blogpost.py tests/test_nodes/test_enrich_weather.py -v`
Expected: Blog-bezogene Tests laufen unverändert.

- [ ] **Step 5: Commit**

```bash
git add tests/test_photobook/test_pipeline_batch.py
git commit -m "test: add integration test for batch-based photobook pipeline"
```

---

### Task 15: Final Cleanup — existierende Tests reparieren

**Files:**
- Modify: `tests/test_photobook/test_integration.py` (falls Signatur-Updates nötig)
- Modify: `tests/test_photobook/test_graph.py` (falls betroffen)

- [ ] **Step 1: Alle Tests im Worktree ausführen**

Run: `uv run pytest tests/ -v -m "not e2e" 2>&1 | tail -40`
Expected: Alle Tests passen oder nur bekannte E2E-Fehler (keine Regressionen).

- [ ] **Step 2: Fehlschlagende Tests reparieren**

Falls Tests fehlschlagen weil sie die alte Signatur von `generate_photobook_pages` oder `plan_photobook_layout` nutzen, aktualisiere sie analog zu Task 12 Step 4.

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "fix: update remaining tests for new photobook pipeline signatures"
```

---

## Test-Strategie Zusammenfassung

| Test-File | Neue Tests | Angepasste Tests |
|-----------|-----------|-----------------|
| `tests/test_services/test_summarize_context.py` | 5 unit | — |
| `tests/test_photobook/test_generate.py` | 14 unit (BatchHelpers, CalculateNumPredict, BuildBatchPrompt, ValidateBatchResult, FallbackForBatch, MergeBatchResults, BatchGenerateIntegration) | ~7 existierende Signatur-Updates |
| `tests/test_photobook/test_pipeline_batch.py` | 1 integration | — |
| `tests/test_photobook/test_image_selector.py` | — | Signatur-Prüfung (gpx_stats/notes → tour_summary) |
| `tests/test_photobook/test_plan.py` | — | Signatur-Prüfung (notes/weather/poi → tour_summary) |
| `tests/test_photobook/test_graph.py` | — | Ggf. Edge-Änderungen prüfen |

---

## Dateien Gesamt-Übersicht

| Aktion | Datei |
|--------|-------|
| CREATE | `app/services/summarize_context.py` |
| CREATE | `app/nodes/summarize_context_node.py` |
| CREATE | `tests/test_services/test_summarize_context.py` |
| CREATE | `tests/test_photobook/test_pipeline_batch.py` |
| MODIFY | `app/services/ollama_client.py` |
| MODIFY | `app/state.py` |
| MODIFY | `app/config.py` |
| MODIFY | `app/graph.py` |
| MODIFY | `app/photobook/image_selector.py` |
| MODIFY | `app/nodes/select_photobook_images_node.py` |
| MODIFY | `app/photobook/plan.py` |
| MODIFY | `app/nodes/plan_photobook_node.py` |
| MODIFY | `app/photobook/generate.py` (Hauptumbau) |
| MODIFY | `app/nodes/generate_photobook_node.py` |
| MODIFY | `tests/test_photobook/test_generate.py` |
| MODIFY | `tests/test_photobook/test_image_selector.py` (mglw.) |
| MODIFY | `tests/test_photobook/test_plan.py` (mglw.) |
