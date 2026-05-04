# Enriched Map Generation — Design Spec

**Date:** 2026-05-04
**Status:** Approved

## Overview

Enhance the map image included in the final blogpost to also display:
1. Positions of breaks (pauses) detected in the GPX analysis step
2. Positions of all images selected for the final blogpost (after review_content)

The basic map (route only) remains in the pipeline early for frontend progress display.
A new enriched map node is added after `review_content`, immediately before `generate_blog_post`.

## Pipeline Change

```
process_gpx → load_images → extract_metadata → clustering → generate_map (basic, unchanged)
    → load_notes → enrich_weather → enrich_poi → select_images → review_content
    → generate_enriched_map (NEW) → generate_blog_post → design → persist → [pdf]
```

## Files Changed

### New Files

| File | Purpose |
|------|---------|
| `app/nodes/generate_enriched_map.py` | Node: reads state, calls service, stores result in metadata |
| `tests/test_services/test_generate_enriched_mapimage.py` | Service unit tests |
| `tests/test_nodes/test_generate_enriched_map.py` | Node unit tests |

### Modified Files

| File | Change |
|------|--------|
| `app/services/generate_mapimage.py` | Add `generate_enriched_map_html(points, pauses, images, output_html)` function |
| `app/graph.py` | Import new node, add to `NODE_NAMES`, wire edge: `review_content → generate_enriched_map → generate_blog_post` |
| `app/nodes/generate_blogpost.py` | Line 31: read `state.metadata.get("enriched_map_image_path")` instead of `"map_image_path"` |
| `tests/test_graph/test_pipeline_e2e.py` | Assert `enriched_map_image_path` is set in metadata |

### Unchanged Files

- `app/state.py` — no new fields needed (uses existing `metadata` dict)
- `app/nodes/generate_map.py` — untouched
- `app/services/blog_generator.py` — untouched (already accepts `map_image_path` generically)
- All other nodes and services

## Detailed Spec

### 1. Service: `generate_enriched_map_html()`

**Signature:**
```python
def generate_enriched_map_html(
    points: List[TrackPoint],
    pauses: List[dict],
    images: List[ImageData],
    output_html: str,
) -> None:
```

**Behavior:**
- Same folium setup as existing `generate_map_html`: OpenTopoMap tiles, bounding box with 500m padding, auto-fit bounds
- Route polyline (reuses existing logic)
- Start marker (green) + End marker (red) — same as existing
- **Pause markers:** Orange `fa-pause` icon marker at each pause location with tooltip `"Pause: {duration} min"` and popup with time range
- **Image markers:** Blue `fa-camera` icon marker at each image location with tooltip `"Bild {n}: {timestamp}"`, where `n` is the 1-based index within `selected_images`
- Saves HTML file via `m.save(output_html)`

**Edge cases:**
- `pauses` is empty → no pause markers, map still renders
- `images` is empty → no image markers, map still renders
- Both empty → functionally identical to basic map

### 2. Node: `generate_enriched_map_node()`

**Signature:**
```python
def generate_enriched_map_node(state: AppState) -> AppState:
```

**Behavior:**
- If `state.gpx_stats` is None or no points → log warning, return state unchanged
- Creates `output/` directory if needed
- Generates `output/enriched_map.html` via `generate_enriched_map_html()`
- Converts to PNG via existing `html_to_png()` → `output/enriched_map.png`
- Stores `state.metadata["enriched_map_image_path"] = "output/enriched_map.png"`
- Returns state

### 3. Graph Wiring

**`NODE_NAMES`** addition:
```python
"generate_enriched_map": "Angereicherte Karte generieren",
```

**Edges:**
- Remove: `builder.add_edge("review_content", "generate_blog_post")`
- Add: `builder.add_edge("review_content", "generate_enriched_map")`
- Add: `builder.add_edge("generate_enriched_map", "generate_blog_post")`

### 4. Blog Generator Change

In `app/nodes/generate_blogpost.py`, line 31:
```python
# Old:
map_image_path = state.metadata.get("map_image_path")
# New:
map_image_path = state.metadata.get("enriched_map_image_path")
```

No service changes needed. `generate_blog_post()` copies the path to `./images/00_map.png` generically.

### 5. Data Flow

```
state.gpx_stats.points ──────┐
state.gpx_pauses ────────────┤──→ generate_enriched_map_node ──→ state.metadata["enriched_map_image_path"]
state.selected_images ───────┘                                              │
                                                                           ▼
                                                              generate_blog_post_node
                                                              (uses enriched map as 00_map.png)
```

### 6. Testing

#### Service Tests (`test_generate_enriched_mapimage.py`)
- `test_generates_html_with_pause_markers` — pauses produce orange markers with duration tooltip
- `test_generates_html_with_image_markers` — images produce blue markers with timestamp tooltip
- `test_handles_empty_pauses` — no pause markers, no crash
- `test_handles_empty_images` — no image markers, no crash
- `test_html_contains_leaflet` — valid folium/leaflet output

#### Node Tests (`test_generate_enriched_map.py`)
- `test_skips_when_no_gpx_stats` — returns state unchanged, no metadata key
- `test_generates_enriched_map_with_mocked_services` — mocks service calls, verifies `enriched_map_image_path` set

#### Graph E2E Test Update
- Add assertion: `assert result["metadata"].get("enriched_map_image_path") is not None`

### 7. Marker Design Details

| Marker Type | Icon | Color | Tooltip | Popup |
|------------|------|--------|---------|-------|
| Start | `fa-flag` | green | "Start" | — |
| End | `fa-flag-checkered` | red | "Ende" | — |
| Pause | `fa-pause` | orange | `"Pause: {dauer} min"` | `"{start} – {end}"` |
| Image | `fa-camera` | blue | `"Bild {n}: {timestamp}"` | `"({lat:.4f}, {lon:.4f})"` |
