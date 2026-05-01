# Configurable Output Parameters — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add user-configurable wildcard photo count, article length presets, and style/persona selection to the blog generation pipeline.

**Architecture:** A new `OutputConfig` Pydantic model carries three fields through the existing pipeline (state → services). Persona prompts and length ranges live as data constants in `app/config.py`. The frontend adds three small Svelte components following the existing `getX()` pattern.

**Tech Stack:** Python (Pydantic, LangGraph, FastAPI), Svelte 5 (runes mode), TypeScript

---

### Task 1: Create `app/config.py` — persona and length data constants

**Files:**
- Create: `app/config.py`

- [ ] **Step 1: Write `app/config.py`**

```python
# app/config.py
"""Konfigurierbare Ausgabeparameter für die Blog-Generierung."""

LENGTH_PRESETS = {
    "short": {"label": "Kurz", "min_words": 300, "max_words": 650},
    "normal": {"label": "Normal", "min_words": 650, "max_words": 1300},
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

- [ ] **Step 2: Verify the module imports cleanly**

```bash
uv run python -c "from app.config import PERSONAS, LENGTH_PRESETS; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add app/config.py
git commit -m "feat: add persona and length preset data constants"
```

---

### Task 2: Add `OutputConfig` model to `app/state.py`

**Files:**
- Modify: `app/state.py`

- [ ] **Step 1: Add `OutputConfig` and field on `AppState`**

In `app/state.py`, add the import and model before `AppState`, then add the field. The file currently has 53 lines.

Add to the imports at line 2 (after `from pydantic import BaseModel`):
```python
from typing import Literal
```

Insert after line 31 (after `AVAILABLE_MODELS`) and before `class AppState`:
```python
class OutputConfig(BaseModel):
    """Konfiguration für die Blog-Ausgabe — vom Benutzer vor Pipeline-Start gesetzt."""
    wildcard_max: int = 12
    article_length: Literal["short", "normal", "detailed"] = "normal"
    style_persona: Literal["mountain_veteran", "field_reporter"] = "mountain_veteran"
```

Add inside `class AppState(BaseModel):` after the `model` field (line 52):
```python
    output_config: OutputConfig = OutputConfig()
```

The final field list in `AppState` should have these lines in order:
```python
class AppState(BaseModel):
    images: List[ImageData] = []
    selected_images: List[ImageData] = []
    image_clusters: List[Dict[str, Any]] = []
    gpx_file: str = ""
    gpx_stats: Optional[GPXStats] = None
    gpx_pauses: List[dict] = []
    elevation_profile_path: Optional[str] = None
    metadata: Dict[str, Any] = {}
    blog_post: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None
    weather: Optional[WeatherInfo] = None
    poi_list: List[Dict[str, Any]] = []
    enrichment_context: Dict[str, Any] = {}
    model: str = "gemma4:26b-ctx128k"
    output_config: OutputConfig = OutputConfig()
```

- [ ] **Step 2: Verify import**

```bash
uv run python -c "from app.state import AppState, OutputConfig; s = AppState(); print(s.output_config.wildcard_max)"
```
Expected: `12`

- [ ] **Step 3: Commit**

```bash
git add app/state.py
git commit -m "feat: add OutputConfig model to AppState"
```

---

### Task 3: Extend `RunPipelineRequest` in API routes

**Files:**
- Modify: `app/api/routes.py`

- [ ] **Step 1: Add fields to `RunPipelineRequest`**

In `app/api/routes.py`, modify the `RunPipelineRequest` class (lines 127-132) to add three new fields:

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

- [ ] **Step 2: Construct `OutputConfig` in the background task**

In `_run_pipeline_in_background` (line 200), modify the `AppState` construction. Change these lines (approximately 196-200):

```python
        state = AppState(
            gpx_file=gpx_file,
            model=model,
            notes=notes if notes else None,
        )
