# Photo Calendar Generation — Design Spec

**Date:** 2026-05-12
**Status:** Draft
**Project:** travel-agent-langgraph

## Overview

Add a photo calendar generation feature to the travel-agent-langgraph pipeline. The calendar has one page per month (12 pages + cover), landscape orientation, a fixed sequence of 12 image-aspect-ratio layouts, no text boxes, and exports as HTML and PDF. Code is shared with the existing photobook pipeline via a new `app/shared/` services layer.

## Architecture

### Integration Model: Separate Calendar Module with Shared Services

The calendar is a standalone module (`app/calendar/`) that shares core services with the photobook via `app/shared/`. This avoids coupling the calendar to the photobook's LangGraph StateGraph, prevents dead code paths, and allows each module to evolve independently.

### Shared Services Layer (`app/shared/`)

Code extracted from `app/photobook/` and made reusable:

| Component | Source | Purpose |
|---|---|---|
| `image_selector.py` | `app/photobook/image_selector.py` | Batch-based multimodal LLM image selection |
| `renderer_base.py` | `app/photobook/renderer.py` | HTML scaffolding, CSS injection, image compression |
| `pdf_generator.py` | `app/photobook/generate_pdf.py` | Headless Chrome CDP wrapper (`Page.printToPDF`) |
| `preset_loader.py` | `app/photobook/preset_loader.py` | JSON → Pydantic loader for layout presets |
| `styles_base.css` | `app/photobook/styles.css` | Shared print CSS basis (`@page`, reset, media queries) |

Photobook-specific code stays in `app/photobook/` (plan/generate nodes, validator, text generation, photobook-specific presets).

The shared `ImageSelector` is parameterized to accept `criteria: str` and `custom_instructions: str | None` instead of hardwired `PhotobookPreset.selection_criteria`.

### Calendar Module Structure (`app/calendar/`)

```
app/calendar/
├── pipeline.py           # Orchestrates the full flow (no LangGraph needed)
├── models.py             # CalendarConfig, CalendarPage, CalendarResult (Pydantic)
├── layouts.py            # 12 fixed landscape layouts + cover definition
├── preset_data/          # 12 JSON files defining the layouts
├── month_assigner.py     # LLM call: assign selected photos to months + slots
├── renderer.py           # HTML generation with day grid
├── day_grid.py           # Day grid logic (weekdays, CW, weekends)
└── styles.css            # Landscape-specific CSS
```

The calendar uses a **sequential pipeline without LangGraph** — a simple function call chain. No plan.py, no generate.py, no validator.py. The layout sequence is fixed, photo assignment is a single LLM call, and validation is unnecessary (no text to validate).

### Pipeline Flow

```
load_images  →  select_calendar_images  →  assign_months  →  render_calendar  →  generate_pdf  →  persist
  (existing)      (shared selector)         (LLM: 1 call)     (HTML + day grid)    (shared CDP)     (new service)
```

## Layout System

### Page Structure

Each month page in landscape orientation (~297×210mm) consists of:

1. **Month header** — dark bar with month name (German) and year
2. **Image area** (~60% height) — CSS Grid with image slots
3. **Day grid** (~40% height) — weekdays, calendar weeks, day numbers

### 12 Fixed Layouts

The layout sequence is fixed in `layouts.py`. One layout per month, all different:

| # | Month | Type | Images | Variant Description |
|---|-------|------|--------|---------------------|
| 0 | Cover | Single | 1 | Full-bleed image + year overlay, no day grid |
| 1 | Januar | Single | 1 | Full image, classic single-motive |
| 2 | Februar | Double | 2 | Side-by-side (equal split) |
| 3 | März | Triple | 3 | 1 large top + 2 small bottom |
| 4 | April | Quad | 4 | 2×2 grid (equal) |
| 5 | Mai | Triple | 3 | 3-column horizontal row |
| 6 | Juni | Double | 2 | Stacked (large top, small bottom) |
| 7 | Juli | Quad | 4 | 1 large left + 3 small right |
| 8 | August | Triple | 3 | 1+2 stacked vertically |
| 9 | September | Quad | 4 | Wide panorama + 3 below |
| 10 | Oktober | Triple | 3 | Asymmetric L-shape |
| 11 | November | Quad | 4 | 2 large + 2 small |
| 12 | Dezember | Single | 1 | Full image (mirrors cover) |

