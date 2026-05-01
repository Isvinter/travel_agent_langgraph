<script lang="ts">
  let selected: string = $state("normal");

  export function getValue(): string {
    return selected;
  }

  const options = [
    { value: "short", label: "Kurz", desc: "300–650 Wörter" },
    { value: "normal", label: "Normal", desc: "650–1300 Wörter" },
    { value: "detailed", label: "Ausführlich", desc: "1300–2500 Wörter" },
  ];
</script>

<div class="length">
  <label>Artikellänge</label>
  <div class="options">
    {#each options as opt}
      <label class="option">
        <input
          type="radio"
          name="length"
          value={opt.value}
          bind:group={selected}
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
  .length {
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
  .options {
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
  }
  .option {
    display: flex;
    align-items: flex-start;
    gap: 0.5rem;
    cursor: pointer;
    text-transform: none;
    font-size: 0.8rem;
    color: var(--text);
    padding: 0.3rem 0;
  }
  .option input[type="radio"] {
    accent-color: var(--accent);
    margin-top: 0.15rem;
  }
  .option-text {
    display: flex;
    flex-direction: column;
    gap: 0.1rem;
  }
  .option-label {
    font-weight: 500;
  }
  .option-desc {
    font-size: 0.7rem;
    color: var(--text-muted);
  }
</style>
