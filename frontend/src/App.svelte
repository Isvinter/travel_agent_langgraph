<svelte:options runes />

<script lang="ts">
  import { route, navigateTo } from "./lib/stores/router";
  import { pipelineMode } from "./lib/stores/pipeline";
  import ModelSelector from "./lib/ModelSelector.svelte";
  import FileDropZone from "./lib/FileDropZone.svelte";
  import OutputDirInput from "./lib/OutputDirInput.svelte";
  import ModeTabs from "./lib/ModeTabs.svelte";
  import LengthSelector from "./lib/LengthSelector.svelte";
  import StyleSelector from "./lib/StyleSelector.svelte";
  import PdfExportCheckbox from "./lib/PdfExportCheckbox.svelte";
  import NotesInput from "./lib/NotesInput.svelte";
  import WildcardCount from "./lib/WildcardCount.svelte";
  import PhotobookSizeSelector from "./lib/PhotobookSizeSelector.svelte";
  import RunButton from "./lib/RunButton.svelte";
  import OutputWindow from "./lib/OutputWindow.svelte";
  import ArticleList from "./lib/ArticleList.svelte";
  import ArticleDetail from "./lib/ArticleDetail.svelte";

  let rt = $derived($route);
  let currentMode = $derived($pipelineMode);
</script>

<div class="layout">
  <aside class="sidebar" class:sidebar-wide={rt.page === "pipeline"}>
    <h1 class="title">Travel Agent</h1>

    <nav class="nav-tabs">
      <button
        class="nav-tab"
        class:active={rt.page === "pipeline"}
        onclick={() => navigateTo({ page: "pipeline" })}
      >
        Pipeline
      </button>
      <button
        class="nav-tab"
        class:active={rt.page === "articles" || rt.page === "article"}
        onclick={() => navigateTo({ page: "articles" })}
      >
        Artikel
      </button>
    </nav>

    {#if rt.page === "pipeline"}
      <ModeTabs />

      <ModelSelector />
      <FileDropZone />
      <OutputDirInput />

      <div class="columns">
        <div class="column" class:inactive={currentMode !== "blog"}>
          <div class="column-badge">Blog</div>
          <NotesInput />
          <WildcardCount />
          <LengthSelector />
          <StyleSelector />
          <PdfExportCheckbox />
          <div class="run-section">
            <RunButton mode="blog" />
          </div>
        </div>

        <div class="column" class:inactive={currentMode !== "photobook"}>
          <div class="column-badge">Fotobuch</div>
          <PhotobookSizeSelector />
          <div class="pdf-info">
            PDF-Export immer aktiv
          </div>
          <div class="run-section">
            <RunButton mode="photobook" />
          </div>
        </div>
      </div>
    {/if}
  </aside>

  <main class="main">
    {#if rt.page === "pipeline"}
      <OutputWindow />
    {:else if rt.page === "articles"}
      <ArticleList />
    {:else if rt.page === "article"}
      <ArticleDetail id={rt.id} />
    {/if}
  </main>
</div>

<style>
  .layout {
    display: flex;
    height: 100vh;
    width: 100vw;
  }
  .sidebar {
    width: 340px;
    min-width: 340px;
    background: var(--surface);
    border-right: 1px solid var(--border);
    padding: 1.25rem;
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    overflow-y: auto;
    transition: width 0.2s;
  }
  .sidebar.sidebar-wide {
    width: 680px;
    min-width: 680px;
  }
  .title {
    font-size: 1rem;
    font-weight: bold;
    color: var(--accent);
    letter-spacing: 0.05em;
    text-transform: uppercase;
  }
  .nav-tabs {
    display: flex;
    gap: 0.25rem;
  }
  .nav-tab {
    flex: 1;
    padding: 0.5rem 0.75rem;
    background: var(--bg);
    color: var(--text-muted);
    font-size: 0.8rem;
  }
  .nav-tab.active {
    background: var(--accent);
    color: white;
  }
  .nav-tab:hover:not(.active) {
    background: var(--surface-alt);
    color: var(--text);
  }

  .columns {
    display: flex;
    gap: 0.75rem;
    flex: 1;
    min-height: 0;
  }
  .column {
    flex: 1;
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 0.75rem;
    display: flex;
    flex-direction: column;
    gap: 0.6rem;
    position: relative;
    transition: opacity 0.2s;
  }
  .column.inactive {
    opacity: 0.45;
    pointer-events: none;
  }
  .column-badge {
    position: absolute;
    top: -0.55rem;
    left: 0.5rem;
    background: var(--bg);
    color: var(--accent);
    font-size: 0.6rem;
    font-weight: bold;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    padding: 0 0.35rem;
  }
  .run-section {
    margin-top: auto;
    padding-top: 0.25rem;
  }
  .pdf-info {
    font-size: 0.65rem;
    color: var(--text-muted);
    font-style: italic;
    padding: 0.1rem 0;
  }

  .main {
    flex: 1;
    display: flex;
    flex-direction: column;
    padding: 1rem;
    overflow: hidden;
  }
</style>
