# Draft-Review visuelle Trennung & Overflow-Fix — Design

**Datum:** 2026-05-09
**Scope:** Frontend — `DraftReview.svelte` CSS
**Bezug:** Erweiterung von `2026-05-08-blog-draft-review-design.md`

---

## 1. Problem

1. **Rechte Überlappung:** Die Hover-Outline bei `<figure>` und der Highlight-Hintergrund bei `<p>` reichen rechts nicht so weit wie der eigentliche Inhalt. Oben, links und unten passt es. Ursache: `.article-preview` hat `overflow-y: auto`, was `overflow-x` implizit ebenfalls auf `auto` setzt. Bei breitem Inhalt (Bilder, lange unbrechbare Strings) entsteht horizontaler Overflow, der die Outline/Highlight abschneidet.

2. **Fehlende optische Trennung:** Die auswählbaren Blöcke (Paragraphen, Bilder) fließen ohne visuelle Abgrenzung ineinander. Der User wünscht moderate Trennung via Zebra-Striping (alternierende Hintergrundfarbe).

---

## 2. Lösung

### 2.1 Overflow-Fix

**`.article-preview`:**
- `overflow-x: clip` — verhindert horizontalen Overflow ohne Scrollbalken.

**`.article-content`:**
- `overflow-wrap: break-word` — lange unbrechbare Strings (URLs, etc.) brechen um.

### 2.2 Zebra-Striping

**`p[data-block-index]:nth-child(even)`, `figure[data-block-index]:nth-child(even)`:**
- `background: var(--panel-2)` — dezent abwechselnder Hintergrund.
- Im Dark-Mode ist `--panel-2` bereits `#1A1F2B`, im Light-Mode `#F1F3F6`. Keine separaten Mode-Regeln nötig.

**Block-Abstand:**
- `p[data-block-index]` erhält `margin-bottom: 1rem` (bisher 1.2rem via ArticleDetail-Global — DraftReview überschreibt dies mit eigener Regel).
- `figure[data-block-index]` erhält `padding: 0.75rem` (statt keinem eigenen Padding).

---

## 3. Betroffene Dateien

| Datei | Änderung |
|---|---|
| `frontend/src/lib/DraftReview.svelte` | CSS-Regeln im `<style>`-Block erweitern |

Keine JS/TS-Logik, keine API-Änderungen, keine neuen Abhängigkeiten.

---

## 4. Test-Strategie

- **Visuelle Prüfung:** Draft öffnen, Hover-Zustände prüfen, horizontales Scrollen prüfen.
- **Dark/Light-Mode:** Beide Modes durchschalten, sicherstellen dass Striping in beiden sichtbar ist.
- **Bestehende Tests:** `uv run pytest tests/ -v` — keine Änderungen nötig, reines CSS.
