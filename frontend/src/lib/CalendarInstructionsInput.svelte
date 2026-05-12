<script lang="ts">
  let { instructions = $bindable("") }: { instructions: string } = $props();
</script>

<div class="instructions-input">
  <label for="calendar-instructions">Anweisungen (optional):</label>
  <textarea
    id="calendar-instructions"
    bind:value={instructions}
    placeholder="z.B. Bevorzuge Sonnenaufgänge, keine verschwommenen Bilder..."
    rows="3"
  ></textarea>
</div>

<style>
  .instructions-input {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }
  .instructions-input label {
    font-size: 0.7rem;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  .instructions-input textarea {
    padding: 0.35rem 0.5rem;
    font-size: 0.75rem;
    background: var(--input-bg, var(--surface));
    color: var(--text);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    resize: vertical;
    font-family: inherit;
  }
</style>