```

To:

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

Add the import at the top of the file (near line 14):
```python
from app.state import AVAILABLE_MODELS, OutputConfig
```

Currently line 14 is:
```python
from app.state import AVAILABLE_MODELS
```
Change it to:
```python
from app.state import AVAILABLE_MODELS, OutputConfig
```

- [ ] **Step 3: Verify import**

```bash
uv run python -c "from app.api.routes import router; print('OK')"
```
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add app/api/routes.py
git commit -m "feat: add output config fields to RunPipelineRequest API"
```

---

### Task 4: Oversample images in `select_images_node`

**Files:**
- Modify: `app/nodes/select_images_node.py`

- [ ] **Step 1: Compute oversample target from config**

In `app/nodes/select_images_node.py`, add `import math` at the top, then change the target computation. Current lines 7-9:

```python
    n = len(state.images)
    target = 12
    print(f"📸 Selecting {target} images for blog post from {n} images...")
```

Change to:

```python
    import math
    n = len(state.images)
    target = math.ceil(state.output_config.wildcard_max * 1.5)
    target = min(target, n)  # nicht mehr als verfügbar
    print(f"📸 Oversampling: selecting {target} images (max {state.output_config.wildcard_max}) from {n} images...")
```

Full file after change:

```python
# app/nodes/select_images_node.py
from app.state import AppState
from app.services.image_selector import select_images_for_blog
import math


def select_images_node(state: AppState) -> AppState:
    """Wählt die besten Bilder für den Blogpost mit einem multimodalen LLM."""
    n = len(state.images)
    target = math.ceil(state.output_config.wildcard_max * 1.5)
    target = min(target, n)
    print(f"📸 Oversampling: selecting {target} images (max {state.output_config.wildcard_max}) from {n} images...")

    selected = select_images_for_blog(
        images=[img.model_dump() for img in state.images],
        target_count=target,
        model=state.model,
    )

    img_by_path = {img.path: img for img in state.images}
    state.selected_images = [
        img_by_path[sel["path"]]
        for sel in selected
        if sel.get("path") in img_by_path
    ]
    state.metadata["selected_image_count"] = len(state.selected_images)

    print(f"✅ Selected {len(selected)} images for blog post")
    return state
```

- [ ] **Step 2: Verify import**

```bash
uv run python -c "from app.nodes.select_images_node import select_images_node; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add app/nodes/select_images_node.py
git commit -m "feat: use wildcard_max for oversampled image selection target"
```

---

### Task 5: Add image filtering to `content_reviewer`

**Files:**
- Modify: `app/services/content_reviewer.py`

- [ ] **Step 1: Accept `output_config` and return `filtered_images`**

In `app/services/content_reviewer.py`, modify `review_enrichment()` to accept and use `output_config`.

Add import at top (after existing imports, around line 13):
```python
from app.state import OutputConfig
```

Change the function signature of `review_enrichment` (lines 180-188):

```python
def review_enrichment(
    weather: Optional[WeatherInfo],
    poi_list: List[Dict[str, Any]],
    selected_images: List[ImageData],
    gpx_stats: Any = None,
    notes: Optional[str] = None,
    model: str = "gemma4:26b-ctx128k",
    base_url: str = "http://localhost:11434",
    output_config: OutputConfig | None = None,
) -> Dict[str, Any]:
```

In the same function, after the result is parsed from the LLM response (after line 248, where `result` is obtained), add the image filtering logic. Replace:

```python
    if result["coherence_score"] < 3 and result["coherence_score"] > 0:
        print(f"⚠️ Low coherence score ({result['coherence_score']}/10) — continuing anyway")

    kept = len(result.get("kept_pois", []))
    print(f"✅ Review complete: {kept} POIs kept, coherence {result['coherence_score']}/10")
    return result
```

With:

```python
    if result["coherence_score"] < 3 and result["coherence_score"] > 0:
        print(f"⚠️ Low coherence score ({result['coherence_score']}/10) — continuing anyway")

    # Bilder nach Qualitätsbewertung filtern
    ratings = result.get("image_ratings", {})
    if ratings and selected_images:
        rated = []
        for img in selected_images:
            score = ratings.get(img.path, 3)
            rated.append((score, img))
        rated.sort(key=lambda x: x[0], reverse=True)
        result["filtered_images"] = [img for _, img in rated]
        print(f"🖼️  Images sorted by quality rating (best first)")
    else:
        result["filtered_images"] = list(selected_images)

    kept = len(result.get("kept_pois", []))
    print(f"✅ Review complete: {kept} POIs kept, coherence {result['coherence_score']}/10")
    return result
```

