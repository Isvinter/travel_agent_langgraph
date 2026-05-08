# Photobook Presets Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 5 thematic photobook presets that steer LLM prompts for image selection, layout planning, and page generation.

**Architecture:** A `PhotobookPreset` Pydantic model holds per-preset prompt fragments. A static `PHOTOBOOK_PRESETS` dict in `presets.py` defines all 5. The three photobook service functions accept a `preset` parameter and inject its fragments into their LLM prompts. Node functions read `state.output_config.photobook_preset` and pass it through.

**Tech Stack:** Python 3.12+, Pydantic v2, LangGraph, Ollama (unchanged)

---

### Task 1: Add `PhotobookPreset` model, presets map, and helper

**Files:**
- Modify: `app/photobook/presets.py`
- Create: `tests/test_photobook_presets.py`

- [ ] **Step 1: Write the failing tests**

```python
"""Tests für PhotobookPreset und get_photobook_preset."""
import pytest
from app.photobook.presets import (
    PhotobookPreset,
    PHOTOBOOK_PRESETS,
    get_photobook_preset,
)


class TestPhotobookPresetModel:
    def test_valid_preset_creation(self):
        preset = PhotobookPreset(
            id="test",
            name="Test Preset",
            selection_criteria="wähle testbilder",
            layout_preferences="nutze tests",
            generation_instructions="schreibe testtext",
            text_enabled=True,
        )
        assert preset.id == "test"
        assert preset.name == "Test Preset"
        assert preset.selection_criteria == "wähle testbilder"
        assert preset.layout_preferences == "nutze tests"
        assert preset.generation_instructions == "schreibe testtext"
        assert preset.text_enabled is True

    def test_text_enabled_defaults_to_true(self):
        preset = PhotobookPreset(
            id="test",
            name="Test",
            selection_criteria="",
            layout_preferences="",
            generation_instructions="",
        )
        assert preset.text_enabled is True


class TestPhotobookPresetsMap:
    def test_all_five_presets_defined(self):
        expected_ids = {
            "nature_outdoor",
            "culture_architecture",
            "people",
            "nature_collage",
            "mixed",
        }
        assert set(PHOTOBOOK_PRESETS.keys()) == expected_ids

    def test_each_preset_is_valid_model(self):
        for preset in PHOTOBOOK_PRESETS.values():
            assert isinstance(preset, PhotobookPreset)
            assert preset.id
            assert preset.name

    def test_nature_collage_has_text_disabled(self):
        preset = PHOTOBOOK_PRESETS["nature_collage"]
        assert preset.text_enabled is False

    def test_mixed_has_empty_criteria_prefs_instructions(self):
        preset = PHOTOBOOK_PRESETS["mixed"]
        assert preset.selection_criteria == ""
        assert preset.layout_preferences == ""
        assert preset.generation_instructions == ""
        assert preset.text_enabled is True

    def test_non_mixed_presets_have_criteria(self):
        for pid, preset in PHOTOBOOK_PRESETS.items():
            if pid != "mixed":
                assert preset.selection_criteria != "", f"{pid} hat leere selection_criteria"
                assert preset.layout_preferences != "", f"{pid} hat leere layout_preferences"
                # nature_collage generiert keine Texte, daher keine instructions nötig
                if pid != "nature_collage":
                    assert preset.generation_instructions != "", f"{pid} hat leere generation_instructions"


class TestGetPhotobookPreset:
    def test_valid_id_returns_correct_preset(self):
        preset = get_photobook_preset("nature_outdoor")
        assert preset.id == "nature_outdoor"
        assert preset.name == "Natur, Outdoor & Sport"

    def test_invalid_id_falls_back_to_mixed(self):
        preset = get_photobook_preset("nonexistent")
        assert preset.id == "mixed"

    def test_empty_string_falls_back_to_mixed(self):
        preset = get_photobook_preset("")
        assert preset.id == "mixed"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_photobook_presets.py -v`
Expected: FAIL with "cannot import name 'PhotobookPreset'"

- [ ] **Step 3: Add `PhotobookPreset` model, `PHOTOBOOK_PRESETS`, and `get_photobook_preset()` to `presets.py`**

