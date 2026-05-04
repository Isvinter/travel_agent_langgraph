# Statische angereicherte Karte mit "Foto X"-Labels — Design Spec

**Date:** 2026-05-04
**Status:** Draft

## Overview

Die angereicherte Karte (`generate_enriched_map`) wird von interaktiven Folium-Markern (Tooltips/Popus) auf rein statische DivIcon-Marker umgestellt. Jedes ausgewählte Foto bekommt eine permanente Nummer ("Foto 1", "Foto 2", …), die sowohl auf der Karte als Label neben dem Kamera-Icon als auch im Blogpost in der Bildunterschrift erscheint. Fotos an derselben Position werden gruppiert. Pausen-Marker zeigen zugeordnete Fotonummern, falls Fotos räumlich (50m) UND zeitlich (während der Pause) zur Pause gehören.

Die HTML- und PDF-Ausgabe des Blogposts bleiben visuell identisch — die Karte ist ein statisches PNG ohne JavaScript-Abhängigkeiten.

## Pipeline

Keine Änderung. `generate_enriched_map` läuft weiterhin nach `review_content` und vor `generate_blog_post`:

```
review_content → generate_enriched_map → generate_blog_post → design → persist → [pdf]
```

## Files Changed

| File | Change |
|------|--------|
| `app/services/generate_mapimage.py` | **Hauptänderung.** Drei neue Hilfsfunktionen. `generate_enriched_map_html()`: DivIcon-Marker mit permanenten Labels, Foto-Gruppierung (5m), Pause-Foto-Zuordnung (50m + zeitlich). Entfernen von Tooltips/Popus an Foto- und Pause-Markern. |
| `app/nodes/generate_enriched_map.py` | Leichte Anpassung: `selected_images`-Liste in voller Länge an Service durchreichen (inkl. Indizes). |
| `app/services/blog_generator.py` | Prompt-Änderung in `construct_blog_post_prompt()`: LLM anweisen, "Foto X: Beschreibung"-Format für Tour-Fotos zu nutzen. Karte und Höhenprofil ohne Prefix. |
| `app/services/design_blogpost.py` | Keine Änderung nötig. `_add_image_captions()` extrahiert alt-Text bereits als `<figcaption>`. |

### Unchanged Files

- `app/state.py` — keine neuen Felder
- `app/graph.py` — keine Pipeline-Änderung
- `app/nodes/generate_map.py` — unverändert (Basis-Karte)
- Alle anderen Nodes und Services

## Detailed Spec

### 1. Neue Hilfsfunktionen (`generate_mapimage.py`)

```python
def _haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distanz in Metern zwischen zwei Koordinaten (Haversine-Formel)."""
```

```python
def _group_photos_by_location(
    images: list[ImageData], threshold_m: float = 5.0
) -> list[list[int]]:
    """Gruppiert Fotos nach räumlicher Nähe (threshold_m).
    Rückgabe: Liste von Gruppen, jede Gruppe = Liste von 0-basierten Indizes in `images`.
    Beispiel: [[0, 2], [1], [3, 4, 5]] → Fotos 0+2 am gleichen Ort, Foto 1 einzeln, Fotos 3+4+5 am gleichen Ort.
    
    Algorithmus: Greedy — jedes Foto wird der ersten Gruppe zugeordnet,
    zu deren Zentrum die Distanz <= threshold_m ist. Sonst neue Gruppe.
    """
```

```python
def _match_photos_to_pauses(
    images: list[ImageData],
    pauses: list[dict],
    distance_m: float = 50.0,
) -> dict[int, list[int]]:
    """Ordnet Fotos Pausen zu.
    Kriterien (beide müssen erfüllt sein):
      1. Haversine-Distanz Foto↔Pause <= distance_m (50m)
      2. Foto-Timestamp liegt zwischen Pausen-Start und Pausen-Ende
    
    Rückgabe: {pause_index: [foto_index, ...]}
    Nur Pausen mit mindestens einem zugeordneten Foto erscheinen im Dict.
    """
```

