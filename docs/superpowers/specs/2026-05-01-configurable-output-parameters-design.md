# Configurable Output Parameters — Design Spec

**Date:** 2026-05-01
**Status:** Approved
**Approach:** Structured Config + Template Data (Approach 2 of 3)

## Overview

Add three user-configurable output parameters to the blog generation pipeline:

1. **Wildcard photo count** — user sets max N; algorithm picks 1.5×N; reviewer discards ≥33% to arrive at ≤N
2. **Article length presets** — short (300–650 W.), normal (650–1300 W.), detailed (1300–2500 W.)
3. **Style / Persona** — "Mountain Veteran" (first-person) and "Field Reporter" (third-person)

Configuration flows: Frontend → API → AppState → Services.

---

## 1. Configuration Data Model

### New file: `app/config.py`

Two constants dictating available presets. No logic — pure data.

```python
LENGTH_PRESETS = {
    "short":    {"label": "Kurz",       "min_words": 300,  "max_words": 650},
    "normal":   {"label": "Normal",     "min_words": 650,  "max_words": 1300},
    "detailed": {"label": "Ausführlich", "min_words": 1300, "max_words": 2500},
}

PERSONAS = {
    "mountain_veteran": {
        "label": "Mountain Veteran",
        "perspective": "first-person",
        "prompt": (
            "STIL & PERSONA: Du schreibst als erfahrener Outdoor-Mensch Ende 40 "
            "mit ca. 20 Jahren Erfahrung im Ski-Tourengehen, alpinen Klettern, "
            "Höhenbergsteigen, Langstreckentrekking (Lappland, Altai, Nepal, Peru) "
            "und Bikepacking (Straße + MTB). Du bist athletisch topfit, liebst "
            "Outdoor-Herausforderungen und hast einen nüchternen, direkten Ton. "
            "Weder harte Abfahrten noch Whiteout-Bedingungen schrecken dich — "
            "im wörtlichen wie im übertragenen Sinn. Schreibe in der Ich-Perspektive, "
            "sachlich, kompetent, ohne Übertreibungen. Deine Leser vertrauen deinem "
            "Urteil, weil du weisst, wovon du sprichst."
        ),
    },
    "field_reporter": {
        "label": "Field Reporter",
        "perspective": "third-person",
        "prompt": (
            "STIL & PERSONA: Du schreibst als objektiver Feldforscher mit einem "
            "Auge fürs Wesentliche. Sachlicher, faktenbasierter Ton mit gelegentlichem "
            "trockenem Humor. Der Artikel soll so lesbar sein, dass man ihn "
            "guten Gewissens der Schwiegermutter weiterleiten oder den Chef in CC "
            "setzen kann. Lesbar, professionell, kein übertriebenes Pathos. "
            "Schreibe in der dritten Person ('man', 'der Wanderer', 'die Gruppe')."
        ),
    },
}
```

### Changes to `app/state.py`

```python
from typing import Literal

class OutputConfig(BaseModel):
    wildcard_max: int = 12
    article_length: Literal["short", "normal", "detailed"] = "normal"
    style_persona: Literal["mountain_veteran", "field_reporter"] = "mountain_veteran"

class AppState(BaseModel):
    # ... existing fields ...
    output_config: OutputConfig = OutputConfig()
```

All fields have defaults — the CLI path (`run_pipeline()`) continues to work without user input.

---

## 2. API Layer

### Changes to `app/api/routes.py`

`RunPipelineRequest` gains three fields:

```python
class RunPipelineRequest(BaseModel):
    model: str
    output_dir: str = "output"
    notes: str = ""
    gpx_file: str = ""
    image_files: list[str] = []
    wildcard_max: int = 12
    article_length: str = "normal"
    style_persona: str = "mountain_veteran"
```

`_run_pipeline_in_background` constructs `AppState` including the config:

```python
state = AppState(
    gpx_file=gpx_file,
    model=model,
    notes=notes if notes else None,
    output_config=OutputConfig(
        wildcard_max=body.wildcard_max,
        article_length=body.article_length,
        style_persona=body.style_persona,
    ),
)
```

Pydantic validates `article_length` and `style_persona` against the `Literal` union. Invalid values → HTTP 422 automatically.

---

## 3. Pipeline & Service Changes

### 3.1 Select Images Node (`app/nodes/select_images_node.py`)

Oversamples: target = `ceil(wildcard_max × 1.5)`.

```python
import math

def select_images_node(state: AppState) -> AppState:
    cfg = state.output_config
    target = math.ceil(cfg.wildcard_max * 1.5)
    # ... call select_images_for_blog(images=..., target_count=target, ...)
```

All images used as the selection pool (`state.images`). No pre-filtering.

### 3.2 Review Content Node (`app/nodes/review_content_node.py`)

After enrichment review, filters `state.selected_images` to ≤ `wildcard_max` using the reviewer's quality ratings.

```python
def review_content_node(state: AppState) -> AppState:
    cfg = state.output_config
    ctx = review_enrichment(
        weather=state.weather,
        poi_list=state.poi_list,
        selected_images=state.selected_images,
        gpx_stats=state.gpx_stats,
        notes=state.notes,
        model=state.model,
        output_config=cfg,
    )

    filtered = ctx.get("filtered_images", state.selected_images)
    state.selected_images = filtered[:cfg.wildcard_max]
    state.enrichment_context = ctx
    return state
```

### 3.3 Content Reviewer Service (`app/services/content_reviewer.py`)

`review_enrichment()` gains `output_config: OutputConfig` parameter. After the LLM returns image ratings:

