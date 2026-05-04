<svelte:options runes />

<script lang="ts">
  import { pdfExport } from "./stores/pipeline";

  let checked: boolean = $state(false);

  $effect(() => {
    pdfExport.set(checked);
  });
</script>

<label class="pdf-toggle">
  <input type="checkbox" bind:checked />
  <span>Als PDF exportieren</span>
</label>

<style>
  .pdf-toggle {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.8rem;
    color: var(--text);
    cursor: pointer;
    padding: 0.25rem 0;
  }
  .pdf-toggle input[type="checkbox"] {
    width: 16px;
    height: 16px;
    accent-color: var(--accent);
    cursor: pointer;
  }
</style>
