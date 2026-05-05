# Design: Validator + Fallback-Logik + Bildanzahl für Photopuch

**Datum:** 2026-05-05
**Status:** approved
**Kontext:** Bugfixing — Subtask C aus Photopuch-Root-Cause-Analyse

## Problem

1. **Alle Seiten erhalten gleiches Layout:** Wenn der LLM Pass 2 fehlschlägt oder der Validator Fehler findet, werden alle Seiten zu `grid_2x2` degradiert. `enforce_fallback()` löscht zudem alle Captions.
2. **Zu viele Bilder:** `photo_count` ist zu hoch (20/14/26), bei der Seitenanzahl (14-18) führt das zu überfüllten Templates.

## Ziel

1. Fallback-Logik differenzieren: Pass-1-Kategorien für Template-Auswahl nutzen, Validator repariert minimal statt alles zu `grid_2x2` zu machen, Captions bleiben erhalten.
2. Bildanzahl auf realistische Werte reduzieren.

## Entscheidungen

| Entscheidung | Gewählte Option |
|---|---|
| `photo_count` | Reduzieren: 12/16/20 (short/normal/detailed) |
| `enforce_fallback()` | Minimale Reparatur statt Template-Austausch |
| LLM-Fallback (`generate.py`) | Kategorie-basierte Template-Auswahl aus Pass 1 |

## Änderungen

### 1. `app/state.py` — `PHOTOBOOK_SIZE_MAP`

**Vorher:**
```python
PHOTOBOOK_SIZE_MAP = {
    "short":    {"photo_count": 14, "page_range": "8-12"},
    "normal":   {"photo_count": 20, "page_range": "14-18"},
    "detailed": {"photo_count": 26, "page_range": "20-24"},
}
```

**Nachher:**
```python
PHOTOBOOK_SIZE_MAP = {
    "short":    {"photo_count": 12, "page_range": "8-12"},
    "normal":   {"photo_count": 16, "page_range": "14-18"},
    "detailed": {"photo_count": 20, "page_range": "20-24"},
}
```

### 2. `app/photobook/validator.py` — `enforce_fallback()` minimal-repair

Neue Logik:
- **Template existiert nicht** → nächstes Template gleicher Kategorie aus Katalog wählen
- **Falsche Slot-IDs** → korrigieren (reparieren statt verwerfen)
- **Zu viele Bilder** → überzählige droppen
- **Zu wenige Bilder** → Template mit passender Bildanzahl wählen
- **Captions bleiben erhalten** — werden in die reparierten Slots übernommen

### 3. `app/photobook/generate.py` — Fallback nutzt Pass-1-Kategorien

Die Fallback-Logik (Zeilen 87-91) nutzt jetzt die Template-Kategorie aus `plan_page`:

| Kategorie | Default-Template |
|-----------|-----------------|
| hero | hero_single |
| split | split_equal |
| grid | grid_2x2 |
| strip | strip_3 |
| mixed | image_text_left |
| collection | collection_3 |

Slot-IDs werden aus dem gewählten Template abgeleitet, nicht hartkodiert auf `["tl", "tr", "bl", "br"]`.

## Tests

### Anzupassen
- `test_state.py::TestApplyPhotobookSize` — Erwartungswerte an neue `photo_count` anpassen
- `test_photobook/test_graph.py::test_select_images_node` — Erwartungswert auf 16 (normal) anpassen

### Neu
- `test_validator.py` — Test für Caption-Erhalt bei `enforce_fallback()`
- `test_validator.py` — Test für Template-Erhalt bei korrigierbaren Fehlern
- `test_generate.py` — Test für kategorie-basierten Fallback

## Risiken

- **Gering:** Bestehende Tests müssen an neue `photo_count`-Werte angepasst werden
- **Gering:** `enforce_fallback()`-Änderung — durch umfangreiche Validator-Tests abgesichert
