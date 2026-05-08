<svelte:options runes />

<script lang="ts">
  import { onMount } from "svelte";
  import { selectedModel } from "./stores/pipeline";

  let models: string[] = $state([]);
  let selected: string = $state("");
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
    if (selected) {
      selectedModel.set(selected);
    }
  }
</script>

<div class="selector">
  {#if models.length === 0 && !fetchError}
    <select disabled><option>Modelle werden geladen…</option></select>
  {:else if models.length === 0 && fetchError}
    <select disabled><option>Fehler beim Laden der Modelle</option></select>
  {:else}
    <select id="model-select" bind:value={selected} onchange={handleModelChange}>
      {#each models as m}
        <option value={m}>{m}</option>
      {/each}
    </select>
  {/if}
</div>

<style>
  .selector {
    display: flex;
    flex-direction: column;
  }
  select {
    width: 100%;
  }
</style>