```python
"""Preset-Metadaten fuer LLM-Prompts (leichtgewichtig, ohne JSON-Loading)."""
from pydantic import BaseModel

# ... bestehende PRESET_CATALOG, get_preset_summary, get_presets_by_image_count,
#     get_any_preset, TEXT_CONSTRAINTS, get_constraint_summary bleiben unverändert ...


class PhotobookPreset(BaseModel):
    """Thematisches Fotobuch-Preset — steuert LLM-Anweisungen in 3 Phasen."""
    id: str
    name: str
    selection_criteria: str
    layout_preferences: str
    generation_instructions: str
    text_enabled: bool = True


PHOTOBOOK_PRESETS: dict[str, PhotobookPreset] = {
    "nature_outdoor": PhotobookPreset(
        id="nature_outdoor",
        name="Natur, Outdoor & Sport",
        selection_criteria=(
            "Fokussiere auf Bilder mit Outdoor-Aktivitäten (Wandern, Klettern, "
            "Paragliding, Skitouren, Mountainbike), Landschaften und Natur. "
            "Wähle eine abwechslungsreiche Mischung aus Action-Aufnahmen, "
            "Panoramen, Detailaufnahmen und stimmungsvollen Momenten."
        ),
        layout_preferences=(
            "Erstelle ein abwechslungsreiches Layout. Verwende grossformatige "
            "Einzelbilder für Landschaftspanoramen, 2er/3er-Kombinationen für "
            "Aktionssequenzen und 4er/5er-Grids für Stimmungs-Collagen. "
            "Variiere zwischen Text- und Bild-lastigen Seiten."
        ),
        generation_instructions=(
            "Schreibe im Stil eines Reise-/Adventure-Blogs: lebendig, "
            "atmosphärisch, mit Fokus auf das Erlebnis und die Aktivität. "
            "Beschreibe sowohl die Landschaft als auch die Aktion — was "
            "wurde gemacht, wie war die Stimmung, welche Herausforderungen "
            "gab es? Nutze die Zeichenlimits aus."
        ),
        text_enabled=True,
    ),
    "culture_architecture": PhotobookPreset(
        id="culture_architecture",
        name="Kultur, Architektur & Städte",
        selection_criteria=(
            "Fokussiere auf Gebäude, Denkmäler, Stadtansichten, architektonische "
            "Details, Kirchen, Burgen und kulturell interessante Motive. "
            "Vermeide reine Naturbilder ohne kulturellen Bezug."
        ),
        layout_preferences=(
            "Bevorzuge Presets mit Text (image_text_split, single_text_below) "
            "für architektonische Beschreibungen. Nutze 2er/3er-Presets für "
            "Detailvergleiche."
        ),
        generation_instructions=(
            "Beschreibe Architektur, Geschichte und kulturellen Kontext. "
            "Gehe auf Baustil, Epoche, Besonderheiten und historische "
            "Hintergründe ein."
        ),
        text_enabled=True,
    ),
    "people": PhotobookPreset(
        id="people",
        name="Menschen",
        selection_criteria=(
            "Fokussiere auf Menschen: Porträts, Gruppenaufnahmen, emotionale "
            "Momente, Aktivitäten mit Personen. Vermeide reine Landschaftsbilder "
            "ohne Menschen."
        ),
        layout_preferences=(
            "Bevorzuge Presets mit mehreren Bildern (quad_grid, double_stacked) "
            "für Personengruppen. Verwende Einzelbild-Presets für Porträts."
        ),
        generation_instructions=(
            "Beschreibe die Menschen auf den Bildern: Stimmung, Aktivität, "
            "Situation, Emotionen. Erzähle kleine Geschichten zu den "
            "Momentaufnahmen."
        ),
        text_enabled=True,
    ),
    "nature_collage": PhotobookPreset(
        id="nature_collage",
        name="Natur-Bildercollagen",
        selection_criteria=(
            "Fokussiere auf Landschaftsaufnahmen, weite Panoramen, Vegetation, "
            "Tiere, Naturdetails."
        ),
        layout_preferences=(
            "Verwende AUSSCHLIESSLICH Presets ohne Text. Bevorzuge 3er-, 4er- "
            "und 5er-Grids (collage_5, quad_grid, triple_stacked). "
            "Das Fotobuch ist eine reine Bilder-Collage."
        ),
        generation_instructions="",
        text_enabled=False,
    ),
    "mixed": PhotobookPreset(
        id="mixed",
        name="Gemischt",
        selection_criteria="",
        layout_preferences="",
        generation_instructions="",
        text_enabled=True,
    ),
}


def get_photobook_preset(preset_id: str) -> PhotobookPreset:
    """Liefert das Preset-Objekt, mit Fallback auf 'mixed'."""
    return PHOTOBOOK_PRESETS.get(preset_id, PHOTOBOOK_PRESETS["mixed"])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_photobook_presets.py -v`
