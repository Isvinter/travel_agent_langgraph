# Frontend List Scroll and Sort Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix scroll behavior so only table rows scroll (header/filters/column titles stay fixed), and add client-side sorting by clicking column headers with ▲/▼ indicators.

**Architecture:** Both `ArticleList.svelte` and `PhotobookList.svelte` get identical CSS/template changes for scroll (flex column layout + sticky thead) and identical script logic for sort (Svelte 5 `$state` + `$derived`). No backend changes.

**Tech Stack:** Svelte 5 (runes mode), TypeScript, CSS (scoped `<style>` blocks)

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `frontend/src/lib/ArticleList.svelte` | Modify | Scroll fix + sort for articles |
| `frontend/src/lib/PhotobookList.svelte` | Modify | Scroll fix + sort for photobooks |

---

### Task 1: Scroll fix in ArticleList.svelte

**Files:**
- Modify: `frontend/src/lib/ArticleList.svelte` (CSS + template)

- [ ] **Step 1: Replace `.article-list` CSS**

Remove `overflow-y: auto`, add flex column layout:

```css
.article-list {
  padding: 1rem;
  display: flex;
  flex-direction: column;
  height: 100%;
}
```

- [ ] **Step 2: Add `.table-scroll-wrapper` CSS**

At the end of the `<style>` block, add:

```css
.table-scroll-wrapper {
  flex: 1;
  overflow-y: auto;
  min-height: 0;
}
```

- [ ] **Step 3: Make `<th>` sticky**

Modify the existing `th` rule to add sticky positioning and background:

```css
th {
  text-align: left;
  color: var(--text-muted);
  font-weight: normal;
  padding: 0.5rem 0.5rem;
  border-bottom: 1px solid var(--border);
  white-space: nowrap;
  position: sticky;
  top: 0;
  background: var(--panel);
  z-index: 1;
}
```

- [ ] **Step 4: Wrap table in scroll wrapper**

In the template, wrap the existing `.table-container` in a `.table-scroll-wrapper` div. Change this:

```svelte
{:else}
  <div class="table-container">
    <table>
```

To this:

```svelte
{:else}
  <div class="table-scroll-wrapper">
    <div class="table-container">
      <table>
```

And close the wrapper after `.table-container`:

```svelte
    </table>
  </div>
</div>
```

To:

```svelte
      </table>
    </div>
  </div>
{/if}
```

- [ ] **Step 5: Verify visually**

Run: `cd frontend && npm run dev`

Open browser, navigate to article list view with enough entries to scroll. Confirm:
- Header "Gespeicherte Artikel (N)" stays fixed
- Filter row stays fixed
- Column headers stay fixed at top of scroll area
- Only data rows scroll

---

### Task 2: Sort implementation in ArticleList.svelte

**Files:**
- Modify: `frontend/src/lib/ArticleList.svelte` (script + template + CSS)

- [ ] **Step 1: Add sort state variables**

After the existing state declarations (`let dialogArticleId`), add:

```typescript
let sortColumn: string | null = $state(null);
let sortDirection: "asc" | "desc" = $state("asc");
```

- [ ] **Step 2: Add sort helper function**

After the `dialogArticleId` declaration (before `toggleSelect`), add:

```typescript
function sortItems<T extends Record<string, any>>(items: T[], column: string, direction: "asc" | "desc"): T[] {
  return [...items].sort((a, b) => {
    const va = a[column];
    const vb = b[column];
    if (va == null && vb == null) return 0;
    if (va == null) return 1;
    if (vb == null) return -1;
    const multiplier = direction === "desc" ? -1 : 1;
    if (typeof va === "string" && typeof vb === "string") {
      return multiplier * va.localeCompare(vb);
    }
    return multiplier * ((va as number) - (vb as number));
  });
}
```

- [ ] **Step 3: Add derived sorted list**

After the sort helper, add:

```typescript
let displayedArticles = $derived(
  sortColumn ? sortItems(articles, sortColumn, sortDirection) : articles
);
```

- [ ] **Step 4: Add click handler**

After `toggleSelectAll`, add:

```typescript
function handleSort(column: string) {
  if (sortColumn === column) {
    sortDirection = sortDirection === "asc" ? "desc" : "asc";
  } else {
    sortColumn = column;
    sortDirection = "desc";
  }
}
```