**Total: 1 cover + 12 pages = 30 image slots.**

Layout categories: Single (1 variant + cover), Double (2 variants), Triple (4 variants), Quad (4 variants) = 12 distinct layouts.

Layouts are defined as JSON files in `preset_data/` (like the photobook) with CSS grid areas for each image slot — but without text slots, char limits, or font sizes.

### Day Grid

- **Weekday row:** Mo Di Mi Do Fr Sa So (German abbreviations)
- **Calendar week column:** Leftmost column shows KW number per row
- **Weekends:** Saturday and Sunday columns highlighted (e.g. `#e74c3c`)
- **Today marker:** Optional, if the calendar year matches current year
- Implemented using Python's `calendar` stdlib module

## Image Selection & Month Assignment

### Two-Stage Flow

**Stage 1 — Coarse Selection (shared `image_selector.py`)**
- All uploaded photos batched (≤15 per batch) for multimodal LLM
- Selection criteria combined from preset + free-text field (e.g. "Nature & Landscape" + "prefer sunsets")
- Output: ~30–40 best photos (buffer for 30 slots)
- Fallback: evenly-spaced chronological selection

**Stage 2 — Month Assignment (`month_assigner.py`)**
- **Single LLM call** operating on photo metadata (filenames, EXIF dates, image indices), **not full base64 images** — this avoids token/context limits with 30+ photos
- Receives: the fixed layout sequence, seasonal expectations per month, preset criteria, and a list of selected photos with their EXIF dates and filenames
- Returns: per month → which photos (by index/ID) in which slots
- Thematic matching logic: "snow, winter vibes → Jan/Dec", "flowers, green → Apr/May", "sunset, beach → Jul/Aug"
- EXIF dates used as secondary signal — e.g. photos taken in July are preferred for summer months, but thematic fit takes priority
- Fallback: pure EXIF date-based assignment, then chronological order

```
50 photos → [Stage 1: Batch Selection] → ~35 photos → [Stage 2: Month Assignment] → 30 slots filled
```

The LLM decides which photos to discard if more than 30 are selected in Stage 1.

### Thematic Presets

Same four presets as photobooks (defined in `app/photobook/presets.py` or shared):

| Preset ID | Name | Prompt Fragment |
|-----------|------|-----------------|
| `mixed` | Mixed (default) | General-purpose selection |
| `nature_landscape` | Nature & Landscape | Landscape, outdoor, nature |
| `people` | People | Portraits, groups, human subjects |
| `culture` | Culture & Architecture | Buildings, cities, cultural sites |

### Free-Text Field

A `custom_instructions: str | None` field in the calendar config. Appended to the LLM prompt for both stages (e.g. "Bevorzuge Sonnenaufgänge", "Keine verschwommenen Bilder"). Exposed as a textarea in the frontend.

## Rendering

### HTML Output

All 13 pages in a single HTML document with `page-break-after: always` between pages.

```html
<div class="calendar-page landscape">
  <div class="month-header">
    <span class="month-name">Januar</span>
    <span class="year">2026</span>
  </div>
  <div class="image-area">
    <!-- CSS Grid with named areas per layout preset -->
  </div>
  <div class="day-grid">
    <div class="weekday-row"><span>KW</span><span>Mo</span>...<span>So</span></div>
    <!-- 5-6 week rows with day numbers -->
  </div>
</div>
```

### CSS

- `@page { size: A4 landscape; }` for PDF print
- Image area: CSS Grid with named areas per layout variant (same pattern as photobook presets, adapted for landscape)
- Day grid: `display: grid; grid-template-columns: 28px repeat(7, 1fr)`
- Image compression via `shared/renderer_base.py`

