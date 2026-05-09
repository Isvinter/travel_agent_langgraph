<svelte:options runes />

<script lang="ts">
  import { photobookPreset } from "./stores/pipeline";

  let selected: string = $state("mixed");

  $effect(() => {
    selected = $photobookPreset;
  });

  const options = [
    { value: "mixed", label: "Gemischt", desc: "Standard — keine Einschränkung" },
    { value: "nature_outdoor", label: "Natur & Outdoor", desc: "Sport, Landschaft, Action" },
    { value: "culture_architecture", label: "Kultur & Architektur", desc: "Gebäude, Geschichte" },
    { value: "people", label: "Menschen", desc: "Porträts, Gruppen, Emotionen" },
    { value: "nature_collage", label: "Bildercollage", desc: "Nur Naturbilder, kein Text" },
  ];

  function handleChange() {
    photobookPreset.set(
      selected as "nature_outdoor" | "culture_architecture" | "people" | "nature_collage" | "mixed"
    );
  }
</script>

<div class="preset">
  <span class="section-label">Preset</span>
  <div class="options-compact">
    {#each options as opt}
      <label class="option-compact">
        <input
          type="radio"
          name="photobook-preset"
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
  .preset {
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