Expected: all 10 tests PASS

- [ ] **Step 5: Commit**

```bash
git add app/photobook/presets.py tests/test_photobook_presets.py
git commit -m "feat: add PhotobookPreset model with 5 thematic presets"
```

---

### Task 2: Add `photobook_preset` field to `OutputConfig`

**Files:**
- Modify: `app/state.py`

- [ ] **Step 1: Add the field to `OutputConfig`**

In `app/state.py`, in the `OutputConfig` class (line 64-71), add the new field:

```python
class OutputConfig(BaseModel):
    """Konfiguration für die Blog-Ausgabe — vom Benutzer vor Pipeline-Start gesetzt."""
    wildcard_max: int = Field(default=12, ge=1, le=50)
    article_length: Literal["short", "normal", "detailed"] = "normal"
    style_persona: Literal["mountain_veteran", "field_reporter"] = "mountain_veteran"
    pdf_export: bool = False
    mode: Literal["blog", "photobook"] = "blog"
    photobook: PhotobookConfig = PhotobookConfig()
    photobook_preset: Literal[
        "nature_outdoor", "culture_architecture", "people", "nature_collage", "mixed"
    ] = "mixed"
```

- [ ] **Step 2: Verify import works**

Run: `uv run python -c "from app.state import OutputConfig; c = OutputConfig(); assert c.photobook_preset == 'mixed'; print('OK')"`
Expected: prints "OK"

- [ ] **Step 3: Commit**

```bash
git add app/state.py
git commit -m "feat: add photobook_preset field to OutputConfig"
```

---

### Task 3: Wire preset into image selection

**Files:**
- Modify: `app/photobook/image_selector.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_photobook_presets.py`:

```python
from app.photobook.image_selector import _build_batch_prompt


class TestImageSelectorPresetIntegration:
    def test_build_batch_prompt_injects_selection_criteria(self):
        preset = PhotobookPreset(
            id="test",
            name="Test Preset",
            selection_criteria="Wähle nur Sonnenuntergänge.",
            layout_preferences="",
            generation_instructions="",
            text_enabled=True,
        )
        prompt = _build_batch_prompt(batch_size=5, select_count=2, preset=preset)
        assert "Test Preset" in prompt
        assert "Wähle nur Sonnenuntergänge." in prompt
        assert "--- Bild 0 ---" in prompt
        assert "--- Bild 4 ---" in prompt

    def test_build_batch_prompt_mixed_preset_uses_default_criteria(self):
        preset = PHOTOBOOK_PRESETS["mixed"]
        prompt = _build_batch_prompt(batch_size=3, select_count=1, preset=preset)
        assert "Gemmischt" in prompt
        assert "starke Motive" in prompt
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_photobook_presets.py::TestImageSelectorPresetIntegration -v`
Expected: FAIL — `_build_batch_prompt` takes too many arguments or doesn't exist

- [ ] **Step 3: Update `_build_batch_prompt` to accept and use preset**

Change `_build_batch_prompt` (lines 26-35 of `image_selector.py`):

```python
from app.photobook.presets import PhotobookPreset


def _build_batch_prompt(batch_size: int, select_count: int, preset: PhotobookPreset) -> str:
    criteria = preset.selection_criteria if preset.selection_criteria else (
        "starke Motive, gute Belichtung, landschaftliche Vielfalt, "
        "verschiedene Perspektiven, Details und Porträts mischen."
    )
    return (
        f"Du erhältst {batch_size} Fotos aus einer Wanderung.\n"
        f"Wähle die {select_count} besten Bilder für ein A4-Fotobuch "
        f"({preset.name}).\n"
        f"Kriterien: {criteria}\n"
        "Antworte NUR mit den 0-basierten Indexnummern, kommagetrennt, aufsteigend. "
        "Keine Erklärung.\n\n"
        + "\n".join(f"--- Bild {i} ---" for i in range(batch_size))
    )
```