### 2. `generate_enriched_map_html()` — geänderte Marker-Logik

**Signatur bleibt:**
```python
def generate_enriched_map_html(
    points: list[TrackPoint],
    pauses: list[dict],
    images: list[ImageData],
    output_html: str,
) -> None:
```

**Ablauf:**

1. **Bounding Box, Tiles, PolyLine, Start/Ende** — unverändert wie bisher (OpenTopoMap, grüne Start-Flagge, rote Ziel-Flagge, Route als PolyLine).

2. **Foto-Gruppierung:** `_group_photos_by_location(images, threshold_m=5.0)` aufrufen.

3. **Pause-Foto-Zuordnung:** `_match_photos_to_pauses(images, pauses, distance_m=50.0)` aufrufen.

4. **Foto-Marker (DivIcon):**
   - Für jede Gruppe aus Schritt 2 einen Marker setzen.
   - Label-Format bei einem Foto: `<i class="fa fa-camera" style="color:#1a73e8;"></i> <b>Foto {n}</b>`
   - Label-Format bei mehreren Fotos: `<i class="fa fa-camera" style="color:#1a73e8;"></i> <b>Fotos {n}, {m}, {o}</b>`
   - `n, m, o` sind 1-basierte Indizes aus `images` (entspricht `state.selected_images`).
   - `DivIcon`-Parameter: `icon_size=(200, 40)` (großzügig, Text läuft nicht über), `icon_anchor=(0, 20)`, `html=...`
   - **Keine** Tooltips, **keine** Popups.

5. **Pause-Marker (DivIcon):**
   - Für jede Pause einen DivIcon-Marker setzen (kein separates Icon + DivIcon).
   - Basis-HTML: `<i class="fa fa-pause" style="color:#f39c12;"></i> <b>Pause ({dauer}min)</b>`
   - Falls `_match_photos_to_pauses()` Fotos für diese Pause liefert:
     - HTML erweitern: `<i class="fa fa-pause" style="color:#f39c12;"></i> <b>Pause ({dauer}min)</b> <span style="color:#1a73e8;font-size:11px;">Fotos {n}, {m}</span>`
   - **Keine** Tooltips, **keine** Popups an Pause-Markern.

6. **HTML speichern:** `m.save(output_html)` wie bisher.

### 3. Node: `generate_enriched_map_node()`

**Signatur unverändert:**
```python
def generate_enriched_map_node(state: AppState) -> AppState:
```

**Änderung:** Beim Aufruf von `generate_enriched_map_html()` wird `state.selected_images` als `images`-Parameter übergeben. Die 1-basierte Nummerierung auf der Karte entspricht der Position in dieser Liste (Index 0 → Foto 1, Index 1 → Foto 2, …).

PNG-Screenshot via `html_to_png()` unverändert.

### 4. Blog Generator Prompt (`blog_generator.py`)

**Aktueller Prompt-Ausschnitt (sinngemäß):**
```
- Nutze für Bilder EXAKT folgendes Format: ![Deine Beschreibung](pfad/zum/bild)
```

**Neuer Prompt-Ausschnitt:**
```
- Nutze für Tour-Fotos EXAKT folgendes Format: ![Foto X: Deine Beschreibung](pfad/zum/bild)
  Die Nummer X entspricht der Position in der Bildliste. Auf der Übersichtskarte
  findest du jedes Foto mit dem Label "Foto X" am Aufnahmeort eingezeichnet.
- Karte und Höhenprofil werden OHNE "Foto X:"-Prefix eingebettet:
  ![Routenverlauf der Tour](pfad/zur/karte.png)
  ![Höhenprofil der Tour](pfad/zum/hoehenprofil.png)
```

Die komprimierten Bilddateien heißen `01_name.jpg`, `02_name.jpg` usw. — der LLM kann durch die Dateinamen die korrekte Nummer zuordnen.

