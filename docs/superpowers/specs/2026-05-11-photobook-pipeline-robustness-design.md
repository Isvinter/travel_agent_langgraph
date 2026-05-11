# Spec: Photobook-Pipeline Robustness Refactor

**Datum**: 2026-05-11
**Branch**: `photobook-pipeline-robustness` (via git worktree)
**Status**: Draft → Review

---

## Problem

Die aktuelle Photobook-Pipeline leidet unter Kontext-Überlastung der LLMs, insbesondere in Pass 2 (Content-Generierung). Alle 16–20 base64-codierten Bilder werden in einem einzigen Ollama-Call gesendet, was bei 128K-Kontextfenstern zu Truncation, fehlenden Bildbeschreibungen und JSON-Parsing-Fehlern führt.

Zusätzlich werden rohe Tournotizen, Wetterdaten und POIs ungefiltert in die Prompts von Pass 1 und Pass 2 injiziert, was wertvollen Kontext verschwendet.

---

## Ziele

1. **Pass 2 robuster machen**: Batch-basierte Verarbeitung (3 Seiten/Batch) mit nur den Bildern des jeweiligen Batches
2. **Kontext reduzieren**: Tour-Summary-Node generiert kompakte Zusammenfassung aus Notizen, GPX-Stats und Karte
3. **Alle drei Pässe optimieren**: Summary in Pass 0 (Bildauswahl), Pass 1 (Layout-Planung) und Pass 2 (Content) nutzen
4. **Batch-Größe konfigurierbar**: Einfache Anpassung in `config.py`
5. **Robustness-Maßnahmen**: Retry/Fallback pro Batch, Validierung pro Batch, dynamisches `num_predict`
6. **Thinking Mode deaktivieren**: Gemma-4-Modelle haben Thinking standardmäßig aktiv — der verbraucht `num_predict`-Budget und führt zu leeren Antworten

---

## Design

### 0. Thinking Mode deaktivieren (Ollama-Client-Änderung)

**Datei**: `app/services/ollama_client.py`

**Problem**: Gemma-4-Modelle (`gemma4:26b-ctx128k`, `gemma4:31b-ctx112k`) haben Thinking Mode standardmäßig aktiviert. Die Thinking-Tokens werden aus dem `num_predict`-Budget bedient. Bei `num_predict=32768` kann das Modell den Großteil des Budgets für internes Reasoning verbrauchen, sodass für die eigentliche Antwort nichts übrig bleibt → leere `content`-Felder.

**Lösung**: Thinking Mode für Photobook-Calls deaktivieren, da es sich um strukturierte JSON-Generierung handelt, nicht um komplexes Reasoning.

**Änderung an `call_ollama()`**:
```python
def call_ollama(
    prompt: str,
    *,
    model: str = "gemma4:26b-ctx128k",
    base_url: str = OLLAMA_BASE_URL,
    images: Optional[list[str]] = None,
    system_prompt: Optional[str] = None,
    temperature: float = 0.7,
    top_p: Optional[float] = 0.9,
    num_predict: int = 16384,
    timeout: int = 600,
    keep_alive: str = "10m",
    strip_thinking: bool = False,
    disable_thinking: bool = False,  # NEU
) -> Optional[str]:
```

Im Payload:
```python
payload = {
    "model": model,
    "messages": messages,
    "stream": False,
    "options": options,
    "keep_alive": keep_alive,
}
if disable_thinking:
    payload["thinking"] = {"type": "disabled"}
```

**Verwendung in Photobook-Calls**: Alle LLM-Calls in `image_selector.py`, `plan.py`, `generate.py` und `summarize_context.py` rufen `call_ollama()` mit `disable_thinking=True` auf.

**Hinweis**: `strip_thinking` bleibt erhalten für Fälle, in denen Thinking erwünscht ist (z.B. Blog-Pfad). Wenn `disable_thinking=True`, ist `strip_thinking` implizit nicht nötig.

---

### 1. Neuer Shared Node: `summarize_context`

**Datei**: `app/nodes/summarize_context_node.py` (neu)
**Service**: `app/services/summarize_context.py` (neu)

