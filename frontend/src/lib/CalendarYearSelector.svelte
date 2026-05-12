<script lang="ts">
  let { year = $bindable(new Date().getFullYear()) }: { year: number } = $props();

  const years = Array.from({ length: 10 }, (_, i) => new Date().getFullYear() + i);
</script>

<div class="year-selector">
  <label for="calendar-year">Jahr:</label>
  <select id="calendar-year" bind:value={year}>
    {#each years as y}
      <option value={y}>{y}</option>
    {/each}
  </select>
</div>

<style>
  .year-selector {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }
  .year-selector label {
    font-size: 0.7rem;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  .year-selector select {
    padding: 0.35rem 0.5rem;
    font-size: 0.8rem;
    background: var(--input-bg, var(--surface));
    color: var(--text);
    border: 1px solid var(--border);
    border-radius: var(--radius);
  }
</style>
