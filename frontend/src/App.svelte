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
  import OutputWindow from "./lib/OutputWindow.svelte";
  import ArticleList from "./lib/ArticleList.svelte";
  import ArticleDetail from "./lib/ArticleDetail.svelte";
  import PhotobookList from "./lib/PhotobookList.svelte";
  import PhotobookDetail from "./lib/PhotobookDetail.svelte";
  import DraftReview from "./lib/DraftReview.svelte";

  let rt = $derived($route);
  let rightTab = $derived(rt.page === "pipeline" ? "pipeline" : "datenbank");
  let dbSubTab: "articles" | "photobooks" = $state("articles");

  function switchRightTab(tab: "pipeline" | "datenbank") {
    if (tab === "pipeline") {
      navigateTo({ page: "pipeline" });
    } else {
      if (dbSubTab === "articles") {
        navigateTo({ page: "articles" });
      } else {
        navigateTo({ page: "photobooks" });
      }
    }
  }

  function switchDbSubTab(sub: "articles" | "photobooks") {
    dbSubTab = sub;
    if (sub === "articles") {
      navigateTo({ page: "articles" });
    } else {
      navigateTo({ page: "photobooks" });
    }
  }

  $effect(() => {
    if ($runState === "running" && rt.page !== "pipeline") {
      navigateTo({ page: "pipeline" });
    }
    if ($currentDraftId !== null && rt.page !== "draft") {
      navigateTo({ page: "draft", id: $currentDraftId });
    }
  });

</script>

<div class="layout">
  <!-- TITELBAR -->
  <header class="titlebar">
    <h1 class="titlebar-title">Tavilo</h1>
    <p class="titlebar-subtitle">KI-basierte Erstellung von Blogartikeln und Fotobüchern aus Rohdaten die Deine Privatsphäre respektiert</p>
  </header>

  <!-- LINKE SIDEBAR -->
  <aside class="sidebar panel">
    <h1 class="sidebar-title">Einstellungen</h1>

    <div class="sidebar-scroll">
      <ModelSelector />
      <div class="section">
        <span class="section-title">TourDaten</span>
        <FileDropZone />
        <NotesInput />
      </div>
      <OutputDirInput />
      <SettingsTabs />
    </div>

    <div class="run-section">
      <RunButton />
    </div>
  </aside>

  <!-- RECHTE SEITE -->
  <main class="main">
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

    <div class="right-content">
      {#if rightTab === "pipeline"}
        <OutputWindow />
      {:else if rt.page === "draft"}
        <DraftReview id={rt.id} />
      {:else if rt.page === "article"}
        <ArticleDetail id={rt.id} />
      {:else if rt.page === "photobook"}
        <PhotobookDetail id={rt.id} />
      {:else if dbSubTab === "photobooks"}
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
    grid-template-columns: 280px 1fr;
    grid-template-rows: auto 1fr;
    height: 100vh;
    width: 100vw;
    background: var(--bg);
  }
  .titlebar {
    grid-column: 1 / -1;
    background: var(--header-bg);
    border-bottom: 1px solid var(--border);
    padding: 12px 24px;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 2px;
  }
  .titlebar-title {
    font-size: 2rem;
    font-weight: bold;
    color: var(--accent);
  }
  .titlebar-subtitle {
    font-size: 1rem;
    font-style: italic;
    color: var(--text-secondary);
  }
  .sidebar {
    background: var(--panel);
    border-right: 1px solid var(--border);
    padding: 20px 20px 0 20px;
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    overflow: hidden;
  }
  .sidebar-title {
    font-size: 1rem;
    font-weight: bold;
    color: var(--accent);
    letter-spacing: 0.05em;
    text-transform: uppercase;
    flex-shrink: 0;
    padding-bottom: 0.25rem;
  }
  .sidebar-scroll {
    flex: 1;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    padding-top: 0.25rem;
  }
  .sidebar-scroll > :first-child {
    padding-top: 0.25rem;
  }
  .section {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }
  .section-title {
    font-size: 0.75rem;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  .run-section {
    flex-shrink: 0;
    padding: 0.5rem 0 20px 0;
  }

  .main {
    flex: 1;
    display: flex;
    flex-direction: column;
    padding: 24px;
    overflow: hidden;
  }
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
    font-size: 1rem;
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
    font-size: 0.85rem;
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
  }
  .theme-toggle:hover {
    background: var(--panel-2);
    color: var(--text-primary);
  }
  .right-content {
    flex: 1;
    display: flex;
    flex-direction: column;
    min-height: 0;
  }
</style>