**Position im Graph**: Direkt nach `load_tour_notes`, vor der blog/photobook-Verzweigung. Wird für beide Modi ausgeführt.

**Input**:
- `state.notes: Optional[str]`
- `state.gpx_stats: Optional[GPXStats]`
- `state.output_config.photobook_preset: str`

**LLM-Call** (text-only, keine Bilder):
```
Erstelle eine kurze Zusammenfassung dieser Tour (max. 150 Wörter).
Enthalte: Tourtyp (Wanderung/Radtour/Städtetrip), Region/Gebiet,
Jahreszeit, besonderer Anlass (falls erkennbar).
Keine detaillierten Wegbeschreibungen.

TOURDATEN: {distanz}km, {höhenmeter}m Aufstieg, {dauer}
TOURNOTIZEN: {notes}
```

- `temperature=0.0`, `num_predict=1024`, `timeout=60s`, `disable_thinking=True`
- Prompt unter 1000 Tokens (nur Text)

**Output**: `state.tour_summary: Optional[str]`

**Fallback**: Deterministische Summary aus GPX-Stats:
```
"{distanz}km {tourtyp} mit {höhenmeter}m Aufstieg"
```
(Tourtyp aus Preset abgeleitet: `nature_outdoor` → "Wanderung", `culture_architecture` → "Städtetrip", etc.)

**State-Änderung** (`app/state.py`):
```python
tour_summary: Optional[str] = None  # neues Feld
```

---

### 2. Pass 0: Bildauswahl mit Tour-Kontext

**Datei**: `app/photobook/image_selector.py`
**Node**: `app/nodes/select_photobook_images_node.py`

**Änderungen**:
- `_build_batch_prompt()` erhält `tour_summary: Optional[str]` als Parameter
- Prompt wird um einen `TOUR:`-Header ergänzt:
  ```
  TOUR: {tour_summary}
  
  Du erhältst {batch_size} Fotos aus dieser Tour.
  Wähle die {select_count} besten Bilder...
  ```
- `gpx_stats` und `notes` Parameter werden aus dem Service entfernt (bisher ungenutzt)
- `disable_thinking=True` für deterministische Bildauswahl
- Batch-Größe bleibt bei 15, zweistufige Selektion bleibt unverändert

**Node-Änderung**: `state.tour_summary` statt `state.gpx_stats` + `state.notes` an den Service übergeben

---

### 3. Pass 1: Layout-Planung mit reduziertem Kontext

**Datei**: `app/photobook/plan.py`
**Node**: `app/nodes/plan_photobook_node.py`

**Änderungen im Prompt**:
- `state.tour_summary` ersetzt `state.notes`, `state.weather`, `state.poi_list`
- GPX-Stats bleiben als `TOURDATEN` erhalten (Distanz/Höhenmeter für Seiten-Kontext relevant)
- Prompt-Aufbau (nach Umbau):
  ```
  TOUR: {tour_summary}
  TOURDATEN: {distanz}km, {höhenmeter}m
  BILDER: {N} Fotos (chronologisch sortiert, Index 0-{N-1})
  
  PRESETS (wähle eins pro Seite):
  {preset_catalog}
  
  VARIETY-REGELN: [unverändert]
  ```

**Kontext-Ersparnis**: ca. 30–40% weniger Prompt-Tokens (Wetter/POI-Listen + rohe Notizen entfallen)
**Thinking**: `disable_thinking=True` (strukturierte JSON-Ausgabe, kein Reasoning nötig)

**Fallback**: `_generate_fallback_plan()` bleibt unverändert

---

### 4. Pass 2: Batch-basierte Content-Generierung (Kern-Refactoring)

**Datei**: `app/photobook/generate.py` (grundlegender Umbau)
**Node**: `app/nodes/generate_photobook_node.py` (minimale Anpassung)

#### 4.1 Neue Hauptfunktion

```python
def generate_photobook_pages(
    plan: PhotobookPlan,
    images: List[ImageData],
    tour_summary: str,
    model: str,
    batch_size: int = PHOTOBOOK_BATCH_SIZE,  # default 3
) -> List[PageDescription]:
```