- [ ] **Step 4: Update `_select_batch` to accept and forward preset**

Change signature (line 38):

```python
def _select_batch(
    batch_images: List[ImageData],
    select_count: int,
    model: str,
    base_url: str,
    preset: PhotobookPreset,
) -> List[int]:
```

And update the call to `_build_batch_prompt` inside (line 56):

```python
    prompt = _build_batch_prompt(len(encoded), select_count, preset)
```

- [ ] **Step 5: Update `select_photobook_images` to accept and forward preset**

Change signature (line 87):

```python
def select_photobook_images(
    images: List[ImageData],
    gpx_stats: Optional[Dict[str, Any]],
    notes: Optional[str],
    model: str = "gemma4:26b-ctx128k",
    photo_count: int = 16,
    base_url: str = OLLAMA_BASE_URL,
    preset: PhotobookPreset = None,
) -> List[ImageData]:
```

Add import for `get_photobook_preset` at top of file (or set default):

```python
from app.photobook.presets import PhotobookPreset, get_photobook_preset

# In function body, at start:
if preset is None:
    preset = get_photobook_preset("mixed")
```

Update `_select_batch` calls (lines 120 and 135) to pass `preset`:

```python
        batch_indices = _select_batch(batch, select, model, base_url, preset)
```

```python
    final_indices = _select_batch(selected, target, model, base_url, preset)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/test_photobook_presets.py::TestImageSelectorPresetIntegration -v`
Expected: all 2 tests PASS

- [ ] **Step 7: Commit**

```bash
git add app/photobook/image_selector.py tests/test_photobook_presets.py
git commit -m "feat: wire photobook preset into image selection prompt"
```

---

### Task 4: Wire preset into layout planning

**Files:**
- Modify: `app/photobook/plan.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_photobook_presets.py`:

```python
from app.photobook.plan import _build_plan_prompt


class TestPlanPresetIntegration:
    def test_build_plan_prompt_injects_layout_preferences(self):
        preset = PhotobookPreset(
            id="test",
            name="Test Layout",
            selection_criteria="",
            layout_preferences="Bevorzuge nur 1-Bild-Presets.",
            generation_instructions="",
            text_enabled=True,
        )
        prompt = _build_plan_prompt(
            image_count=5,
            gpx_stats_d=None,
            notes=None,
            weather=None,
            poi_count=0,
            page_range=None,
            preset=preset,
        )
        assert "THEMA: Test Layout" in prompt
        assert "Bevorzuge nur 1-Bild-Presets." in prompt

    def test_build_plan_prompt_mixed_has_no_theme_section(self):
        preset = PHOTOBOOK_PRESETS["mixed"]
        prompt = _build_plan_prompt(
            image_count=5,
            gpx_stats_d=None,
            notes=None,
            weather=None,
            poi_count=0,
            page_range=None,
            preset=preset,
        )
        assert "THEMA:" not in prompt
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_photobook_presets.py::TestPlanPresetIntegration -v`
Expected: FAIL — `_build_plan_prompt` got unexpected keyword argument 'preset'

- [ ] **Step 3: Update `_build_plan_prompt` to accept and use preset**

Change signature (line 17):

```python
from app.photobook.presets import PhotobookPreset


def _build_plan_prompt(
    image_count: int,
    gpx_stats_d: Optional[Dict[str, Any]],
    notes: Optional[str],
    weather: Optional[WeatherInfo],
    poi_count: int,
    page_range: Optional[str] = None,
    preset: PhotobookPreset = None,
) -> str:
```

Add `get_photobook_preset` import at top of file:

```python
from app.photobook.presets import get_preset_summary, get_any_preset, PhotobookPreset, get_photobook_preset
```

Near the top of `_build_plan_prompt`, after the existing code but before the return statement, add the theme injection. After the variety rules section (after "6. Seite 0 MUSS cover_hero sein"), insert:

```python
    theme_block = ""
    if preset and preset.layout_preferences:
        theme_block = f"\nTHEMA: {preset.name}\n{preset.layout_preferences}\n"
```

And append `{theme_block}` to the return string, before the final `ANTWORTE AUSSCHLIESSLICH mit diesem JSON:` line.

The full updated return statement:

```python
    return f"""Du bist Fotobuch-Art-Director fuer eine Wandertour.

{context}{page_range_hint}
PRESETS (waehle eins pro Seite):
{preset_catalog}

VARIETY-REGELN (UNBEDINGT EINHALTEN):
1. Maximal 2x das gleiche Preset im gesamten Buch (cover_hero NUR auf Seite 0, niemals woanders)
2. Nicht 2x hintereinander das gleiche Preset
3. Maximal 3 Seiten ohne Text hintereinander
4. Nicht 3x hintereinander die gleiche Bildanzahl
5. Dramatischer Bogen: Cover (cover_hero) -> ruhiger Start (1-Bild) -> Aufbau (2-3 Bilder) -> Hoehepunkt (4-Bild) -> Ausklang (1-Bild)
6. Seite 0 MUSS cover_hero sein
{theme_block}
PLANE die Seitenabfolge. Gib JEDEM Bild einen Platz — alle {image_count} Bilder muessen verwendet werden.

ANTWORTE AUSSCHLIESSLICH mit diesem JSON:
{{"pages": [{{"position": 0, "preset_id": "cover_hero", "image_indices": [3], "purpose": "Cover"}}], "dramatic_arc": "kurze Beschreibung"}}"""
```

- [ ] **Step 4: Update `plan_photobook_layout` to accept and forward preset**

Change signature (line 118):

```python
def plan_photobook_layout(
    images: List[ImageData],
    gpx_stats: Optional[Dict[str, Any]],
    notes: Optional[str],
    weather: Optional[WeatherInfo],
    poi_list: List[Dict[str, Any]],
    model: str = "gemma4:26b-ctx128k",
    base_url: str = OLLAMA_BASE_URL,
    page_range: str = "",
    preset: PhotobookPreset = None,
) -> Dict[str, Any]:
```

At the start of the function body, set default:

```python
    if preset is None:
        preset = get_photobook_preset("mixed")
```

Update the `_build_plan_prompt` call (line 130) to pass `preset`:

```python
    prompt = _build_plan_prompt(
        len(images), gpx_stats, notes, weather, len(poi_list),
        page_range=page_range if page_range else None,
        preset=preset,
    )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_photobook_presets.py::TestPlanPresetIntegration -v`
Expected: all 2 tests PASS

- [ ] **Step 6: Commit**

```bash
git add app/photobook/plan.py tests/test_photobook_presets.py
git commit -m "feat: wire photobook preset into layout planning prompt"
```

---

### Task 5: Wire preset into page generation

**Files:**
- Modify: `app/photobook/generate.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_photobook_presets.py`:

```python
from app.photobook.generate import _build_generate_prompt


class TestGeneratePresetIntegration:
    def test_build_generate_prompt_injects_generation_instructions(self):
        preset = PhotobookPreset(
            id="test",
            name="Test Gen",
            selection_criteria="",
            layout_preferences="",
            generation_instructions="Schreibe im poetischen Stil.",
            text_enabled=True,
        )
        pages_plan = [
            {"preset_id": "single_text_below", "image_indices": [0], "purpose": "Test"}
        ]
        prompt = _build_generate_prompt(pages_plan, None, None, preset=preset)
        assert "STILVORGABE (Test Gen)" in prompt
        assert "Schreibe im poetischen Stil." in prompt

    def test_build_generate_prompt_mixed_has_no_style_section(self):
        preset = PHOTOBOOK_PRESETS["mixed"]
        pages_plan = [
            {"preset_id": "single_text_below", "image_indices": [0], "purpose": "Test"}
        ]
        prompt = _build_generate_prompt(pages_plan, None, None, preset=preset)
        assert "STILVORGABE" not in prompt

    def test_build_generate_prompt_text_disabled_no_text_block(self):
        preset = PHOTOBOOK_PRESETS["nature_collage"]
        pages_plan = [
            {"preset_id": "quad_grid", "image_indices": [0, 1, 2, 3], "purpose": "Collage"}
        ]
        prompt = _build_generate_prompt(pages_plan, None, None, preset=preset)
        assert "TEXT IST PFLICHT" not in prompt
        assert "title-Slot" not in prompt

    def test_build_generate_prompt_text_enabled_has_text_block(self):
        preset = PHOTOBOOK_PRESETS["nature_outdoor"]
        pages_plan = [
            {"preset_id": "single_text_below", "image_indices": [0], "purpose": "Test"}
        ]
        prompt = _build_generate_prompt(pages_plan, None, None, preset=preset)
        assert "TEXT IST PFLICHT" in prompt
        assert "title-Slot" in prompt
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_photobook_presets.py::TestGeneratePresetIntegration -v`
Expected: FAIL — `_build_generate_prompt` got unexpected keyword argument 'preset'

