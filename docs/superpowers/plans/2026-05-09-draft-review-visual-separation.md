# Draft-Review visuelle Trennung & Overflow-Fix — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Overflow-Fix und Zebra-Striping in DraftReview.svelte per CSS

**Architecture:** Reine CSS-Änderung in einer Datei (`DraftReview.svelte`). Keine JS/TS-Logik, keine API-Änderungen, keine neuen Abhängigkeiten.

**Tech Stack:** Svelte 5, plain CSS (CSS custom properties)

---

### Task 1: CSS-Regeln hinzufügen

**Files:**
- Modify: `frontend/src/lib/DraftReview.svelte` (Zeilen 511-514, 517-543)

- [ ] **Step 1: Overflow-Fix auf `.article-preview`**

In `frontend/src/lib/DraftReview.svelte`, ersetze in Zeile 513 `overflow-y: auto;` durch `overflow-y: auto; overflow-x: clip;`:

```css
  .article-preview {
    flex: 6;
    overflow-y: auto;
    overflow-x: clip;
    padding: 1.5rem 2rem;
  }
```

- [ ] **Step 2: `overflow-wrap` auf `.article-content`**

In `frontend/src/lib/DraftReview.svelte`, ergänze die `.article-content`-Regel. Füge nach den `figure[data-marked="true"]`-Regeln (ca. Zeile 544) eine neue Regel ein:

```css
  .article-content {
    overflow-wrap: break-word;
  }
```

- [ ] **Step 3: Zebra-Striping für Paragraphen und Bilder**

Ergänze nach den bestehenden `figure[data-marked="true"]`-Regeln und vor den `h1..h6`-Regeln:

```css
  .article-content :global(p[data-block-index]:nth-child(even)),
  .article-content :global(figure[data-block-index]:nth-child(even)) {
    background: var(--panel-2);
    border-radius: 4px;
  }
```

- [ ] **Step 4: Block-Abstände anpassen**

Passe die bestehenden `p[data-block-index]`-Regeln an (Zeile 517-523) — füge `margin-bottom: 1rem` hinzu und das `border-radius` auf `4px`:

```css
  .article-content :global(p[data-block-index]) {
    cursor: pointer;
    transition: background 0.15s, border-color 0.15s;
    border-left: 3px solid transparent;
    padding-left: 0.75rem;
    border-radius: 4px;
    margin-bottom: 1rem;
  }
```

Passe die bestehenden `figure[data-block-index]`-Regeln an (Zeile 531-536) — füge `padding` und `margin` hinzu:

```css
  .article-content :global(figure[data-block-index]) {
    cursor: pointer;
    transition: outline 0.15s;
    outline: 2px solid transparent;
    border-radius: 4px;
    padding: 1rem;
    margin: 0.5rem 0;
  }
```

- [ ] **Step 5: Markierte Blöcke — Zebra-Striping überschreiben**

Füge nach den Zebra-Striping-Regeln eine Regel ein, die sicherstellt, dass markierte Blöcke ihren blauen Hintergrund behalten (nicht vom Zebra-Striping überschrieben werden):

```css
  .article-content :global(p[data-marked="true"]),
  .article-content :global(figure[data-marked="true"]) {
    background: rgba(52, 152, 219, 0.1);
  }
```

**Hinweis:** Dies ersetzt/erweitert die bestehenden `data-marked`-Regeln. Prüfe, ob die bestehenden `p[data-marked="true"]` (Zeile 527-530) und `figure[data-marked="true"]` (Zeile 540-543) zusammengelegt werden sollen oder separat bleiben.

- [ ] **Step 6: Frontend-Build prüfen**

```bash
cd frontend && npm run build
```

Expected: Build erfolgreich ohne Fehler.

- [ ] **Step 7: Backend-Tests prüfen (keine Änderungen erwartet)**

```bash
uv run pytest tests/ -v
```

Expected: Alle Tests bestehen (reine CSS-Änderung, keine Backend-Auswirkungen).

- [ ] **Step 8: Commit**

```bash
git add frontend/src/lib/DraftReview.svelte
git commit -m "fix: draft-review overflow und zebra-striping für selektierbare blöcke"
```