Also update the fallback function `_build_fallback_context` (lines 252-269) to include `filtered_images`:

```python
def _build_fallback_context(
    weather: Optional[WeatherInfo],
    poi_list: List[Dict[str, Any]],
    selected_images: List[ImageData],
) -> Dict[str, Any]:
    """Baut einen Fallback-Kontext, wenn der Review-LLM nicht verfügbar ist."""
    summary = ""
    if weather:
        summary = weather.summary or "Wetterdaten verfügbar (siehe Details)."

    return {
        "kept_pois": poi_list,
        "weather_summary": summary,
        "discarded_weather_fields": [],
        "image_ratings": {img.path: 3 for img in selected_images},
        "filtered_images": list(selected_images),
        "coherence_score": 0,
        "flags": ["review_unavailable"],
    }
```

- [ ] **Step 2: Verify import**

```bash
uv run python -c "from app.services.content_reviewer import review_enrichment; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add app/services/content_reviewer.py
git commit -m "feat: add quality-based image filtering to content reviewer"
```

---

### Task 6: Wire filtering in `review_content_node`

**Files:**
- Modify: `app/nodes/review_content_node.py`

- [ ] **Step 1: Pass config to reviewer and apply filtered images**

Replace the entire file content:

```python
# app/nodes/review_content_node.py
from app.state import AppState
from app.services.content_reviewer import review_enrichment


def review_content_node(state: AppState) -> AppState:
    """Prüft angereicherte Inhalte auf Qualität und thematische Passung.

    Filtert zudem überzählige Bilder anhand der LLM-Qualitätsbewertung
    auf maximal wildcard_max (≥33% der oversampled Bilder werden verworfen).
    """
    print("🔍 Running content quality review...")

    ctx = review_enrichment(
        weather=state.weather,
        poi_list=state.poi_list,
        selected_images=state.selected_images,
        gpx_stats=state.gpx_stats,
        notes=state.notes,
        model=state.model,
        output_config=state.output_config,
    )

    # Auf wildcard_max kappen — die ≥33% Discard-Quote ist automatisch
    # erfüllt, da select_images ceil(N*1.5) liefert und hier auf N gekappt wird.
    filtered = ctx.get("filtered_images", state.selected_images)
    before = len(state.selected_images)
    state.selected_images = filtered[:state.output_config.wildcard_max]
    after = len(state.selected_images)
    state.enrichment_context = ctx

    score = ctx.get("coherence_score", 0)
    discarded = before - after
    print(f"✅ Content review complete (coherence: {score}/10, images: {after} kept, {discarded} discarded)")

    return state
```

- [ ] **Step 2: Verify import**

```bash
uv run python -c "from app.nodes.review_content_node import review_content_node; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add app/nodes/review_content_node.py
git commit -m "feat: enforce wildcard_max image limit in review node"
```

---

### Task 7: Use config in blog generator prompt

**Files:**
- Modify: `app/services/blog_generator.py`

- [ ] **Step 1: Import config and add `output_config` parameter to `construct_blog_post_prompt`**

At the top of `app/services/blog_generator.py`, add after the existing imports (after line 16):

```python
from app.config import PERSONAS, LENGTH_PRESETS
```

Add `output_config` parameter to `construct_blog_post_prompt` (line 120). Change:

```python
def construct_blog_post_prompt(
    images: List[Dict[str, Any]],
    map_image_path: Optional[str] = None,
    elevation_profile_path: Optional[str] = None,
    gpx_stats: Optional[Dict[str, Any]] = None,
    notes: Optional[str] = None,
    image_path_prefix: str = "",
    enrichment_context: Optional[Dict[str, Any]] = None,
    weather: Any = None,
    poi_list: Optional[List[Dict[str, Any]]] = None,
) -> tuple[str, List[Dict[str, Any]]]:
```

