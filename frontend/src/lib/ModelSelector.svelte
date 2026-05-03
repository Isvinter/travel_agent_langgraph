<script lang="ts">
  import { onMount } from "svelte";
  import { selectedModel } from "./stores/pipeline";

  let models: string[] = $state([]);
  let selected: string = $state("");
  let custom: string = $state("");
  let useCustom: boolean = $state(false);
  let fetchError: boolean = $state(false);

  onMount(async () => {
    try {
      const res = await fetch("/api/models");
      const data = await res.json();
      models = data.models;
      if (models.length > 0) {
        selected = models[0];
        selectedModel.set(selected);
      }
    } catch (e) {
      console.error("Failed to fetch models:", e);
      fetchError = true;
    }
  });

  function handleModelChange() {
    if (useCustom && custom) {
      selectedModel.set(custom);
    } else if (selected) {
      selectedModel.set(selected);
    }
  }

  $effect(() => {
    selected;
    if (!useCustom && selected) {
      selectedModel.set(selected);
    }
  });

  $effect(() => {
    custom;
    if (useCustom && custom) {
      selectedModel.set(custom);
    }
  });
</script>

<div class="selector">
  <label for="model-select">Modell</label>
  {#if models.length === 0 && !fetchError}
    <select disabled><option>Modelle werden geladen…</option></select>
  {:else if models.length === 0 && fetchError}
    <select disabled><option>Fehler beim Laden der Modelle</option></select>
  {:else}
    <select id="model-select" bind:value={selected} onchange={handleModelChange} disabled={useCustom}>
      {#each models as m}
        <option value={m}>{m}</option>
      {/each}
    </select>
  {/if}
  <div class="custom-row">
    <label>
      <input type="checkbox" bind:checked={useCustom} onchange={handleModelChange} />
      eigenes Modell
    </label>
    {#if useCustom}
      <input
        type="text"
        bind:value={custom}
        oninput={handleModelChange}
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
