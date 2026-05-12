<svelte:options runes />

<script lang="ts">
  import { pipelineMode, pipelineFiles } from "./stores/pipeline";
  import WildcardCount from "./WildcardCount.svelte";
  import LengthSelector from "./LengthSelector.svelte";
  import StyleSelector from "./StyleSelector.svelte";
  import ReviewCheckbox from "./ReviewCheckbox.svelte";
  import PhotobookSizeSelector from "./PhotobookSizeSelector.svelte";
  import PhotobookPresetSelector from "./PhotobookPresetSelector.svelte";
  import CalendarPresetSelector from "./CalendarPresetSelector.svelte";
  import CalendarYearSelector from "./CalendarYearSelector.svelte";
  import CalendarInstructionsInput from "./CalendarInstructionsInput.svelte";

  let current = $derived($pipelineMode);
  let hasGpx = $derived(!!$pipelineFiles.gpxFile);

  function select(mode: "blog" | "photobook" | "calendar") {
    pipelineMode.set(mode);
  }
</script>

<div class="settings-tabs">

  <div class="tabs">
    <button
      class="tab"
      class:active={current === "blog"}
      class:disabled={!hasGpx}
      onclick={() => select("blog")}
      disabled={!hasGpx}
      title={hasGpx ? "" : "GPX-Datei erforderlich"}
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
    <button
      class="tab"
      class:active={current === "calendar"}
      onclick={() => select("calendar")}
    >
      Kalender
    </button>
  </div>

  <div class="content">
    {#if current === "blog"}
      <WildcardCount />
      <LengthSelector />
      <StyleSelector />
      <ReviewCheckbox />
    {:else if current === "photobook"}
      <PhotobookSizeSelector />
      <PhotobookPresetSelector />
    {:else}
      <CalendarPresetSelector />
      <CalendarYearSelector />
      <CalendarInstructionsInput />
    {/if}
  </div>
</div>

<style>
  .settings-tabs {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }
  .tabs {
    display: flex;
    gap: 0.25rem;
  }
  .tab {
    flex: 1;
    padding: 0.4rem 0.5rem;
    background: var(--bg);
    color: var(--text-muted);
    font-size: 0.65rem;
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
  .tab.disabled,
  .tab:disabled {
    opacity: 0.35;
    cursor: not-allowed;
    background: var(--bg);
    color: var(--text-muted);
  }
  .content {
    display: flex;
    flex-direction: column;
    gap: 0.6rem;
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 0.75rem;
  }
</style>