Add `output_config: Any = None` before the closing `)`:

```python
def construct_blog_post_prompt(
    images: List[Dict[str, Any]],
    map_image_path: Optional[str] = None,
    elevation_profile_path: Optional[str] = None,
    gpx_stats: Optional[Dict[str, Any]] = None,
    notes: Optional[str] = None,
    image_path_prefix: str = "",
    enrichment_context: Optional[Dict[str, Any]] = None,
    weather: Any = None,
    poi_list: Optional[List[Dict[str, Any]]] = None,
    output_config: Any = None,
) -> tuple[str, List[Dict[str, Any]]]:
```

- [ ] **Step 2: Replace hardcoded persona/length with config-driven blocks**

The current prompt header starts at line 148 with the hardcoded personality `"Du bist ein abenteuerlustiger, erfahrener Backpacker..."`. Replace the header section (lines 148-154):

Current:
```python
    # Header für den Prompt
    text_prompt = """
    Du bist ein abenteuerlustiger, erfahrener Backpacker und ein gefeierter Reiseblogger. Dein Schreibstil ist fesselnd, humorvoll, authentisch und voller Leidenschaft. Deine Leser lieben dich für deine langen, lebhaften und immersiven Erzählungen, bei denen sie das Gefühl haben, direkt neben dir zu wandern.

    Deine Aufgabe ist es, einen ausführlichen, spannenden und mitreißenden Long-Form-Blogpost über unsere neueste Tour zu verfassen. Schreibe nicht nur einen Bericht, sondern erzähle eine echte Geschichte!

    HIER SIND DIE DATEN ZUR TOUR:
    """
```

Replace with:

```python
    # Header für den Prompt — Persona und Länge aus Config
    persona_prompt = ""
    length_guidance = ""
    if output_config and hasattr(output_config, 'style_persona'):
        persona = PERSONAS.get(output_config.style_persona, list(PERSONAS.values())[0])
        persona_prompt = persona["prompt"]
        length = LENGTH_PRESETS.get(output_config.article_length, LENGTH_PRESETS["normal"])
        length_guidance = (
            f"UMFANG: Schreibe {length['min_words']}–{length['max_words']} Wörter. "
            f"Halte dich an diese Vorgabe — weder deutlich kürzer noch deutlich länger.\n"
        )
    else:
        # Fallback für Aufrufe ohne OutputConfig (CLI, alte Tests)
        persona_prompt = PERSONAS["mountain_veteran"]["prompt"]
        length_guidance = "UMFANG: Schreibe 650–1300 Wörter.\n"

    text_prompt = f"""{persona_prompt}

{length_guidance}
Deine Aufgabe ist es, einen Blogpost über unsere neueste Tour zu verfassen.
Schreibe nicht nur einen Bericht, sondern erzähle eine echte Geschichte!

HIER SIND DIE DATEN ZUR TOUR:
"""
```

- [ ] **Step 3: Remove the old hardcoded word count**

In the existing prompt, there's a line (around line 186):
```
    1. **UMFANG & TIEFE (SEHR WICHTIG)**: Schreibe einen ausführlichen Artikel (mindestens 800-1000 Wörter). Nimm dir Zeit für Details. Beschreibe die Atmosphäre, das Wetter, die körperliche Anstrengung (brennende Waden bei Höhenmetern!), die Geräusche der Natur und das Gefühl der Belohnung am Ziel. "Show, don't tell!"
```

Replace it with:
```
    1. **TIEFE**: Nimm dir Zeit für Details. Beschreibe die Atmosphäre, das Wetter, die körperliche Anstrengung (brennende Waden bei Höhenmetern!), die Geräusche der Natur und das Gefühl der Belohnung am Ziel. "Show, don't tell!"
```

- [ ] **Step 4: Remove old persona reference in prompt**