- [ ] **Step 5: Change `{#each}` to use sorted list**

Change:
```svelte
{#each articles as a}
```
To:
```svelte
{#each displayedArticles as a}
```

- [ ] **Step 6: Add click handlers and indicators to sortable `<th>` elements**

Replace the flat `<th>` elements with sortable variants. Change:

```svelte
<th>Titel</th>
<th>Tour-Datum</th>
<th>Dauer</th>
<th>Distanz</th>
<th>Höhenmeter</th>
<th>Bilder</th>
```

To:

```svelte
<th class="sortable" onclick={() => handleSort("title")}>
  Titel {sortColumn === "title" ? (sortDirection === "asc" ? "▲" : "▼") : ""}
</th>
<th class="sortable" onclick={() => handleSort("tour_date")}>
  Tour-Datum {sortColumn === "tour_date" ? (sortDirection === "asc" ? "▲" : "▼") : ""}
</th>
<th class="sortable" onclick={() => handleSort("tour_duration_hours")}>
  Dauer {sortColumn === "tour_duration_hours" ? (sortDirection === "asc" ? "▲" : "▼") : ""}
</th>
<th class="sortable" onclick={() => handleSort("total_distance_km")}>
  Distanz {sortColumn === "total_distance_km" ? (sortDirection === "asc" ? "▲" : "▼") : ""}
</th>
<th class="sortable" onclick={() => handleSort("elevation_gain_m")}>
  Höhenmeter {sortColumn === "elevation_gain_m" ? (sortDirection === "asc" ? "▲" : "▼") : ""}
</th>
<th class="sortable" onclick={() => handleSort("image_count")}>
  Bilder {sortColumn === "image_count" ? (sortDirection === "asc" ? "▲" : "▼") : ""}
</th>
```

- [ ] **Step 7: Add sortable CSS**

In the `<style>` block, after the existing `th` rule, add:

```css
th.sortable {
  cursor: pointer;
  user-select: none;
}
th.sortable:hover {
  color: var(--text-primary);
}
```

- [ ] **Step 8: Verify sort behavior**

Run: `cd frontend && npm run dev`

In the article list view:
- Click "Titel" → sorts Z→A descending, shows ▼
- Click "Titel" again → sorts A→Z ascending, shows ▲
- Click "Dauer" → sorts highest→lowest descending, shows ▼, Titel indicator disappears
- Click "Bilder" → sorts descending, shows ▼
- Verify checkbox column and button columns have no sort interaction

- [ ] **Step 9: Commit Task 1 + Task 2**

```bash
git add frontend/src/lib/ArticleList.svelte
git commit -m "feat: add fixed scroll headers and client-side sorting to ArticleList"
```

---

### Task 3: Scroll fix in PhotobookList.svelte

**Files:**
- Modify: `frontend/src/lib/PhotobookList.svelte` (CSS + template)

- [ ] **Step 1: Apply the same three CSS changes from Task 1**

Same CSS changes as ArticleList Task 1 Steps 1-3:

a) Replace `.photobook-list` CSS (remove `overflow-y: auto`, add flex column):

```css
.photobook-list {
  padding: 1rem;
  display: flex;
  flex-direction: column;
  height: 100%;
}
```

b) Add `.table-scroll-wrapper` CSS at end of `<style>` block:

```css
.table-scroll-wrapper {
  flex: 1;
  overflow-y: auto;
  min-height: 0;
}
```

c) Add sticky to existing `th` rule:

```css
th {
  text-align: left;
  color: var(--text-muted);
  font-weight: normal;
  padding: 0.5rem 0.5rem;
  border-bottom: 1px solid var(--border);
  white-space: nowrap;
  position: sticky;
  top: 0;
  background: var(--panel);
  z-index: 1;
}
```

- [ ] **Step 2: Wrap table in scroll wrapper (template)**

Same as ArticleList Task 1 Step 4 — wrap `.table-container` in `.table-scroll-wrapper`:

Change:
```svelte
{:else}
  <div class="table-container">
    <table>
```
To:
```svelte
{:else}
  <div class="table-scroll-wrapper">
    <div class="table-container">
      <table>
```

And close:
```svelte
      </table>
    </div>
  </div>
```

- [ ] **Step 3: Verify scroll visually**

