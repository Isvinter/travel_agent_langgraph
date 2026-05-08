<svelte:options runes />

<script lang="ts">
  import { route, navigateTo } from "./lib/stores/router";
  import { runState, currentDraftId } from "./lib/stores/pipeline";
  import { theme, toggleTheme } from "./lib/stores/theme";
  import ModelSelector from "./lib/ModelSelector.svelte";
  import FileDropZone from "./lib/FileDropZone.svelte";
  import OutputDirInput from "./lib/OutputDirInput.svelte";
  import NotesInput from "./lib/NotesInput.svelte";
  import SettingsTabs from "./lib/SettingsTabs.svelte";
  import RunButton from "./lib/RunButton.svelte";
  import PipelineTimeline from "./lib/PipelineTimeline.svelte";
  import ArticleList from "./lib/ArticleList.svelte";
  import ArticleDetail from "./lib/ArticleDetail.svelte";
  import PhotobookList from "./lib/PhotobookList.svelte";
  import PhotobookDetail from "./lib/PhotobookDetail.svelte";
  import DraftReview from "./lib/DraftReview.svelte";

  let rt = $derived($route);
  let showSidebar = $derived(rt.page === "pipeline");

  $effect(() => {
    if ($runState === "running" && rt.page !== "pipeline") {
      navigateTo({ page: "pipeline" });
    }
    if ($currentDraftId !== null && rt.page !== "draft") {
      navigateTo({ page: "draft", id: $currentDraftId });
    }
  });
</script>

<div class="layout" class:has-sidebar={showSidebar}>

  <header class="topnav">
    <span class="topnav-brand">Tavilo</span>
    <nav class="topnav-tabs">
      <button
        class="t-tab"
        class:active={rt.page === "pipeline"}
        onclick={() => navigateTo({ page: "pipeline" })}
      >Pipeline</button>
      <button
        class="t-tab"
        class:active={rt.page === "articles" || rt.page === "article" || rt.page === "draft"}
        onclick={() => navigateTo({ page: "articles" })}
      >Blogartikel</button>
      <button
        class="t-tab"
        class:active={rt.page === "photobooks" || rt.page === "photobook"}
        onclick={() => navigateTo({ page: "photobooks" })}
      >Fotobücher</button>
    </nav>
    <div class="topnav-spacer"></div>
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
  </header>

  {#if showSidebar}
    <aside class="sidebar panel">
      <div class="sidebar-header">⚙ Einstellungen</div>

      <div class="sidebar-scroll">
        <div class="sb-group">
          <div class="sb-group-title">Daten-Input</div>
          <FileDropZone />
          <NotesInput />
        </div>

        <div class="sb-group">
          <div class="sb-group-title">KI-Modell</div>
          <ModelSelector />
        </div>

        <div class="sb-group">
          <div class="sb-group-title">Modus</div>
          <SettingsTabs />
        </div>

        <div class="sb-group">
          <div class="sb-group-title">Ausgabe</div>
          <OutputDirInput />
        </div>
      </div>

      <div class="run-section">
        <RunButton />
      </div>
    </aside>
  {/if}

  <main class="main">
    <div class="right-content">
      {#if rt.page === "pipeline"}
        <PipelineTimeline />
      {:else if rt.page === "draft"}
        <DraftReview id={rt.id} />
      {:else if rt.page === "article"}
        <ArticleDetail id={rt.id} />
      {:else if rt.page === "photobook"}
        <PhotobookDetail id={rt.id} />
      {:else if rt.page === "photobooks"}
        <PhotobookList />
      {:else}
        <ArticleList />
      {/if}
    </div>
  </main>
</div>

<style>
  .layout {
    display: grid;
    grid-template-columns: 1fr;
    grid-template-rows: 44px 1fr;
    height: 100vh;
    width: 100vw;
    background: var(--bg);
  }
  .layout.has-sidebar {
    grid-template-columns: 260px 1fr;
  }

  /* ── Top Navigation ── */
  .topnav {
    grid-column: 1 / -1;
    display: flex;
    align-items: center;
    gap: 0;
    height: 44px;
    padding: 0 16px;
    background: var(--header-bg);
    border-bottom: 1px solid var(--border);
  }
  .topnav-brand {
    font-weight: 700;
    color: var(--accent);
    font-size: 1rem;
    margin-right: 24px;
  }
  .topnav-tabs {
    display: flex;
    height: 100%;
  }
  .t-tab {
    padding: 0 16px;
    height: 100%;
    display: flex;
    align-items: center;
    background: none;
    border: none;
    border-bottom: 2px solid transparent;
    color: var(--text-secondary);
    font-size: 0.8rem;
    font-weight: 500;
    cursor: pointer;
    transition: color 0.15s, border-color 0.15s;
  }
  .t-tab.active {
    color: var(--text-primary);
    font-weight: 600;
    border-bottom-color: var(--accent);
  }
  .t-tab:hover:not(.active) {
    color: var(--text-primary);
  }
  .topnav-spacer {
    flex: 1;
  }
  .theme-toggle {
    padding: 0.5rem;
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    color: var(--text-secondary);
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    line-height: 1;
    flex-shrink: 0;
  }
  .theme-toggle:hover {
    background: var(--panel-2);
    color: var(--text-primary);
  }

  /* ── Sidebar ── */
  .sidebar {
    background: var(--panel);
    border-right: 1px solid var(--border);
    padding: 14px 14px 0 14px;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }
  .sidebar-header {
    font-size: 0.7rem;
    font-weight: 600;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 12px;
    flex-shrink: 0;
  }
  .sidebar-scroll {
    flex: 1;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 0;
  }
  .sb-group {
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 10px;
    margin-bottom: 10px;
    background: rgba(91, 140, 255, 0.02);
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }
  .sb-group-title {
    font-size: 0.6rem;
    font-weight: 600;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }
  .run-section {
    flex-shrink: 0;
    padding: 0.5rem 0 14px 0;
    background: var(--panel);
  }

  /* ── Main Content ── */
  .main {
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }
  .right-content {
    flex: 1;
    display: flex;
    flex-direction: column;
    min-height: 0;
  }
</style>