The old prompt has a section "STIL & PERSPEKTIVE" (around line 195):
```
    4. **STIL & PERSPEKTIVE**: Locker, persönlich, kumpelhaft. Nutze konsequent "wir" statt "ich". Streue etwas Humor ein (z.B. über schwere Rucksäcke oder falsche Abzweigungen). Mach den Leser neugierig. Nutze abwechslungsreiche Satzstrukturen und Absätze, um den Lesefluss dynamisch zu halten.
```

Replace with:
```
    4. **TEXTFLUSS**: Mach den Leser neugierig. Nutze abwechslungsreiche Satzstrukturen und Absätze, um den Lesefluss dynamisch zu halten.
```

- [ ] **Step 5: Add `output_config` to `generate_blog_post` and pass it through**

Change the `generate_blog_post` function signature (line 400):

```python
def generate_blog_post(
    images: List[Dict[str, Any]],
    map_image_path: Optional[str] = None,
    elevation_profile_path: Optional[str] = None,
    gpx_stats: Optional[Dict[str, Any]] = None,
    notes: Optional[str] = None,
    model: str = "gemma4:26b-ctx128k",
    enrichment_context: Optional[Dict[str, Any]] = None,
    weather: Any = None,
    poi_list: Optional[List[Dict[str, Any]]] = None,
    output_config: Any = None,
) -> Dict[str, Any]:
```

And pass it to `construct_blog_post_prompt` (around line 462):

```python
    prompt, image_data = construct_blog_post_prompt(
        images=images_for_prompt,
        map_image_path=abs_map,
        elevation_profile_path=elevation_profile_path,
        gpx_stats=gpx_stats,
        notes=notes,
        image_path_prefix=image_path_prefix,
        enrichment_context=enrichment_context,
        weather=weather,
        poi_list=poi_list,
        output_config=output_config,
    )
```

- [ ] **Step 6: Verify import**

```bash
uv run python -c "from app.services.blog_generator import generate_blog_post, construct_blog_post_prompt; print('OK')"
```
Expected: `OK`

- [ ] **Step 7: Commit**

```bash
git add app/services/blog_generator.py
git commit -m "feat: use persona and length config in blog prompt construction"
```

---

### Task 8: Pass config from `generate_blogpost_node`

**Files:**
- Modify: `app/nodes/generate_blogpost.py`

- [ ] **Step 1: Add `output_config` to the service call**

In `app/nodes/generate_blogpost.py`, modify the `generate_blog_post()` call (lines 35-45) to include `output_config`:

```python
        result = generate_blog_post(
            images=[img.model_dump() for img in images],
            map_image_path=map_image_path,
            elevation_profile_path=state.elevation_profile_path,
            gpx_stats=state.gpx_stats.model_dump() if hasattr(state.gpx_stats, "model_dump") else state.gpx_stats,
            notes=state.notes,
            model=state.model,
            enrichment_context=state.enrichment_context,
            weather=state.weather,
            poi_list=state.poi_list,
            output_config=state.output_config,
        )
```

- [ ] **Step 2: Verify import**

```bash
uv run python -c "from app.nodes.generate_blogpost import generate_blog_post_node; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add app/nodes/generate_blogpost.py
git commit -m "feat: pass output_config from blogpost node to generator service"
```

---

### Task 9: Create `WildcardCount.svelte`

**Files:**
- Create: `frontend/src/lib/WildcardCount.svelte`

- [ ] **Step 1: Write the component**

```svelte
<script lang="ts">
  let count: number = $state(12);

  export function getValue(): number {
    return count;
  }
</script>

<div class="wildcard">
  <label for="wildcard-input">Max. Bilder im Artikel</label>
  <div class="wildcard-row">
    <input
      id="wildcard-input"
      type="range"
      min={4}
      max={20}
      bind:value={count}
    />
    <span class="count-badge">{count}</span>
  </div>
</div>

<style>
  .wildcard {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }
  label {
    font-size: 0.75rem;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  .wildcard-row {
    display: flex;
    align-items: center;
    gap: 0.75rem;
  }
  input[type="range"] {
    flex: 1;
    accent-color: var(--accent);
    background: var(--bg);
    height: 4px;
    border: none;
    padding: 0;
  }
  .count-badge {
    font-size: 0.9rem;
    font-weight: bold;
    color: var(--accent);
    min-width: 2rem;
    text-align: center;
  }
</style>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/lib/WildcardCount.svelte
git commit -m "feat: add WildcardCount component for photo count config"
```