- [ ] **Step 3: Update `_build_generate_prompt` to accept and use preset**

Change signature (line 14):

```python
from app.photobook.presets import PhotobookPreset, get_photobook_preset


def _build_generate_prompt(pages_plan, gpx_stats_d, notes, preset=None):
```

At start of function (after the docstring/imports), set default:

```python
    if preset is None:
        preset = get_photobook_preset("mixed")
```

Replace the text requirement block (currently lines 45 and 58):

```python
    # Text requirement: nur wenn Preset Text erlaubt
    if preset.text_enabled:
        text_required = any(all_presets.get(pid) and all_presets[pid].has_text for pid in used_preset_ids)
        text_block = (
            "TEXT IST PFLICHT: Hat ein Preset Text-Slots, MUSST du diese befuellen. "
            "Lass KEINEN Text-Slot leer. Betrachte die Bilder und beschreibe ausfuehrlich, "
            "was du siehst — Landschaft, Stimmung, Farben, Details, Wetter."
        ) if text_required else ""
    else:
        text_block = ""

    # Style instructions
    style_block = ""
    if preset.generation_instructions:
        style_block = f"\nSTILVORGABE ({preset.name}): {preset.generation_instructions}\n"
```

Now update the return statement to use these blocks. Replace the existing `{... if text_required else ""}` section (remove the old inline ternary) and add `{style_block}` after "AUFGABE PRO SEITE:":

```python
    return f"""Du befuellst die Slots der gewaehlten Presets mit Bildern und ausfuehrlichem Text.

SEITENPLAN (preset_id pro Seite):
{plan_text}

VERWENDETE PRESETS (nur diese sind relevant):
{catalog}
{gpx_text}{notes_text}

{constraints}

{text_block}

AUFGABE PRO SEITE:{style_block}
1. Weise jedem Image-Slot ein Bild zu (image_index aus dem Plan).
2. Text-Rollen: title (stimmungsvoller Titel, 60 Z.), caption (ausfuehrliche Bildbeschreibung, max. 500 Z.), intro (detaillierte Einleitung, max. 1200 Z.).
3. Generiere AUSFUEHRLICHE, lebendige Texte — beschreibe Landschaft, Stimmung, Farben, Details, Wetter, was auf den Bildern zu sehen ist. Nutze die Zeichenlimits WIRKLICH aus.
{"4. JEDE Seite MUSS einen title-Slot haben: {{\"slot_id\": \"title\", \"text\": \"Einzeiliger Seitentitel\"}}" if preset.text_enabled else ""}
{"5. Bei Presets mit MEHREREN Bildern (quad_grid, double_stacked, triple_stacked): beschreibe den Gesamteindruck der Bildgruppe, nicht nur ein einzelnes Bild." if preset.text_enabled else ""}

BEISPIELE:
- cover_hero: [{{"preset_id": "cover_hero", "slots": [{{"slot_id": "title", "text": "Aufbruch im Morgengrauen"}}, {{"slot_id": "main", "image_index": 0}}]}}]
- single_text_below: [{{"preset_id": "single_text_below", "slots": [{{"slot_id": "title", "text": "Alpenwiese"}}, {{"slot_id": "main", "image_index": 1}}, {{"slot_id": "caption", "text": "Ein atemberaubender Weitblick ueber das Tal. Die Morgensonne taucht die gegenüberliegenden Berggipfel in warmes, goldenes Licht. In der Ferne sind vereinzelte Wanderer auf dem schmalen Gratweg zu erkennen, während unter uns die Nebelschwaden langsam aus dem Tal aufsteigen."}}]}}]
- double_stacked (KEIN Text): [{{"preset_id": "double_stacked", "slots": [{{"slot_id": "title", "text": "Aufstieg"}}, {{"slot_id": "top", "image_index": 3}}, {{"slot_id": "bottom", "image_index": 4}}]}}]
- image_text_split: [{{"preset_id": "image_text_split", "slots": [{{"slot_id": "title", "text": "Kapitel 1"}}, {{"slot_id": "image", "image_index": 2}}, {{"slot_id": "text", "text": "Nach drei Stunden stetigen Aufstiegs durch dichten Fichtenwald erreichten wir endlich die Baumgrenze. Vor uns erstreckte sich ein weites Hochplateau, übersät mit bunten Alpenblumen. Der Wind frischte auf und trug den Duft von wildem Thymian heran. Wir legten eine wohlverdiente Rast ein und genossen den ersten unverstellten Blick auf die gegenüberliegende Gipfelkette, deren schroffe Zacken sich scharf gegen den tiefblauen Himmel abzeichneten."}}]}}]

ANTWORTE NUR mit JSON-Array:"""
```

