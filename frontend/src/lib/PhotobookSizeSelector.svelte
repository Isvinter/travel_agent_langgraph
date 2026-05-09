<svelte:options runes />

<script lang="ts">
  import { photobookSize } from "./stores/pipeline";

  let selected: string = $state("normal");

  $effect(() => {
    selected = $photobookSize;
  });

  const options = [
    { value: "short", label: "Kurz", desc: "8-12 Seiten" },
    { value: "normal", label: "Mittel", desc: "14-18 Seiten" },
    { value: "detailed", label: "Lang", desc: "20-24 Seiten" },
  ];

  function handleChange() {
    photobookSize.set(selected as "short" | "normal" | "detailed");
  }
</script>

<div class="size">
  <span class="section-label">Umfang</span>
  <div class="options-compact">
    {#each options as opt}
      <label class="option-compact">
        <input
          type="radio"
          name="photobook-size"
          value={opt.value}
          bind:group={selected}
          onchange={handleChange}
        />
        <div class="option-text">
          <span class="option-label">{opt.label}</span>
          <span class="option-desc">{opt.desc}</span>
        </div>
      </label>
    {/each}
  </div>
</div>

<style>
  .size {
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
  }
  .section-label {
    font-size: 0.7rem;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  .options-compact {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }
  .option-compact {
    display: flex;
    align-items: flex-start;
    gap: 0.4rem;
    cursor: pointer;
    font-size: 0.75rem;
    color: var(--text);
    padding: 0.2rem 0;
  }
  .option-compact input[type="radio"] {
    accent-color: var(--accent);
    margin-top: 0.12rem;
    flex-shrink: 0;
  }
  .option-text {
    display: flex;
    flex-direction: column;
    gap: 0.05rem;
  }
  .option-label {
    font-weight: 500;
  }
  .option-desc {
    font-size: 0.65rem;
    color: var(--text-muted);
  }
</style>
