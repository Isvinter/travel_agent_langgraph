<script lang="ts">
  import { onMount } from "svelte";

  let models: string[] = $state([]);
  let selected: string = $state("");
  let custom: string = $state("");
  let useCustom: boolean = $state(false);

  onMount(async () => {
    try {
      const res = await fetch("/api/models");
      const data = await res.json();
      models = data.models;
      if (models.length > 0) {
        selected = models[0];
      }
    } catch (e) {
      console.error("Failed to fetch models:", e);
    }
  });

  export function getModel(): string {
    return useCustom ? custom : selected;
  }
</script>

<div class="selector">
  <label for="model-select">Modell</label>
  <select id="model-select" bind:value={selected} disabled={useCustom}>
    {#each models as m}
      <option value={m}>{m}</option>
    {/each}
  </select>
  <div class="custom-row">
    <label>
      <input type="checkbox" bind:checked={useCustom} />
      eigenes Modell
    </label>
    {#if useCustom}
      <input
        type="text"
        bind:value={custom}
        placeholder="Modellnamen eingeben…"
        class="custom-input"
      />
    {/if}
  </div>
</div>

<style>
  .selector {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }
  label {
    font-size: 0.75rem;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  select {
    width: 100%;
  }
  .custom-row {
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
    font-size: 0.8rem;
  }
  .custom-row label {
    text-transform: none;
    color: var(--text);
    display: flex;
    align-items: center;
    gap: 0.4rem;
    cursor: pointer;
  }
  .custom-input {
    width: 100%;
  }
</style>