- [ ] **Step 4: Update `generate_photobook_pages` to accept and forward preset**

Change signature (line 76):

```python
def generate_photobook_pages(
    plan: Dict[str, Any],
    images: List[ImageData],
    gpx_stats: Optional[Dict[str, Any]],
    notes: Optional[str],
    model: str = "gemma4:26b-ctx128k",
    base_url: str = OLLAMA_BASE_URL,
    preset: PhotobookPreset = None,
) -> List[PageDescription]:
```

At the start of the function body, set default:

```python
    if preset is None:
        preset = get_photobook_preset("mixed")
```

Update the `_build_generate_prompt` call (line 87):

```python
    prompt = _build_generate_prompt(pages_plan, gpx_stats, notes, preset=preset)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_photobook_presets.py::TestGeneratePresetIntegration -v`
Expected: all 4 tests PASS

- [ ] **Step 6: Commit**

```bash
git add app/photobook/generate.py tests/test_photobook_presets.py
git commit -m "feat: wire photobook preset into page generation prompt"
```

---

### Task 6: Wire preset into the three node functions

**Files:**
- Modify: `app/nodes/select_photobook_images_node.py`
- Modify: `app/nodes/plan_photobook_node.py`
- Modify: `app/nodes/generate_photobook_node.py`

- [ ] **Step 1: Update `select_photobook_images_node.py`**

Add import:

```python
from app.photobook.presets import get_photobook_preset
```

After computing `photo_count`, add preset resolution (before the try block):

```python
    preset = get_photobook_preset(state.output_config.photobook_preset)
```

Update the `select_photobook_images` call to pass `preset`:

```python
        selected = select_photobook_images(
            images=state.images, gpx_stats=gpx_dict, notes=state.notes,
            model=state.model, photo_count=state.output_config.photobook.photo_count,
            preset=preset,
        )
```

- [ ] **Step 2: Update `plan_photobook_node.py`**

Add import:

```python
from app.photobook.presets import get_photobook_preset
```

Before the try block, add:

```python
    preset = get_photobook_preset(state.output_config.photobook_preset)
```

Update the `plan_photobook_layout` call:

```python
        plan = plan_photobook_layout(
            images=state.photobook_images, gpx_stats=gpx_dict, notes=state.notes,
            weather=state.weather, poi_list=state.poi_list, model=state.model,
            page_range=state.output_config.photobook.page_range,
            preset=preset,
        )
```

- [ ] **Step 3: Update `generate_photobook_node.py`**

Add import:

```python
from app.photobook.presets import get_photobook_preset
```

Before the `generate_photobook_pages` call, add:

```python
    preset = get_photobook_preset(state.output_config.photobook_preset)
```

Update the `generate_photobook_pages` call:

```python
        pages = generate_photobook_pages(
            plan=state.photobook_plan, images=state.photobook_images,
            gpx_stats=gpx_dict, notes=state.notes, model=state.model,
            preset=preset,
        )
```

- [ ] **Step 4: Verify nodes compile without errors**

Run: `uv run python -c "from app.nodes.select_photobook_images_node import select_photobook_images_node; from app.nodes.plan_photobook_node import plan_photobook_node; from app.nodes.generate_photobook_node import generate_photobook_node; print('All nodes loaded OK')"`
Expected: prints "All nodes loaded OK"

- [ ] **Step 5: Run full test suite to verify no regressions**

Run: `uv run pytest tests/ -v`
Expected: all existing tests still PASS

- [ ] **Step 6: Commit**

```bash
git add app/nodes/select_photobook_images_node.py app/nodes/plan_photobook_node.py app/nodes/generate_photobook_node.py
git commit -m "feat: wire photobook preset through node functions"
```
