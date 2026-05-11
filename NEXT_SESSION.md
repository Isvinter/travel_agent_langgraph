# NEXT_SESSION.md — Photobook-Pipeline Robustness Refactor

**Branch**: `photobook-pipeline-robustness`
**Worktree**: `.worktrees/photobook-pipeline-robustness/`
**Status**: Implementierung abgeschlossen, wartet auf manuellen Test

---

## Was wurde umgesetzt

### Problem
LLMs kamen mit der alten Architektur an ihre Grenzen: Alle 16–20 base64-codierten Bilder in einem einzigen Ollama-Call (~3 MB Prompt) → Truncation, fehlende Bildbeschreibungen, JSON-Parse-Fehler.

### Lösung
Drei Kerntechniken:

1. **Batch-basierte Content-Generierung (Pass 2)**: Seiten in Batches à 3 aufgeteilt, nur Batch-Bilder ans LLM gesendet (~85% Kontext-Reduktion pro Call)
2. **Tour-Summary-Node**: Kompakte LLM-Zusammenfassung (150 Wörter) vor der blog/photobook-Verzweigung generiert; ersetzt rohe Notizen/Wetter/POIs in allen Photobook-Prompts
3. **Thinking Mode deaktiviert**: Gemma-4-Modelle haben Thinking standardmäßig an → verbraucht `num_predict`-Budget → leere Antworten. `disable_thinking=True` in allen Photobook-Calls

### Datei-Änderungen

| Datei | Änderung |
|-------|----------|
| `app/services/ollama_client.py` | `disable_thinking` Parameter → `payload["thinking"] = {"type": "disabled"}` |
| `app/state.py` | `tour_summary: Optional[str] = None` |
| `app/config.py` | `PHOTOBOOK_BATCH_SIZE = 3` |
| `app/services/summarize_context.py` | **NEU** — LLM-Summary-Service mit deterministischem Fallback |
| `app/nodes/summarize_context_node.py` | **NEU** — Thin wrapper, extrahiert GPX-Daten → Service |
| `app/graph.py` | Neuer Node + Routing: `load_tour_notes → summarize_context → [blog\|photobook]` |
| `app/photobook/image_selector.py` | `tour_summary` statt `gpx_stats`/`notes`; `disable_thinking=True` |
| `app/nodes/select_photobook_images_node.py` | Übergibt `state.tour_summary` statt raw data |
| `app/photobook/plan.py` | `tour_summary` statt `notes`/`weather`/`poi_list`; `disable_thinking=True` |
| `app/nodes/plan_photobook_node.py` | Übergibt `state.tour_summary` statt raw data |
| `app/photobook/generate.py` | **Hauptumbau** — Batch-basierte Pipeline (details unten) |
| `app/nodes/generate_photobook_node.py` | Neue Signatur: `tour_summary`, `gpx_distance`, `gpx_elevation` |

### generate.py — Neue Batch-Pipeline im Detail

```
generate_photobook_pages(plan, images, tour_summary, ...):
  batches = _split_into_batches(pages, batch_size=3)
  for batch in batches:
    batch_images = _images_for_batch(batch, images)
    prompt = _build_batch_prompt(batch, tour_summary, ...)
    num_pred = calculate_num_predict(batch)  # dynamisch, min 8192
    for attempt in range(2):
      content = call_ollama(prompt, images=batch_images, disable_thinking=True)
      pages_data = json.loads(content)
      ok, msg = _validate_batch_result(pages_data, batch)
      if ok: break
    if not ok:
      fallback = _generate_fallback_for_batch(batch, batch_images)
  return _merge_batch_results(all_results)
```

**Neue Funktionen**: `_split_into_batches`, `_images_for_batch`, `calculate_num_predict`, `_build_batch_prompt`, `_validate_batch_result`, `_generate_fallback_for_batch`, `_merge_batch_results`

**Entfernte Funktionen**: `GENERATE_PROMPT_TEMPLATE`, `_build_generate_prompt`, `_generate_fallback_pages` (alte globale)

### Konfiguration