### 5. Blog Design (`design_blogpost.py`)

Keine Änderung. `_add_image_captions()` extrahiert den alt-Text aus `<img alt="Foto 1: Blick auf den See" src="...">` und setzt ihn als `<figcaption>Foto 1: Blick auf den See</figcaption>`. Funktioniert automatisch mit dem neuen Format.

### 6. HTML/PDF-Konsistenz

Die Karte ist ein statisches PNG ohne JavaScript. Sowohl HTML als auch PDF binden dieselbe PNG-Datei ein. Die visuelle Ausgabe ist identisch. Keine separaten Render-Pfade nötig.

### 7. Marker Design Summary

| Marker-Typ | Icon/Inhalt | Farbe | Label |
|---|---|---|---|
| Start | `fa-flag` | grün | — |
| Ende | `fa-flag-checkered` | rot | — |
| Pause | `fa-pause` | orange | `Pause (Dauer)` + ggf. `Fotos n, m` |
| Foto (einzeln) | `fa-camera` | blau (#1a73e8) | `Foto n` |
| Foto (Gruppe) | `fa-camera` | blau (#1a73e8) | `Fotos n, m, o` |

### 8. Edge Cases

- `images` leer → keine Foto-Marker, Karte zeigt nur Route + Start/Ende + Pausen
- `pauses` leer → keine Pause-Marker, keine Pause-Foto-Zuordnung
- Kein Foto hat gültige Koordinaten → keine Foto-Marker (wie bisher)
- Kein Foto liegt innerhalb einer Pause (räumlich+zeitlich) → Pausen ohne Foto-Label
- Alle Fotos am exakt gleichen Ort → ein einziger gruppierter Marker mit allen Nummern
- Foto-Timestamp ohne Pause → wird nicht zugeordnet (auch wenn räumlich nah)

### 9. Testing

#### Service Tests (anpassen/erweitern)

- `test_haversine_distance` — korrekte Distanzberechnung
- `test_group_photos_by_location_single` — einzelnes Foto → eine Gruppe
- `test_group_photos_by_location_clustered` — nahe Fotos gruppiert, entfernte getrennt
- `test_group_photos_by_location_threshold` — Fotos genau an der 5m-Grenze
- `test_match_photos_to_pauses_spatial_and_temporal` — beide Kriterien erfüllt
- `test_match_photos_to_pauses_spatial_only` — nur räumlich nah, zeitlich außerhalb → keine Zuordnung
- `test_match_photos_to_pauses_temporal_only` — nur zeitlich in Pause, räumlich weit → keine Zuordnung
- `test_divicon_foto_marker_format` — Marker-HTML enthält "Foto n" bzw. "Fotos n, m"
- `test_divicon_pause_marker_format` — Pause-Marker enthält "Fotos n" wenn zugeordnet
- `test_no_tooltips_on_foto_markers` — keine Tooltips/Popus an Foto-Markern
- `test_no_tooltips_on_pause_markers` — keine Tooltips/Popus an Pause-Markern

#### Blog Generator Tests

- `test_prompt_contains_foto_x_format` — Prompt enthält "Foto X:"-Anweisung
- `test_prompt_excludes_foto_prefix_for_map` — Karte/Höhenprofil ohne "Foto X:"-Prefix

#### Node Tests (anpassen)

- Bestehende Tests für `generate_enriched_map_node` prüfen weiterhin dass `enriched_map_image_path` gesetzt wird

### 10. Abgrenzung zu bestehendem Spec

Dieser Spec ersetzt die Marker-Details aus `2026-05-04-enriched-map-design.md`:
- Tooltips und Popups werden **entfernt** (statt eingeführt)
- `folium.Icon` für Fotos wird durch `folium.DivIcon` mit permanenten Text-Labels ersetzt
- Neue Hilfsfunktionen für Gruppierung und Pause-Zuordnung
- Blog-Prompt für "Foto X:"-Format