---

### Task 10: Create `LengthSelector.svelte`

**Files:**
- Create: `frontend/src/lib/LengthSelector.svelte`

- [ ] **Step 1: Write the component**

```svelte
<script lang="ts">
  let selected: string = $state("normal");

  export function getValue(): string {
    return selected;
  }

  const options = [
    { value: "short", label: "Kurz", desc: "300–650 Wörter" },
    { value: "normal", label: "Normal", desc: "650–1300 Wörter" },
    { value: "detailed", label: "Ausführlich", desc: "1300–2500 Wörter" },
  ];
</script>

<div class="length">
  <label>Artikellänge</label>
  <div class="options">
    {#each options as opt}
      <label class="option">
        <input
          type="radio"
          name="length"
          value={opt.value}
          bind:group={selected}
        />
        <div class="option-text">
          <span class="option-label">{opt.label}</span>
          <span class="option-desc">{opt.desc}</span>
        </div>
      </label>
    {/each}
  </div>
</div>

<style>
  .length {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }
  label {
    font-size: 0.75rem;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  .options {
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
  }
  .option {
    display: flex;
    align-items: flex-start;
    gap: 0.5rem;
    cursor: pointer;
    text-transform: none;
    font-size: 0.8rem;
    color: var(--text);
    padding: 0.3rem 0;
  }
  .option input[type="radio"] {
    accent-color: var(--accent);
    margin-top: 0.15rem;
  }
  .option-text {
    display: flex;
    flex-direction: column;
    gap: 0.1rem;
  }
  .option-label {
    font-weight: 500;
  }
  .option-desc {
    font-size: 0.7rem;
    color: var(--text-muted);
  }
</style>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/lib/LengthSelector.svelte
git commit -m "feat: add LengthSelector component for article length config"
```

---

### Task 11: Create `StyleSelector.svelte`

**Files:**
- Create: `frontend/src/lib/StyleSelector.svelte`

- [ ] **Step 1: Write the component**

```svelte
<script lang="ts">
  let selected: string = $state("mountain_veteran");

  export function getValue(): string {
    return selected;
  }

  const options = [
    {
      value: "mountain_veteran",
      label: "Mountain Veteran",
      desc: "Ich-Perspektive, erfahrener Outdoor-Typ, direkter Ton",
    },
    {
      value: "field_reporter",
      label: "Field Reporter",
      desc: "Sachlich, objektiv, trockener Humor",
    },
  ];
</script>

<div class="style">
  <label>Schreibstil</label>
  <div class="options">
    {#each options as opt}
      <label class="option">
        <input
          type="radio"
          name="style"
          value={opt.value}
          bind:group={selected}
        />
        <div class="option-text">
          <span class="option-label">{opt.label}</span>
          <span class="option-desc">{opt.desc}</span>
        </div>
      </label>
    {/each}
  </div>
</div>

<style>
  .style {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }
  label {
    font-size: 0.75rem;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  .options {
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
  }
  .option {
    display: flex;
    align-items: flex-start;
    gap: 0.5rem;
    cursor: pointer;
    text-transform: none;
    font-size: 0.8rem;
    color: var(--text);
    padding: 0.3rem 0;
  }
  .option input[type="radio"] {
    accent-color: var(--accent);
    margin-top: 0.15rem;
  }
  .option-text {
    display: flex;
    flex-direction: column;
    gap: 0.1rem;
  }
  .option-label {
    font-weight: 500;
  }
  .option-desc {
    font-size: 0.7rem;
    color: var(--text-muted);
  }
</style>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/lib/StyleSelector.svelte
git commit -m "feat: add StyleSelector component for persona config"
```

---

### Task 12: Extend `RunButton.svelte`

**Files:**
- Modify: `frontend/src/lib/RunButton.svelte`

- [ ] **Step 1: Add props and include in POST body**

Change the props declaration (lines 4-9):

