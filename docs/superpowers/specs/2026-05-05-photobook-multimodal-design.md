# Design: Multimodale Photopuch-Pipeline

**Datum:** 2026-05-05
**Status:** approved
**Kontext:** Captions fehlen, Layout-Qualität unzureichend — LLM-Pässe sind text-only

## Problem

Pass 1 (`plan.py`) und Pass 2 (`generate.py`) sind rein text-basiert. Das LLM sieht keine Bilder und kann daher weder sinnvolle Layout-Entscheidungen treffen noch Bildbeschreibungen generieren. Resultat: leere Seiten, fehlende Captions, monotone Template-Wahl.

## Ziel

Beide LLM-Pässe multimodal machen (Bilder als Base64 an Ollama senden). Zusätzlich Seitentitel/Mottos als neues Template-Feature einführen.

## Entscheidungen

| Entscheidung | Gewählte Option |
|---|---|
| Welche Pässe multimodal? | Pass 1 + Pass 2 (B) |
| Batching? | Alle Bilder in einem Call (B) — max 20 Bilder passen in 128k Kontext |
| Modell? | Globales Modell aus AppState (A) — gleiche Auswahl wie Blog |
| Seitentitel? | Ja, als neuer optionaler `title`-Slot in Templates |

## Änderungen

### 1. `app/utils/image_utils.py` — `encode_image_base64()` hinzufügen

Extrahiert aus `image_selector.py:_encode_image()`. Thumbnail max 600px, JPEG Q=60, Base64-Encoding.

```python
def encode_image_base64(image_path: str, max_size: int = 600) -> str | None:
```

### 2. `app/photobook/plan.py` — Pass 1 multimodal

- `_encode_images()`: Alle Bilder als Base64 encoden
- `_build_plan_prompt()`: unverändert (Text-Prompt bleibt gleich)
- `plan_photobook_layout()`: Bilder als `"images"`-Array im Ollama-Request mitsenden
- Ollama-Request-Format wechselt von reinem Text zu multimodal (`"images"` key)
- Output-Format (JSON mit `pages` + `dramatic_arc`) bleibt gleich
- Fallback-Plan bleibt unverändert (greift bei LLM-Fehlern)

### 3. `app/photobook/generate.py` — Pass 2 multimodal

- `_encode_images()`: Alle Bilder als Base64 encoden
- `_build_generate_prompt()`: Prompt um Caption- und Title-Anweisungen erweitert
- `generate_photobook_pages()`: Bilder als `"images"`-Array mitsenden
- Neuer Prompt-Teil: "Generiere für jede Seite einen kurzen, stimmungsvollen Titel (2-5 Wörter, Deutsch). Generiere für jedes Bild eine aussagekräftige Bildunterschrift (1 Satz, sachlich, Deutsch)."
- Output-Format erweitert: `title`-Feld pro Seite, `caption`-Feld pro Slot

### 4. Templates — `title`-Slot hinzufügen

Jedes der 8 Template-JSONs erhält einen optionalen `title`-Slot:

```json
{"id": "title", "type": "text", "css_area": "title", "optional": true}
```

CSS-Grid wird um `"title"`-Area erweitert.

### 5. `app/photobook/renderer.py` — Title-Rendering

Title-Slot wie Text-Slot rendern, aber mit eigener CSS-Klasse:
```html
<div class="slot-title" style="grid-area: title">...</div>
```

### 6. `app/photobook/styles.css` — Title-Styling

```css
.slot-title {
  font-size: 14pt;
  font-weight: bold;
  color: #222;
  padding: 4mm;
}
```

### 7. `app/services/image_selector.py` — Refactoring

`_encode_image()` durch Import aus `app.utils.image_utils` ersetzen (optional, reduziert Duplizierung).

## Tests

### Anzupassen
- `test_plan.py` — Mock muss multimodal response erwarten
- `test_generate.py` — Mock muss multimodal response erwarten
- `test_renderer.py` — Tests für Title-Slot
- `test_template_loader.py` — Tests für neue Title-Slots

### Neu
- `test_image_utils.py` — `test_encode_image_base64`
- Integrationstest für multimodale Pipeline (mit Mock)

## Risiken

- **Mittel:** Grössere Änderung an LLM-Interfaces — Mocks müssen angepasst werden
- **Gering:** Template-Änderungen — backwards-kompatibel (Title ist optional)
- **Gering:** Base64-Encoding — bereits in Blog-Pipeline bewährt
