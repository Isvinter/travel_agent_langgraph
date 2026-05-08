# Tab-Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the Pipeline/Datenbank and Blogartikel/Fotobücher tabs with distinct visual hierarchy (line tabs + segmented control).

**Architecture:** Pure HTML/CSS change in a single Svelte component (`App.svelte`). No TypeScript logic changes. Reuses existing `app.css` CSS variables for both dark/light themes.

**Tech Stack:** Svelte 5 (runes mode), CSS custom properties, no new dependencies.

---

### Task 1: Replace Ebene 1 template — `nav.right-tabs` → `div.top-tab-bar`

**Files:**
- Modify: `frontend/src/App.svelte:73-107` (the `<nav class="right-tabs">` block)

- [ ] **Step 1: Replace the tab bar template**

Replace lines 73-107:

```svelte
    <nav class="right-tabs">
      <button
        class="right-tab"
        class:active={rightTab === "pipeline"}
        onclick={() => switchRightTab("pipeline")}
      >
        Pipeline
      </button>
      <button
        class="right-tab"
        class:active={rightTab === "datenbank"}
        onclick={() => switchRightTab("datenbank")}
      >
        Datenbank
      </button>
      <button
        class="theme-toggle"
        onclick={toggleTheme}
        title={$theme === "dark" ? "Helles Design" : "Dunkles Design"}
      >
        {#if $theme === "dark"}
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="5"/>
            <line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/>
            <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
            <line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/>
            <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
          </svg>
        {:else}
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
          </svg>
        {/if}
      </button>
    </nav>
```

With:

```svelte
    <div class="top-tab-bar">
      <div class="top-tab-bar-line"></div>
      <button
        class="top-tab"
        class:active={rightTab === "pipeline"}
        onclick={() => switchRightTab("pipeline")}
      >
        Pipeline
      </button>
      <button
        class="top-tab"
        class:active={rightTab === "datenbank"}
        onclick={() => switchRightTab("datenbank")}
      >
        Datenbank
      </button>
      <div class="top-tab-bar-spacer"></div>
      <button
        class="theme-toggle"
        onclick={toggleTheme}
        title={$theme === "dark" ? "Helles Design" : "Dunkles Design"}
      >
        {#if $theme === "dark"}
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="5"/>
            <line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/>
            <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
            <line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/>
            <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
          </svg>
        {:else}
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
          </svg>
        {/if}
      </button>
    </div>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/App.svelte
git commit -m "feat: replace tab bar template with line-based top-tab-bar"
```

---

### Task 2: Replace Ebene 2 template — `div.sub-tabs` → `div.segmented-control`

**Files:**
- Modify: `frontend/src/App.svelte:109-126` (the `{#if rightTab === "datenbank"}` block)

- [ ] **Step 1: Replace the subtabs template**

Replace lines 109-126:

```svelte
    {#if rightTab === "datenbank"}
      <div class="sub-tabs">
        <button
          class="sub-tab"
          class:active={dbSubTab === "articles"}
          onclick={() => switchDbSubTab("articles")}
        >
          Blogartikel
        </button>
        <button
          class="sub-tab"
          class:active={dbSubTab === "photobooks"}
          onclick={() => switchDbSubTab("photobooks")}
        >
          Fotobücher
        </button>
      </div>
    {/if}
```

With:

```svelte
    {#if rightTab === "datenbank"}
      <div class="segmented-control">
        <button
          class="segment"
          class:active={dbSubTab === "articles"}
          onclick={() => switchDbSubTab("articles")}
        >
          Blogartikel
        </button>
        <button
          class="segment"
          class:active={dbSubTab === "photobooks"}
          onclick={() => switchDbSubTab("photobooks")}
        >
          Fotobücher
        </button>
      </div>
    {/if}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/App.svelte
git commit -m "feat: replace sub-tabs with segmented control pill design"
```

---

### Task 3: Replace CSS — remove old styles, add new styles

**Files:**
- Modify: `frontend/src/App.svelte:191-241` (the `.right-tabs`, `.right-tab`, `.sub-tabs`, `.sub-tab` styles)

- [ ] **Step 1: Replace the tab CSS**