1. Sort images by rating (descending, 1–5)
2. Return the sorted list as `filtered_images` in the result dict
3. The node caps at `wildcard_max`; the ≥33% discard is mathematically guaranteed since `ceil(N × 1.5) × 0.67 ≈ N`

The `_build_review_prompt` is unchanged — it already asks the LLM for image ratings. The `_parse_review_response` gains a `filtered_images` key containing images sorted by rating.

**Fallback behavior (LLM unavailable):** `_build_fallback_context` returns all images rated 3, so the node's `[:wildcard_max]` slice keeps the first N — no meaningful filtering but the pipeline doesn't break.

### 3.4 Blog Generator Service (`app/services/blog_generator.py`)

`construct_blog_post_prompt()` gains `output_config: OutputConfig` parameter. Replaces the hardcoded persona and word count with:

```python
from app.config import PERSONAS, LENGTH_PRESETS

def construct_blog_post_prompt(
    images, map_image_path, elevation_profile_path, gpx_stats,
    notes, image_path_prefix, enrichment_context, weather, poi_list,
    output_config: OutputConfig,
) -> tuple[str, List[Dict[str, Any]]]:

    persona = PERSONAS[output_config.style_persona]
    length = LENGTH_PRESETS[output_config.article_length]

    text_prompt = f"""
{persona['prompt']}

UMFANG: Schreibe {length['min_words']}–{length['max_words']} Wörter. Halte dich an diese Vorgabe — weder deutlich kürzer noch deutlich länger.

HIER SIND DIE DATEN ZUR TOUR:
"""
    # ... rest of prompt construction unchanged ...
```

The existing hardcoded personality block (`"Du bist ein abenteuerlustiger, erfahrener Backpacker..."`) and word count (`"mindestens 800–1000 Wörter"`) are removed. All other prompt structure (hero's journey, image formatting, map/elevation references) remains unchanged.

`generate_blog_post()` gains `output_config: OutputConfig` parameter and passes it to `construct_blog_post_prompt()`.

---

## 4. Frontend Changes

### 4.1 New Components

Three new Svelte components in `frontend/src/lib/`, placed in the sidebar below `NotesInput`:

**`WildcardCount.svelte`**
- Number input (or range slider), range 4–20, default 12
- Label: "Max. Bilder im Artikel"
- Exposes a `getValue(): number` method

**`LengthSelector.svelte`**
- Three radio buttons:
  - "Kurz (300–650 W.)"
  - "Normal (650–1300 W.)"
  - "Ausführlich (1300–2500 W.)"
- Default: "Normal"
- Exposes a `getValue(): string` method returning one of `"short"`, `"normal"`, `"detailed"`

**`StyleSelector.svelte`**
- Two radio buttons, each with label + one-line subtitle:
  - "Mountain Veteran" — "Ich-Perspektive, erfahrener Outdoor-Typ, direkter Ton"
  - "Field Reporter" — "Sachlich, objektiv, trockener Humor"
- Default: "Mountain Veteran"
- Exposes a `getValue(): string` method returning one of `"mountain_veteran"`, `"field_reporter"`

### 4.2 Existing Component Changes

**`RunButton.svelte`** gains three new props: `getWildcardMax`, `getArticleLength`, `getStylePersona`. The POST body to `/api/pipeline/run` includes the three new fields.

**`App.svelte`** binds the three new components and wires their getters to `RunButton`, following the same pattern as `ModelSelector`, `FileDropZone`, `OutputDirInput`, and `NotesInput`.

### 4.3 Unchanged

- `pipeline.ts` store
- `OutputWindow.svelte`
- `ArticleList.svelte`, `ArticleDetail.svelte`
- `router.ts`

---

## 5. Error Handling & Edge Cases

| Scenario | Behavior |
|----------|----------|
| `total_images < ceil(N × 1.5)` | Skip oversampling, use all images. Reviewer filters to ≤ N anyway. |
| `total_images == 0` | Existing behavior: `generate_blog_post_node` returns `success: False`. |
| Reviewer LLM unavailable | `_build_fallback_context` returns all images rated 3. Filter keeps first N — pipeline completes, no crash. |
| Invalid API values | Pydantic validation on `RunPipelineRequest` → HTTP 422. |
| CLI path (`run_pipeline()`) | `OutputConfig` defaults are sensible; no changes needed. |
| Future persona added | Add entry to `PERSONAS` in `config.py`, add literal to `OutputConfig`, add radio button in `StyleSelector.svelte`. |

---

## 6. Files Affected

| File | Change |
|------|--------|
| `app/config.py` | **New** — `PERSONAS`, `LENGTH_PRESETS` constants |
| `app/state.py` | Add `OutputConfig` model + field on `AppState` |
| `app/api/routes.py` | Add 3 fields to `RunPipelineRequest`, pass to `AppState` |
| `app/nodes/select_images_node.py` | Read `output_config.wildcard_max`, compute oversample target |
| `app/nodes/review_content_node.py` | Pass `output_config` to reviewer, filter `selected_images` |
| `app/services/content_reviewer.py` | Accept `output_config`, return `filtered_images` sorted by rating |
| `app/services/blog_generator.py` | Accept `output_config`, use `PERSONAS`/`LENGTH_PRESETS` in prompt |
| `app/nodes/generate_blogpost.py` | Pass `state.output_config` to `generate_blog_post()` |
| `frontend/src/lib/WildcardCount.svelte` | **New** |
| `frontend/src/lib/LengthSelector.svelte` | **New** |
| `frontend/src/lib/StyleSelector.svelte` | **New** |
| `frontend/src/lib/RunButton.svelte` | Add 3 props, include in POST body |
| `frontend/src/App.svelte` | Bind new components |
