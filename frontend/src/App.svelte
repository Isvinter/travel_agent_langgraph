<svelte:options runes />

<script lang="ts">
  import { route, navigateTo } from "./lib/stores/router";
  import { runState } from "./lib/stores/pipeline";
  import ModelSelector from "./lib/ModelSelector.svelte";
  import FileDropZone from "./lib/FileDropZone.svelte";
  import OutputDirInput from "./lib/OutputDirInput.svelte";
  import NotesInput from "./lib/NotesInput.svelte";
  import SettingsTabs from "./lib/SettingsTabs.svelte";
  import RunButton from "./lib/RunButton.svelte";
  import OutputWindow from "./lib/OutputWindow.svelte";
  import ArticleList from "./lib/ArticleList.svelte";
  import ArticleDetail from "./lib/ArticleDetail.svelte";

  let rt = $derived($route);
  let rightTab = $derived(rt.page === "pipeline" ? "pipeline" : "datenbank");

  function switchRightTab(tab: "pipeline" | "datenbank") {
    if (tab === "pipeline") {
      navigateTo({ page: "pipeline" });
    } else {
      navigateTo({ page: "articles" });
    }
  }

  $effect(() => {
    if ($runState === "running" && rt.page !== "pipeline") {
      navigateTo({ page: "pipeline" });
    }
  });

</script>

<div class="layout">
  <!-- LINKE SIDEBAR -->
  <aside class="sidebar">
    <h1 class="title">Travel Agent</h1>

    <ModelSelector />
    <FileDropZone />
    <NotesInput />
    <OutputDirInput />
    <SettingsTabs />

    <div class="run-section">
      <RunButton />
    </div>
  </aside>

  <!-- RECHTE SEITE -->
  <main class="main">
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
    </nav>

    <div class="right-content">
      {#if rightTab === "pipeline"}
        <OutputWindow />
      {:else if rt.page === "article"}
        <ArticleDetail id={rt.id} />
      {:else}
        <ArticleList />
      {/if}
    </div>
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
  }
  .title {
    font-size: 1rem;
    font-weight: bold;
    color: var(--accent);
    letter-spacing: 0.05em;
    text-transform: uppercase;
  }
  .run-section {
    margin-top: auto;
    padding-top: 0.25rem;
  }

  .main {
    flex: 1;
    display: flex;
    flex-direction: column;
    padding: 1rem;
    overflow: hidden;
  }
  .right-tabs {
    display: flex;
    gap: 0.25rem;
    margin-bottom: 0.75rem;
    flex-shrink: 0;
  }
  .right-tab {
    padding: 0.5rem 1rem;
    background: var(--surface);
    color: var(--text-muted);
    font-size: 0.8rem;
    font-weight: 500;
    border: 1px solid var(--border);
    border-radius: 4px;
    cursor: pointer;
    transition: background 0.15s, color 0.15s;
  }
  .right-tab.active {
    background: var(--accent);
    color: white;
    border-color: var(--accent);
  }
  .right-tab:hover:not(.active) {
    background: var(--surface-alt);
    color: var(--text);
  }
  .right-content {
    flex: 1;
    display: flex;
    flex-direction: column;
    min-height: 0;
  }
</style>