**Ablauf**:
1. Seiten aus `plan.pages` in Batches à `batch_size` aufteilen
2. Für jeden Batch:
   a. `_build_batch_prompt(batch_pages, batch_images, tour_summary)` — Prompt konstruieren
   b. `_call_llm_for_batch(prompt, batch_images, model)` — LLM-Call mit nur den Bildern des Batches
   c. `_validate_batch_result(result, batch_pages)` — Validierung (JSON-Parse, Slot-Vollständigkeit, Char-Limits)
   d. Bei Fehler: Retry (1x) → `_generate_fallback_for_batch(batch_pages, batch_images)` als Fallback
3. `_merge_batch_results(all_results)` — deterministisch nach `position` konkatenieren

#### 4.2 Batch-Aufteilung

```python
def _split_into_batches(pages: List[PagePlan], batch_size: int) -> List[List[PagePlan]]:
    """Teilt Seiten chronologisch in Batches. Cover (position=0) immer in Batch 0."""
    return [pages[i:i+batch_size] for i in range(0, len(pages), batch_size)]
```

- Chronologische Aufteilung (kein Shuffling)
- Cover-Seite (position=0) ist garantiert in Batch 0

#### 4.3 Pro-Batch-Prompt

```
TOUR: {tour_summary}
TOURDATEN: {distanz}km, {höhenmeter}m

SEITENPLAN (nur dieser Batch, {batch_size} Seiten):
[
  {"position": N, "preset_id": "...", "image_indices": [...], "purpose": "..."},
  ...
]

VERWENDETE PRESETS (nur diese sind relevant):
{preset_catalog_filtered}

AUFGABE PRO SEITE:
{style_block}
1. Weise jedem Image-Slot ein Bild zu...
2. TEXT-PFLICHT: [unverändert]
3. Textdimensionen: [unverändert]
4. Generiere AUSFÜHRLICHE, lebendige Texte... [unverändert]
5. JEDE Seite MUSS einen title-Slot haben... [unverändert]
6. [Mehr-Bild-Regeln unverändert]

VOR DER AUSGABE PRÜFEN: [unverändert]

BEISPIELE: [nur die im Batch verwendeten Presets zeigen]
```

**Schlüsseländerungen**:
- `tour_summary` statt `notes_text` (rohe Notizen komplett entfernt)
- `preset_catalog_filtered`: Nur Presets, die in diesem Batch vorkommen (3–5 statt 18)
- `plan_text`: Nur die Seiten dieses Batches (3 statt 16–20)
- `images`: Nur die Bilder, die in `image_indices` dieses Batches referenziert werden (3–12 statt 16–20)
- `num_predict`: Dynamisch berechnet (siehe 4.5)

#### 4.4 Bildzuordnung pro Batch

```python
def _images_for_batch(batch_pages: List[PagePlan], all_images: List[ImageData]) -> List[ImageData]:
    """Ermittelt die Menge der im Batch referenzierten Bilder."""
    used_indices = set()
    for page in batch_pages:
        used_indices.update(page.image_indices)
    return [all_images[i] for i in sorted(used_indices)]
```

Nur diese Bilder werden base64-codiert an den LLM gesendet.

#### 4.5 Dynamisches `num_predict`

```python
def calculate_num_predict(
    batch_pages: List[PagePlan],
    preset_catalog: Dict[str, Preset],
    safety_factor: float = 1.5,
    min_tokens: int = 8192,
) -> int:
    """Berechnet num_predict aus der Summe der char_limits aller Text-Slots im Batch."""
    max_chars = 0
    for page in batch_pages:
        preset = preset_catalog[page.preset_id]
        for slot in preset.slots:
            if slot.text_role:  # nur Text-Slots
                max_chars += slot.char_limit or 600  # fallback 600 chars
    
    # Konservativ: 2.5 chars pro Token (Deutsch hat längere Wörter)
    text_tokens = max_chars / 2.5
    json_overhead = 2000  # JSON-Struktur, title-Slots, Boilerplate
    return max(min_tokens, int((text_tokens + json_overhead) * safety_factor))
```

