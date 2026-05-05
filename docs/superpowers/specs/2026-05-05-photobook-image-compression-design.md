# Design: Bildkompression für Photopuch

**Datum:** 2026-05-05
**Status:** approved
**Kontext:** Bugfixing — Subtask A aus Photopuch-Root-Cause-Analyse

## Problem

Das Photopuch-PDF ist extrem langsam zu öffnen und rendern, selbst auf High-End-Hardware. Ursache: Original-Bilder werden in voller Auflösung (potenziell 20MP, 15MB pro Bild) via `file://` URI in das HTML eingebettet und von Headless Chrome ins PDF gerendert. Es existiert keinerlei Bildkompression im Photopuch-Pfad.

Die Blog-Pipeline hat hingegen `compress_image_to_jpeg()` in `app/services/blog_generator.py`, die Bilder auf max 1200px skaliert und auf ≤1MB komprimiert.

## Ziel

Bildkompression (identisch zur Blog-Pipeline) in den Photopuch-Pfad einbauen: max 1200px längste Seite, ≤1MB pro Bild, JPEG/RGB-Konvertierung, EXIF-Transpose.

## Entscheidungen

| Entscheidung | Gewählte Option | Begründung |
|---|---|---|
| Code-Wiederverwendung | Shared Utility `app/utils/image_utils.py` | DRY, beide Pipelines profitieren, saubere Architektur |
| Kompressions-Zeitpunkt | Im `render_photobook_node` vor Renderer-Aufruf | Trennung von Concerns: Node = Orchestrierung, Renderer = reines HTML |
| Kompressions-Parameter | 1200px / 1MB (wie Blog) | Bewährt, konsistent, ausreichend für A4-Druck |

## Architektur

```
app/utils/image_utils.py          [NEU]  ← shared utility
       ↑                    ↑
       │                    │
app/services/          app/nodes/
blog_generator.py      render_photobook_node.py
```

## Änderungen

### 1. Neue Datei: `app/utils/image_utils.py`

Extrahiert `compress_image_to_jpeg()` aus `blog_generator.py`. Die Funktion:
- Resized auf max 1200px (längste Seite) mit LANCZOS
- RGB-Konvertierung (JPEG unterstützt kein Alpha)
- EXIF-Transpose (korrekte Orientierung)
- Iterative JPEG-Qualitätsreduktion (85 → 10) bis ≤1MB
- Weitere Grössenreduktion (75% Schritte) falls nötig
- Fallback: 200px, JPEG Q=10
- Gibt Pfad zur Ausgabedatei zurück oder None bei Fehler

### 2. Änderung: `app/services/blog_generator.py`

- `compress_image_to_jpeg()` entfernen (Zeilen 70–134)
- Import hinzufügen: `from app.utils.image_utils import compress_image_to_jpeg`
- Alle internen Aufrufe bleiben unverändert (Signatur identisch)

### 3. Änderung: `app/nodes/render_photobook_node.py`

Vor `render_photobook()`-Aufruf:
- Output-Verzeichnis erstellen: `output/photobook_<ts>/images/`
- Für jedes Bild in `state.photobook_images`:
  1. `compress_image_to_jpeg(original_path, output_dir / f"{idx:02d}_{basename}.jpg")`
  2. Neues `ImageData(path=compressed_path, ...)` erstellen
- Komprimierte `ImageData`-Liste an `render_photobook()` übergeben
- Originale bleiben unverändert

### 4. Unverändert

- `app/photobook/renderer.py` — bekommt bereits komprimierte Pfade
- `app/photobook/generate_pdf.py`
- Alle anderen Photopuch-Module

## Tests

### Neue Datei: `tests/test_photobook/test_image_compression.py`

- `test_compress_image_to_jpeg_reduces_size`: Bild wird kleiner als Original
- `test_compress_image_to_jpeg_max_dim`: Maximal-Dimension ≤ 1200px
- `test_compress_image_to_jpeg_rgb_output`: Output ist RGB
- `test_compress_image_to_jpeg_exif_transpose`: EXIF-Orientierung korrigiert
- `test_render_node_compresses_images`: `render_photobook_node` erzeugt komprimierte Kopien
- `test_render_node_preserves_originals`: Originale bleiben unverändert
- `test_blog_compression_still_works`: Blog-Pipeline funktioniert nach Refactoring

### Bestehende Tests

- `tests/test_photobook/test_renderer.py` — muss weiterhin grün sein
- `tests/test_photobook/test_pdf.py` — muss weiterhin grün sein
- Alle Blog-Tests — müssen nach Refactoring grün sein

## Abhängigkeiten

- `PIL` (Pillow) — bereits in `pyproject.toml`
- Keine neuen Abhängigkeiten

## Risiken

- **Gering:** Refactoring von `blog_generator.py` — durch Tests abgesichert
- **Gering:** Pfad-Management im Node — Output-Verzeichnis muss vor Kompression existieren
