# Calendar Rendering Fix — Design Spec

**Date:** 2026-05-19
**Status:** Draft
**Context:** Root cause analysis of black areas and layout overflow in photo calendar rendering

## Root Causes (Recap)

### Bug 1: Black areas instead of images (März, April, Mai, Juli)

`object-fit: cover` + centered crop on ALL images. When a photo's orientation mismatches the slot's aspect ratio, only a narrow center strip is visible. If that strip happens to be dark (shadow, water, night sky), the result is black.

Example: June bottom slot (cal_double_stacked, 5.7:1 ultra-wide) with a portrait image (3:4) → only 8% of image visible.

### Bug 2: Layout overflow (Juni)

`.calendar-page` uses `min-height: 210mm` instead of fixed `height`. Photobook uses `height: 297mm` (fixed) and works. Without a fixed container height, CSS Grid `fr` units can't resolve. Grid items with default `min-height: auto` expand to image intrinsic size, causing pages to grow 3× beyond intended height.

### Architectural weakness

No orientation-aware matching between images and slots. The month assigner picks images by index only — zero knowledge of whether a landscape or portrait photo fits a wide or tall slot.

---

## Design: Five-Layer Fix

### Layer 1: CSS Fix (immediate stability)

Two changes to `app/calendar/styles.css`:

```css
/* Change: min-height → fixed height */
.calendar-page {
    width: 297mm;
    height: 210mm;        /* was: min-height: 210mm */
    overflow: hidden;
}
```

```css
/* ADD: allow grid items to shrink within cells */
.image-area img,
.image-area .slot-placeholder {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
    min-height: 0;          /* NEW: overrides default min-height: auto */
    min-width: 0;           /* NEW: overrides default min-width: auto */
}
```

**Rationale:** Matches the photobook pattern exactly (fixed page height). The `min-height: 0` on grid items allows Chrome's print engine to properly constrain images within grid cells.

**Impact:** Fixes June overflow immediately. Does NOT fix black areas — that requires Layer 3.

### Layer 2: Slot Aspect Ratio Computation

Add `SlotDimensions` to `app/calendar/layouts.py`:

```python
@dataclass
class SlotDimensions:
    """Berechnete Slot-Maße aus dem CSS-Grid-Layout."""
    width_ratio: float    # relativ zu image-area
    height_ratio: float   # relativ zu image-area
    aspect_ratio: float   # width / height (>1 = breit, <1 = hoch)

def compute_slot_dimensions(preset_id: str) -> dict[str, SlotDimensions]
```

Pre-computed from the grid-template definitions. For each preset, parse the CSS grid spec and calculate what fraction of the `.image-area` each slot occupies.

Example for `cal_double_stacked`:
```
top slot:    1fr width (100%) × 2fr of 3fr height (66%)  → ratio = 2.9:1 (breit)
bottom slot: 1fr width (100%) × 1fr of 3fr height (33%)  → ratio = 5.7:1 (ultra-breit)
```

**Computation approach:** Hard-code a mapping dict (no CSS parser needed — 12 presets, stable). Read from the JSON preset's CSS grid specs:

```python
SLOT_ASPECT_RATIOS = {
    "cal_single_full":     {"img": (1.0, 1.0)},       # 1:1 grid → ~1.9:1 image area ratio
    "cal_double_side":     {"left": (0.5, 1.0), "right": (0.5, 1.0)},
    "cal_double_stacked":  {"top": (1.0, 0.667), "bottom": (1.0, 0.333)},
    "cal_triple_big_top":  {"big": (1.0, 0.667), "sl": (0.5, 0.333), "sr": (0.5, 0.333)},
    "cal_triple_row":      {"l": (0.333, 1.0), "m": (0.333, 1.0), "r": (0.333, 1.0)},
    # ... etc
}
```

Applied against the image area's actual dimensions (295mm × ~155mm with header and day grid subtracted).

### Layer 3: Orientation-Aware Image Matching

Modify `month_assigner.py` — both the LLM prompt and the fallback:

**LLM Prompt Enhancement:**
Add per-slot orientation constraints to the assignment prompt:
```
Slot-Orientierungen beachten:
- "wide" Slots (ratio > 1.5): bevorzuge Querformat-Fotos
- "tall" Slots (ratio < 0.67): bevorzuge Hochformat-Fotos
- "square" Slots (0.67 ≤ ratio ≤ 1.5): beide Formate ok

Verfügbare Fotos:
  0: IMG_5391.jpg (PORTRAIT, EXIF: 2025-07-15)
  1: IMG_5392.jpg (LANDSCAPE, EXIF: 2025-07-15)
  ...
```

The prompt now includes `(LANDSCAPE)` or `(PORTRAIT)` tags derived from EXIF or PIL metadata.

**Fallback Enhancement:**
In `_fallback_assignment()`, sort photos into landscape/portrait buckets first, then match:
```python
def _fallback_assignment(selected_photos, year):
    landscapes = [p for p in selected_photos if is_landscape(p)]
    portraits = [p for p in selected_photos if not is_landscape(p)]
    # Assign landscapes to wide slots, portraits to tall slots
```

**Orientation detection function** in `month_assigner.py`:
```python
def _get_orientation(img: ImageData) -> str:
    """Returns 'landscape', 'portrait', or 'square' from EXIF or PIL."""
    # Try EXIF orientation tag first (fast)
    # Fallback: PIL Image.open for actual dimensions
```

### Layer 4: Smart Image Cropping (object-position)

Add orientation-dependent `object-position` to the CSS or inline styles:

```python
# In renderer.py, when placing images:
def _get_object_position(slot_dimensions, image_orientation):
    """Bestimmt den object-position Wert basierend auf Slot-Format und Bild-Orientierung."""
    if slot_dimensions.aspect_ratio > 1.5 and image_orientation == "portrait":
        return "center 30%"    # bei Portrait in Breitslot: zeige oberen Teil
    elif slot_dimensions.aspect_ratio > 1.5:
        return "center center"  # Landscape in Breitslot: guter Fit
    elif slot_dimensions.aspect_ratio < 0.67 and image_orientation == "landscape":
        return "30% center"    # bei Landscape in Hochslot: zeige linken Teil
    else:
        return "center center"
```

Add `style="grid-area: X; object-position: ..."` to the `<img>` tags in `renderer.py`.

**Alternative (if `object-position` insufficient):** Pre-crop images with PIL to match slot aspect ratio before rendering. This gives full control but requires more processing. Keep as fallback strategy.

### Layer 5: Layout Validation

Add `app/calendar/validator.py` — lightweight validation that runs before PDF generation:

```python
def validate_calendar_html(html_content: str, year: int) -> list[str]:
    """Prüft das gerenderte HTML auf strukturelle Probleme.
    
    Checked:
    - Alle 13 Seiten vorhanden (Cover + 12 Monate)
    - Jede Seite hat genau einen image-area
    - Jede image-area hat die korrekte Anzahl img-Tags pro Preset
    - Keine slot-placeholder divs (indiziert fehlende Bilder)
    - Keine doppelten image_index-Werte innerhalb einer Seite
    """
```

Run as a post-render check in `pipeline.py`, log warnings for fixable issues.

---

## Architecture: New Data Flow

```
  images
    │
    ▼
  image_selector.py       (unverändert: LLM Batch-Auswahl)
    │
    ▼
  selected_images  ────────►  orientation detection (PIL/EXIF)
    │                              │
    ▼                              ▼
  month_assigner.py  ◄────  slot_dimensions (pre-computed)
    │                              │
    │    orientation-aware matching (LLM prompt + fallback)
    │
    ▼
  CalendarMonthPages (mit image_index + slot_id)
    │
    ▼
  renderer.py  ◄──── slot_dimensions (pre-computed)
    │                    image_orientations
    │
    │    HTML mit object-position inline-styles
    │    CSS: height: 210mm, min-height: 0 auf grid items
    ▼
  validator.py            (post-render check)
    │
    ▼
  pdf_generator.py        (unverändert)
```