### PDF Generation

Headless Chrome CDP via `shared/pdf_generator.py`. Same `Page.printToPDF` approach with landscape `@page` directive.

## API & Frontend Integration

### API Routes

| Route | Method | Description |
|---|---|---|
| `/api/calendar/generate` | POST | Start calendar generation |
| `/api/calendar/{id}` | GET | Calendar details + status |
| `/api/calendar` | GET | List all calendars |
| `/api/calendar/{id}/html` | GET | HTML output |
| `/api/calendar/{id}/pdf` | GET | PDF download |

### Generate Payload

```json
{
  "image_ids": [1, 2, 3, "..."]},
  "preset": "nature_landscape",
  "year": 2026,
  "custom_instructions": "Bevorzuge Sonnenaufgänge und Nahaufnahmen"
}
```

### SSE Events

Progress streaming: `calendar_selecting_images → calendar_assigning_months → calendar_rendering → calendar_generating_pdf → calendar_complete`

### Frontend Components (Svelte 5)

- `CalendarPresetSelector.svelte` — Dropdown for thematic preset
- `CalendarYearSelector.svelte` — Year dropdown
- `CalendarInstructionsInput.svelte` — Free-text textarea
- `CalendarDetail.svelte` — Result view (HTML preview + download)
- `CalendarList.svelte` — List of generated calendars

The `pipelineStore` gets a `calendarMode` alongside existing blog/photobook modes.

### Database Tables

**`calendars` table:**
- `id` (PK)
- `preset` (string)
- `year` (int)
- `custom_instructions` (text, nullable)
- `html_path` (string)
- `pdf_path` (string)
- `status` (string: pending/running/complete/error)
- `created_at` (datetime)

**`calendar_images` table:**
- `id` (PK)
- `calendar_id` (FK → calendars.id)
- `image_id` (FK → images.id)
- `month_index` (int, 0=cover, 1–12)
- `slot_index` (int, position within the month's layout)

## Testing

- Unit tests for `day_grid.py` (calendar calculations, weekday names, CW logic)
- Unit tests for `layouts.py` (all 12 layouts load, correct slot counts)
- Unit tests for `month_assigner.py` (LLM output parsing, fallback assignment)
- Integration tests for full pipeline with small photo sets (max 50)
- Same pytest markers: `unit`, `integration`, `e2e`
- Test photos in `tests/fixtures/` (reuse existing or add calendar-specific)

The image selection algorithm must be robust for larger photo sets (hundreds of images). The batch-based approach from the shared `image_selector.py` already handles this — batches of 15 are processed independently, then results are merged.

## Non-Goals

- No text boxes or captions on images
- No LLM layout planning (sequence is fixed)
- No variety validation (no text to validate)
- No GPX, weather, POI, or tour note processing
- No table view / list view for the calendar (only the monthly page view)
- No print dialog customization beyond `@page` CSS
- No iCal/ICS export
- No drag-and-drop reordering of photos or months

## Error Handling & Fallbacks

- **Image selection failure:** Fallback to evenly-spaced chronological selection
- **Month assignment failure:** Fallback to EXIF date-based assignment, then chronological
- **PDF generation failure:** HTML output still available; error reported via SSE
- **Empty photo set:** Return error immediately, no pipeline execution

## Implementation Order

1. Extract `app/shared/` from photobook (image_selector, renderer_base, pdf_generator, preset_loader)
2. Implement `app/calendar/layouts.py` + 12 JSON presets + `styles.css`
3. Implement `app/calendar/day_grid.py`
4. Implement `app/calendar/models.py` (config + result models)
5. Implement `app/calendar/month_assigner.py` (LLM assignment call)
6. Implement `app/calendar/renderer.py` (HTML assembly)
7. Implement `app/calendar/pipeline.py` (orchestration)
8. Add `app/db/models.py` calendar tables + repository
9. Add API routes + SSE events
10. Add frontend components
11. End-to-end integration testing