**Beispielrechnungen** (Thinking deaktiviert, daher realistisch):
- 3 × `single_text_below` (je 1400 chars) → `(4200/2.5 + 2000) * 1.5 = 5520` → min. 8192
- 3 × `quad_grid_text` (je 1400 chars) → `(4200/2.5 + 2000) * 1.5 = 5520` → min. 8192
- Mix: `cover_hero` (0 text) + `single_text_below` (1400) + `double_stacked_text` (800) → `(2200/2.5 + 2000) * 1.5 = 4320` → min. 8192

Das Minimum von 8192 dient als Sicherheitspuffer — selbst wenn Thinking versehentlich aktiv bleibt, reicht das Budget für eine vollständige Antwort.

#### 4.6 Batch-Validierung

```python
def _validate_batch_result(
    result_json: list,
    batch_pages: List[PagePlan],
    preset_catalog: Dict[str, Preset],
) -> Tuple[bool, Optional[str]]:
    """Validiert ein Batch-Ergebnis. Returns (ok, error_message)."""
    # 1. JSON-Struktur: Alle erwarteten Seiten vorhanden?
    # 2. Slots: Alle image_slots belegt? Alle text_slots mit nicht-leerem Text?
    # 3. Char-Limits: Kein Text überschreitet char_max?
    # 4. image_index: Alle Indizes innerhalb des Batch-Bildbereichs?
```

#### 4.7 Batch-Fallback

```python
def _generate_fallback_for_batch(
    batch_pages: List[PagePlan],
    batch_images: List[ImageData],
) -> List[PageDescription]:
    """Generiert Fallback-Seiten für einen Batch."""
    # Analog zur existierenden _generate_fallback_pages(), aber nur für die Seiten dieses Batches
```

#### 4.8 LLM-Call-Parameter

| Parameter | Vorher | Nachher |
|-----------|--------|---------|
| `temperature` | 0.3 | 0.3 (unverändert) |
| `num_predict` | 32768 (fest) | dynamisch, min. 8192 (safety) |
| `timeout` | 300s | 120s (kürzer pro Batch) |
| `disable_thinking` | — (nicht gesetzt) | `True` (verhindert Thinking-Token-Verbrauch) |
| Bilder im Call | 16–20 | 3–12 (nur Batch-Bilder) |

#### 4.9 Kontext-Ersparnis pro Batch (geschätzt)

| Komponente | Vorher (gesamt) | Nachher (pro Batch) |
|---|---|---|
| Bilder (base64) | ~2 MB (20 à ~100KB) | ~300 KB (3–8 à ~100KB) |
| Preset-Katalog | 18 Presets | 3–5 Presets |
| Seitenplan-JSON | 16–20 Seiten | 3 Seiten |
| Tour-Kontext | Notizen roh (~1KB) | Summary (~200 Tokens) |
| **Prompt gesamt** | **~3 MB** | **~400 KB** |

**~85% Reduktion des Prompt-Kontexts pro LLM-Call.**

---

### 5. Konfiguration

**Datei**: `app/config.py`

Neue Konstante:
```python
PHOTOBOOK_BATCH_SIZE = 3  # Seiten pro Batch in Pass 2. Bei Kontext-Problemen auf 2 reduzieren.
```

Alle Batch-Logik in `generate.py` verwendet diesen Wert, überschreibbar per Funktionsparameter.

---

### 6. State-Modell

**Datei**: `app/state.py`

```python
# Neues Feld (zusätzlich zu existierenden):
tour_summary: Optional[str] = None
```

`notes`, `weather`, `poi_list` bleiben im State (Blog-Pfad nutzt sie weiter), werden aber im Photobook-Pfad nicht mehr an LLMs übergeben.

---

### 7. Graph-Änderungen

**Datei**: `app/graph.py`

1. Neuer Node `summarize_context` nach `load_tour_notes` einfügen
2. Edge: `load_tour_notes` → `summarize_context`
3. Conditional Edge ab `summarize_context` (statt `load_tour_notes`):
   - `mode == "photobook"` → `select_photobook_images`
   - `mode == "blog"` → `enrich_weather`
4. Nodes für `select_photobook_images`, `plan_photobook`, `generate_photobook` bleiben an gleicher Position

---

## Dateien (Übersicht)

