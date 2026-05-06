<svelte:options runes />

<script lang="ts">
  import { pipelineMode } from "./stores/pipeline";
  import WildcardCount from "./WildcardCount.svelte";
  import LengthSelector from "./LengthSelector.svelte";
  import StyleSelector from "./StyleSelector.svelte";
  import PdfExportCheckbox from "./PdfExportCheckbox.svelte";
  import PhotobookSizeSelector from "./PhotobookSizeSelector.svelte";

  let current = $derived($pipelineMode);

  function select(mode: "blog" | "photobook") {
    pipelineMode.set(mode);
  }
</script>

<div class="settings-tabs">
  <span class="settings-label">Einstellungen</span>

  <div class="tabs">
    <button
      class="tab"
      class:active={current === "blog"}
      onclick={() => select("blog")}
    >
      Blog
    </button>
    <button
      class="tab"
      class:active={current === "photobook"}
      onclick={() => select("photobook")}
    >
      Fotobuch
    </button>
  </div>

  <div class="content">
    {#if current === "blog"}
      <WildcardCount />
      <LengthSelector />
      <StyleSelector />
      <PdfExportCheckbox />
    {:else}
      <PhotobookSizeSelector />
      <div class="pdf-info">
        PDF-Export immer aktiv
      </div>
    {/if}
  </div>
</div>

<style>
  .settings-tabs {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }
  .settings-label {
    font-size: 0.75rem;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  .tabs {
    display: flex;
    gap: 0.25rem;
  }
  .tab {
    flex: 1;
    padding: 0.4rem 0.75rem;
    background: var(--bg);
    color: var(--text-muted);
    font-size: 0.7rem;
    font-weight: 500;
    text-align: center;
    border: 1px solid var(--border);
    border-radius: 3px;
    cursor: pointer;
    transition: background 0.15s, color 0.15s;
  }
  .tab.active {
    background: var(--accent);
    color: white;
    border-color: var(--accent);
    font-weight: bold;
  }
  .tab:hover:not(.active) {
    background: var(--surface-alt);
    color: var(--text);
  }
  .content {
    display: flex;
    flex-direction: column;
    gap: 0.6rem;
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 0.75rem;
  }
  .pdf-info {
    font-size: 0.65rem;
    color: var(--text-muted);
    font-style: italic;
    padding: 0.1rem 0;
  }
</style>
