<script lang="ts">
  let { preset = $bindable("mixed") }: { preset: string } = $props();

  const options = [
    { value: "mixed", label: "Gemischt" },
    { value: "nature_landscape", label: "Natur & Landschaft" },
    { value: "people", label: "Menschen" },
    { value: "culture", label: "Kultur & Architektur" },
  ];
</script>

<div class="preset-selector">
  <label for="calendar-preset">Thema:</label>
  <select id="calendar-preset" bind:value={preset}>
    {#each options as opt}
      <option value={opt.value}>{opt.label}</option>
    {/each}
  </select>
</div>

<style>
  .preset-selector {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }
  .preset-selector label {
    font-size: 0.7rem;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  .preset-selector select {
    padding: 0.35rem 0.5rem;
    font-size: 0.8rem;
    background: var(--input-bg, var(--surface));
    color: var(--text);
    border: 1px solid var(--border);
    border-radius: var(--radius);
  }
</style>