In photobook list view with enough entries, confirm same fixed-header scroll behavior as ArticleList.

---

### Task 4: Sort implementation in PhotobookList.svelte

**Files:**
- Modify: `frontend/src/lib/PhotobookList.svelte` (script + template + CSS)

- [ ] **Step 1: Add sort state variables**

After `let deleting`:

```typescript
let sortColumn: string | null = $state(null);
let sortDirection: "asc" | "desc" = $state("asc");
```

- [ ] **Step 2: Add sort helper function**

After `let deleting` (before `toggleSelect`):

```typescript
function sortItems<T extends Record<string, any>>(items: T[], column: string, direction: "asc" | "desc"): T[] {
  return [...items].sort((a, b) => {
    const va = a[column];
    const vb = b[column];
    if (va == null && vb == null) return 0;
    if (va == null) return 1;
    if (vb == null) return -1;
    const multiplier = direction === "desc" ? -1 : 1;
    if (typeof va === "string" && typeof vb === "string") {
      return multiplier * va.localeCompare(vb);
    }
    return multiplier * ((va as number) - (vb as number));
  });
}
```

- [ ] **Step 3: Add derived sorted list**

After the sort helper:

```typescript
let displayedPhotobooks = $derived(
  sortColumn ? sortItems(photobooks, sortColumn, sortDirection) : photobooks
);
```

- [ ] **Step 4: Add click handler**

After `toggleSelectAll`:

```typescript
function handleSort(column: string) {
  if (sortColumn === column) {
    sortDirection = sortDirection === "asc" ? "desc" : "asc";
  } else {
    sortColumn = column;
    sortDirection = "desc";
  }
}
```

- [ ] **Step 5: Change `{#each}`**

Change:
```svelte
{#each photobooks as p}
```
To:
```svelte
{#each displayedPhotobooks as p}
```

- [ ] **Step 6: Add sortable `<th>` elements with indicators**

Replace:
```svelte
<th>Titel</th>
<th>Tour-Datum</th>
<th>Dauer</th>
<th>Distanz</th>
<th>Höhenmeter</th>
<th>Bilder</th>
<th>Grösse</th>
```

With:
```svelte
<th class="sortable" onclick={() => handleSort("title")}>
  Titel {sortColumn === "title" ? (sortDirection === "asc" ? "▲" : "▼") : ""}
</th>
<th class="sortable" onclick={() => handleSort("tour_date")}>
  Tour-Datum {sortColumn === "tour_date" ? (sortDirection === "asc" ? "▲" : "▼") : ""}
</th>
<th class="sortable" onclick={() => handleSort("tour_duration_hours")}>
  Dauer {sortColumn === "tour_duration_hours" ? (sortDirection === "asc" ? "▲" : "▼") : ""}
</th>
<th class="sortable" onclick={() => handleSort("total_distance_km")}>
  Distanz {sortColumn === "total_distance_km" ? (sortDirection === "asc" ? "▲" : "▼") : ""}
</th>
<th class="sortable" onclick={() => handleSort("elevation_gain_m")}>
  Höhenmeter {sortColumn === "elevation_gain_m" ? (sortDirection === "asc" ? "▲" : "▼") : ""}
</th>
<th class="sortable" onclick={() => handleSort("image_count")}>
  Bilder {sortColumn === "image_count" ? (sortDirection === "asc" ? "▲" : "▼") : ""}
</th>
<th class="sortable" onclick={() => handleSort("photobook_size")}>
  Grösse {sortColumn === "photobook_size" ? (sortDirection === "asc" ? "▲" : "▼") : ""}
</th>
```

- [ ] **Step 7: Add sortable CSS**

In `<style>`, after the `th` rule:

```css
th.sortable {
  cursor: pointer;
  user-select: none;
}
th.sortable:hover {
  color: var(--text-primary);
}
```

- [ ] **Step 8: Verify sort behavior**

In photobook list view:
- Click each column header → sorts descending on first click
- Click same header again → toggles to ascending
- Arrow indicators appear only on active sort column
- Checkbox and button columns are not sortable

- [ ] **Step 9: Commit Task 3 + Task 4**

```bash
git add frontend/src/lib/PhotobookList.svelte
git commit -m "feat: add fixed scroll headers and client-side sorting to PhotobookList"
```