| Aktion | Datei |
|--------|-------|
| **NEU** | `app/nodes/summarize_context_node.py` |
| **NEU** | `app/services/summarize_context.py` |
| **MODIFY** | `app/state.py` — `tour_summary` Feld |
| **MODIFY** | `app/config.py` — `PHOTOBOOK_BATCH_SIZE` |
| **MODIFY** | `app/services/ollama_client.py` — `disable_thinking` Parameter |
| **MODIFY** | `app/graph.py` — neuer Node + Edge-Änderungen |
| **MODIFY** | `app/nodes/select_photobook_images_node.py` — Summary statt raw data |
| **MODIFY** | `app/photobook/image_selector.py` — Summary in Prompt |
| **MODIFY** | `app/nodes/plan_photobook_node.py` — Summary statt raw data |
| **MODIFY** | `app/photobook/plan.py` — Summary in Prompt, reduced context |
| **MODIFY** | `app/nodes/generate_photobook_node.py` — batch_size Parameter |
| **MODIFY** | `app/photobook/generate.py` — Batch-basierte Generierung (Hauptumbau) |

---

## Test-Strategie

### Unit-Tests (pytest -m unit)

| Test | Was |
|------|-----|
| `test_batch_splitting` | Seiten korrekt in Batches aufgeteilt, Cover in Batch 0 |
| `test_images_for_batch` | Nur referenzierte Bilder werden extrahiert |
| `test_calculate_num_predict` | Verschiedene Batch-Konfigurationen, Minimum-Grenze |
| `test_validate_batch_result` | Valide/Invalide Ergebnisse, Char-Limit-Überschreitung |
| `test_summarize_context_fallback` | Deterministischer Fallback bei LLM-Fehler |
| `test_build_batch_prompt` | Prompt enthält Summary, nur Batch-Presets, nur Batch-Seiten |

### Integration-Tests (pytest -m integration)

| Test | Was |
|------|-----|
| `test_full_photobook_pipeline` | End-to-End mit Mock-LLM, alle Batches durchlaufen |
| `test_batch_fallback_on_llm_error` | Fallback greift pro Batch, andere Batches unbeeinflusst |
| `test_summarize_context_in_blog_path` | Blog-Pfad läuft mit neuem Node durch |

### Manuelle Tests

- Vollständiger Photobook-Durchlauf mit `nature_outdoor` Preset, `normal` size
- Vollständiger Blog-Durchlauf (sicherstellen, dass neuer Node nicht bricht)
- Batch-Größe auf 1 und 5 ändern, Durchlauf prüfen

---

## Risiken

| Risiko | Mitigation |
|--------|------------|
| Batch-übergreifende Textkonsistenz leidet (kein globaler Kontext) | `tour_summary` in jedem Batch-Prompt hält roten Faden; LLM-Prompt enthält Anweisung, Seitenübergänge konsistent zu halten |
| `num_predict` zu niedrig → Truncation | 1.5x Safety-Faktor + 8192 Minimum; Thinking deaktiviert → keine versteckten Token-Verbraucher; im Fehlerfall greift Batch-Fallback |
| Thinking Mode verbraucht `num_predict`-Budget → leere Antwort | `disable_thinking=True` in allen Photobook-Calls; Minimum von 8192 als zusätzlicher Puffer |
| Mehr LLM-Calls → höhere Gesamtlatenz (6 Batches × 30s = 3min statt 1 Call × 120s = 2min) | Akzeptabler Trade-off für Robustheit; Ollama ist lokal, kein API-Kosten-Problem |
| `summarize_context` schlägt fehl → leere Summary | Deterministischer Fallback aus GPX-Stats garantiert immer ein Ergebnis |

---

## Ausgeschlossen (Non-Goals)

- **Parallelismus**: Batches laufen sequenziell (Ollama bedient nur ein Model gleichzeitig)
- **Blog-Pfad-Änderungen**: Nur der `summarize_context` Node wird shared; Blog-Pfad nutzt Summary optional
- **Preset-Änderungen**: Die 18 Layout-Presets bleiben unverändert
- **Bild-Kompression**: `encode_image_base64` bleibt bei 800px/Q85