- `PHOTOBOOK_BATCH_SIZE = 3` in `config.py` — bei Bedarf auf 2 reduzieren oder auf 4–5 erhöhen
- `calculate_num_predict()`: Safety-Factor 1.5x, Minimum 8192 Tokens

---

## Test-Status

```
498 passed, 0 failed, 1 deselected (e2e)
```

Alle Unit- und Integration-Tests grün. E2E-Tests (`-m e2e`) sind ausgeschlossen (benötigen Ollama + Chrome).

---

## Manuelle Tests (vor Merge durchführen)

### 1. Photobook-Pipeline End-to-End

```python
from app.graph import build_graph
from app.state import AppState, OutputConfig

state = AppState(
    gpx_file="/pfad/zu/einer/tour.gpx",
    images_dir="/pfad/zu/bildern/",
    output_config=OutputConfig(
        mode="photobook",
        photobook_preset="nature_outdoor",
        photobook=PhotobookConfig(size="normal"),
    ),
    model="gemma4:31b-ctx112k",  # oder 26b
)

graph = build_graph()
result = graph.invoke(state)
```

**Prüfen**:
- `result["tour_summary"]` ist nicht leer
- `result["photobook_images"]` hat ~16 Bilder
- `result["photobook_plan"]` hat ~14–18 Seiten
- `result["photobook_pages"]` hat korrekte Anzahl, jede Seite hat `title`-Slot mit Text
- `result["photobook_html"]` enthält HTML
- `result["photobook_pdf_path"]` zeigt auf existierende PDF
- Keine leeren Bildbeschreibungen
- Logs zeigen Batch-Verarbeitung: "Batch 1/6: 3 Seiten", "Batch 2/6: 3 Seiten", ...

### 2. Blog-Pfad unverändert

```python
state = AppState(
    gpx_file="...",
    images_dir="...",
    output_config=OutputConfig(mode="blog"),
)
result = graph.invoke(state)
```

Blog-Pfad sollte normal funktionieren (der neue `summarize_context` Node läuft auch für Blog, aber Blog nutzt `tour_summary` nicht aktiv — kein Breaking Change).

### 3. Fallback testen

Photobook mit `model="invalid-model-name"` ausführen → alle Batches sollten Fallback nutzen, PDF sollte trotzdem generiert werden (mit Platzhalter-Texten).

### 4. Batch-Größe variieren

`PHOTOBOOK_BATCH_SIZE = 1` vs `PHOTOBOOK_BATCH_SIZE = 5` in `config.py` testen.

---

## Spec & Plan

- **Spec**: `docs/superpowers/specs/2026-05-11-photobook-pipeline-robustness-design.md`
- **Plan**: `docs/superpowers/plans/2026-05-11-photobook-pipeline-robustness-plan.md`

---

## Commit-Log (13 commits)

```
c0ca52f fix: update test_photobook_presets.py for new function signatures
102f691 feat: implement batch-based page generation with merge and fallback
05ca62f feat: add batch validation and per-batch fallback generation
87a296e feat: add batch prompt construction with tour_summary and filtered presets
e245bbc feat: add batch helper functions and tests (split, images_for_batch, num_predict)
44c02f7 feat: use tour_summary in layout planner, reduce context, disable thinking
77d0144 feat: use tour_summary in image selector, disable thinking mode
3c4241f feat: integrate summarize_context node into graph, route after summary
cd774c3 feat: add summarize_context node
9b03a75 feat: add summarize_context service with LLM + deterministic fallback
9e294c8 feat: add PHOTOBOOK_BATCH_SIZE config constant
eedb61b feat: add tour_summary field to AppState
345c5ba feat: add disable_thinking parameter to call_ollama
```

---

## Nächste Session

1. `cd .worktrees/photobook-pipeline-robustness`
2. Manuelle Tests durchführen (siehe oben)
3. Wenn alles passt: `git checkout main && git merge photobook-pipeline-robustness`
4. Worktree aufräumen: `git worktree remove .worktrees/photobook-pipeline-robustness`
5. Branch löschen: `git branch -d photobook-pipeline-robustness`
