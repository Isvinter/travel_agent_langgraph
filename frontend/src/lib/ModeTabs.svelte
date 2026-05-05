<svelte:options runes />

<script lang="ts">
  import { pipelineMode } from "./stores/pipeline";

  let current = $derived($pipelineMode);

  function select(mode: "blog" | "photobook") {
    pipelineMode.set(mode);
  }

</script>

<div class="mode-tabs">
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

<style>
  .mode-tabs {
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
</style>
