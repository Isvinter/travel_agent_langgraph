<svelte:options runes />

<script lang="ts">
  import { route, navigateTo } from "./lib/stores/router";
  import ModelSelector from "./lib/ModelSelector.svelte";
  import FileDropZone from "./lib/FileDropZone.svelte";
  import OutputDirInput from "./lib/OutputDirInput.svelte";
  import NotesInput from "./lib/NotesInput.svelte";
  import WildcardCount from "./lib/WildcardCount.svelte";
  import LengthSelector from "./lib/LengthSelector.svelte";
  import StyleSelector from "./lib/StyleSelector.svelte";
  import RunButton from "./lib/RunButton.svelte";
  import OutputWindow from "./lib/OutputWindow.svelte";
  import ArticleList from "./lib/ArticleList.svelte";
  import ArticleDetail from "./lib/ArticleDetail.svelte";

  let modelSelector: ModelSelector;
  let fileDropZone: FileDropZone;
  let outputDirInput: OutputDirInput;
  let notesInput: NotesInput;
  let wildcardCount: WildcardCount;
  let lengthSelector: LengthSelector;
  let styleSelector: StyleSelector;

  let rt = $derived($route);
</script>

<div class="layout">
  <aside class="sidebar">
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
      <ModelSelector bind:this={modelSelector} />
      <FileDropZone bind:this={fileDropZone} />
      <OutputDirInput bind:this={outputDirInput} />
      <NotesInput bind:this={notesInput} />
      <WildcardCount bind:this={wildcardCount} />
      <LengthSelector bind:this={lengthSelector} />
      <StyleSelector bind:this={styleSelector} />

      <div class="run-section">
        <RunButton
          getModel={() => modelSelector.getModel()}
          getFiles={() => fileDropZone.getFiles()}
          getOutputDir={() => outputDirInput.getOutputDir()}
          getNotes={() => notesInput.getNotes()}
          getWildcardMax={() => wildcardCount.getValue()}
          getArticleLength={() => lengthSelector.getValue()}
          getStylePersona={() => styleSelector.getValue()}
        />
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
    gap: 1.25rem;
    overflow-y: auto;
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
  .run-section {
    margin-top: auto;
    padding-top: 0.5rem;
  }
  .main {
    flex: 1;
    display: flex;
    flex-direction: column;
    padding: 1rem;
    overflow: hidden;
  }
</style>