Replace lines 191-241:

```css
  .right-tabs {
    display: flex;
    gap: 0.25rem;
    margin-bottom: 0.75rem;
    flex-shrink: 0;
    align-items: center;
  }
  .right-tab {
    padding: 0.5rem 1rem;
    background: var(--panel);
    color: var(--text-secondary);
    font-size: 0.8rem;
    font-weight: 500;
    border: 1px solid var(--border);
    border-radius: var(--radius);
    cursor: pointer;
  }
  .right-tab.active {
    background: var(--accent);
    color: white;
    border-color: var(--accent);
  }
  .right-tab:hover:not(.active) {
    background: var(--panel-2);
    color: var(--text-primary);
  }
  .sub-tabs {
    display: flex;
    gap: 0.25rem;
    margin-bottom: 0.75rem;
    flex-shrink: 0;
  }
  .sub-tab {
    padding: 0.35rem 0.75rem;
    background: var(--panel);
    color: var(--text-secondary);
    font-size: 0.75rem;
    font-weight: 500;
    border: 1px solid var(--border);
    border-radius: var(--radius);
    cursor: pointer;
  }
  .sub-tab.active {
    background: var(--accent);
    color: white;
    border-color: var(--accent);
  }
  .sub-tab:hover:not(.active) {
    background: var(--panel-2);
    color: var(--text-primary);
  }
```

With:

```css
  .top-tab-bar {
    position: relative;
    display: flex;
    gap: 1.5rem;
    align-items: flex-end;
    margin-bottom: 1.25rem;
    flex-shrink: 0;
  }
  .top-tab-bar-line {
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    height: 1px;
    background: var(--border);
  }
  .top-tab {
    position: relative;
    padding: 0 0 10px 0;
    background: none;
    border: none;
    border-radius: 0;
    color: var(--text-secondary);
    font-size: 0.8rem;
    font-weight: 500;
    cursor: pointer;
  }
  .top-tab.active {
    color: var(--text-primary);
    font-weight: 600;
  }
  .top-tab.active::after {
    content: "";
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    height: 2px;
    background: var(--accent);
    border-radius: 1px 1px 0 0;
  }
  .top-tab:hover:not(.active) {
    color: var(--text-primary);
  }
  .top-tab-bar-spacer {
    flex: 1;
  }
  .segmented-control {
    display: inline-flex;
    background: var(--panel-2);
    border-radius: var(--radius);
    padding: 3px;
    margin-bottom: 0.5rem;
    flex-shrink: 0;
  }
  .segment {
    padding: 5px 16px;
    background: transparent;
    border: none;
    border-radius: var(--radius-sm);
    color: var(--text-secondary);
    font-size: 0.75rem;
    font-weight: 500;
    cursor: pointer;
  }
  .segment.active {
    background: var(--panel);
    color: var(--text-primary);
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.15);
  }
  .segment:hover:not(.active) {
    color: var(--text-primary);
  }
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/App.svelte
git commit -m "style: replace tab CSS with line tabs and segmented control styles"
```

---

### Task 4: Verify visual rendering

**Files:**
- No file changes

- [ ] **Step 1: Check TypeScript build compiles**

```bash
cd frontend && npx svelte-check
```

Expected: No errors.

- [ ] **Step 2: Visual verification checklist**

Start the dev server (`cd frontend && npm run dev`) and check:

1. **Pipeline active:** Pipeline tab has blue underline, Datenbank is gray. No segmented control visible. Theme toggle at far right.
2. **Datenbank active:** Datenbank tab has blue underline, Pipeline is gray. Segmented control visible below, Blogartikel is active pill.
3. **Switch Blogartikel → Fotobücher:** Pill slides to Fotobücher, content changes.
4. **Toggle dark/light theme:** All colors switch correctly. Line, underline, segmented control all adapt.
5. **Hover inaktive Tabs:** Text color brightens on hover, no background change.
6. **Hover inaktive Segmente:** Text color brightens on hover.

- [ ] **Step 3: Commit (if any fixups needed)**

```bash
git add frontend/src/App.svelte
git commit -m "fix: tab redesign visual tweaks"
```