### File changes at a glance

| File | Change | Layer |
|------|--------|-------|
| `app/calendar/styles.css` | `height: 210mm`, `min-height: 0` on grid items | Layer 1 |
| `app/calendar/layouts.py` | `SLOT_DIMENSIONS` dict, `SlotDimensions` dataclass | Layer 2 |
| `app/calendar/month_assigner.py` | `_get_orientation()`, enhanced prompt, orientation-aware fallback | Layer 3 |
| `app/calendar/renderer.py` | `object-position` inline styles per slot | Layer 4 |
| `app/calendar/validator.py` | NEW: structural HTML validation | Layer 5 |
| `app/calendar/pipeline.py` | Call validator after render, log warnings | Layer 5 |
| `tests/test_calendar/test_renderer.py` | Tests for object-position, orientation, dimensions | All |
| `tests/test_calendar/test_month_assigner.py` | Tests for orientation-aware matching | Layer 3 |

### Non-goals

- No LLM-based smart cropping (too expensive, too slow)
- No drag-and-drop image repositioning
- No dynamic `object-fit: contain` fallback (letterboxing looks bad for photos)
- No per-image aspect-ratio analysis beyond landscape/portrait/square

---

## Implementation Order

1. **Layer 1 (CSS fix)** — smallest change, highest impact. Fixes June overflow immediately.
2. **Layer 2 (slot dimensions)** — pure data, no side effects. Foundation for layers 3-4.
3. **Layer 3 (orientation matching)** — core logic change. Fixes black areas.
4. **Layer 4 (object-position)** — rendering enhancement. Improves visible crop placement.
5. **Layer 5 (validation)** — safety net. Catches regressions.

Each layer is independently testable and deployable. Layer 1 can ship alone as a hotfix.

---

## Testing Strategy

### Unit tests (Layer 1)
- `test_calendar_page_has_fixed_height`: CSS contains `height: 210mm` not `min-height`
- `test_grid_items_have_min_height_zero`: `.image-area img` has `min-height: 0`

### Unit tests (Layer 2)
- `test_slot_dimensions_for_all_presets`: Every slot in all 12 presets has a valid aspect ratio
- `test_double_stacked_top_slot_is_wide`: top slot ratio > 1.5
- `test_quad_big_left_right_slots_are_wide`: right slots ratio > 1.5

### Unit tests (Layer 3)
- `test_orientation_detection_landscape`: landscape image → "landscape"
- `test_orientation_detection_portrait`: portrait image → "portrait"
- `test_fallback_assigns_landscapes_to_wide_slots`: orientation matches slot shape
- `test_llm_prompt_includes_orientation_tags`: prompt contains (LANDSCAPE)/(PORTRAIT)

### Unit tests (Layer 4)
- `test_object_position_for_portrait_in_wide_slot`: gets "center 30%"
- `test_object_position_for_landscape_in_tall_slot`: gets "30% center"
- `test_renderer_output_contains_object_position`: HTML has inline object-position

### Integration tests
- `test_full_pipeline_orientation_matching`: end-to-end with mixed orientation images → no pure-black slots
- `test_pdf_page_height_is_constant`: all PDF pages are 297×210mm (no overflow)
- `test_no_slot_placeholders`: all slots filled with images (no fallback divs)

### Regression guard
- `test_existing_calendar_tests_still_pass`: all existing tests green after changes

---

## Risks & Mitigations

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| `height: 210mm` clips day grid on months with 6 week rows | Low | Day grid is flex-shrink: 0, measured at ~40mm. Image area gets remaining ~155mm. Should fit. |

| `object-position` values look wrong for some photos | Medium | Use conservative defaults (center center). Only apply offset for extreme mismatches (ratio > 2.0). |

| Orientation detection fails for EXIF-stripped images | Low | PIL open + get size always works. EXIF is optional optimization. |

| LLM ignores orientation hints in prompt | Medium | Fallback assignment handles this. LLM is best-effort. |