```typescript
  let { getModel, getFiles, getOutputDir, getNotes, getWildcardMax, getArticleLength, getStylePersona }: {
    getModel: () => string;
    getFiles: () => { gpxFile: string; imageFiles: string[]; txtFile: string | null };
    getOutputDir: () => string;
    getNotes: () => string;
    getWildcardMax: () => number;
    getArticleLength: () => string;
    getStylePersona: () => string;
  } = $props();
```

In `handleRun` (lines 13-17), add the three new values:

```typescript
    const model = getModel();
    const { gpxFile, imageFiles } = getFiles();
    const outputDir = getOutputDir();
    const notes = getNotes();
    const wildcardMax = getWildcardMax();
    const articleLength = getArticleLength();
    const stylePersona = getStylePersona();
```

In the POST body (lines 31-37), add the three fields:

```typescript
        body: JSON.stringify({
          model,
          output_dir: outputDir,
          notes,
          gpx_file: gpxFile,
          image_files: imageFiles,
          wildcard_max: wildcardMax,
          article_length: articleLength,
          style_persona: stylePersona,
        }),
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/lib/RunButton.svelte
git commit -m "feat: add config fields to RunButton API call"
```

---

### Task 13: Bind new components in `App.svelte`

**Files:**
- Modify: `frontend/src/App.svelte`

- [ ] **Step 1: Import and bind new components**

Add imports (after existing imports on lines 5-12):

```typescript
  import WildcardCount from "./lib/WildcardCount.svelte";
  import LengthSelector from "./lib/LengthSelector.svelte";
  import StyleSelector from "./lib/StyleSelector.svelte";
```

Add component references (after line 17, alongside the other `let` declarations):

```typescript
  let wildcardCount: WildcardCount;
  let lengthSelector: LengthSelector;
  let styleSelector: StyleSelector;
```

Add components to the template (after the `NotesInput` block, around line 47, before the `run-section` div):

```svelte
      <WildcardCount bind:this={wildcardCount} />
      <LengthSelector bind:this={lengthSelector} />
      <StyleSelector bind:this={styleSelector} />
```

Update the `RunButton` props (lines 49-55):

```svelte
        <RunButton
          getModel={() => modelSelector.getModel()}
          getFiles={() => fileDropZone.getFiles()}
          getOutputDir={() => outputDirInput.getOutputDir()}
          getNotes={() => notesInput.getNotes()}
          getWildcardMax={() => wildcardCount.getValue()}
          getArticleLength={() => lengthSelector.getValue()}
          getStylePersona={() => styleSelector.getValue()}
        />
```

- [ ] **Step 2: Build frontend to verify**

```bash
cd frontend && npm run build
```
Expected: build succeeds with no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/App.svelte
git commit -m "feat: bind WildcardCount, LengthSelector, StyleSelector in App"
```

---

### Task 14: End-to-end verification

- [ ] **Step 1: Start the backend and verify import chain**

```bash
uv run python -c "
from app.state import AppState, OutputConfig
from app.config import PERSONAS, LENGTH_PRESETS
from app.services.blog_generator import construct_blog_post_prompt
from app.services.content_reviewer import review_enrichment
from app.services.image_selector import select_images_for_blog

s = AppState()
s.output_config = OutputConfig(wildcard_max=8, article_length='short', style_persona='field_reporter')

print(f'Config: wildcard={s.output_config.wildcard_max}, length={s.output_config.article_length}, persona={s.output_config.style_persona}')
print(f'Personas: {list(PERSONAS.keys())}')
print(f'Lengths: {list(LENGTH_PRESETS.keys())}')
print('All imports OK')
"
```
Expected: prints config values and "All imports OK"

- [ ] **Step 2: Start the backend server to confirm no startup errors**

```bash
timeout 5 uv run uvicorn app.api.server:app --host 0.0.0.0 --port 8000 2>&1 || true
```
Expected: server starts, no import errors.

- [ ] **Step 3: Build frontend to confirm all components compile**

```bash
cd frontend && npm run build
```
Expected: build succeeds.

- [ ] **Step 4: Commit verification artifacts if any**
