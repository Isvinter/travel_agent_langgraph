<script lang="ts">
  let notes: string = $state("");

  export function getNotes(): string {
    return notes;
  }
</script>

<div class="notes">
  <label for="notes-input">Tour-Notizen</label>
  <textarea
    id="notes-input"
    bind:value={notes}
    placeholder="Optionale Notizen zur Tour…"
    rows={5}
  ></textarea>
</div>

<style>
  .notes {
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
  textarea {
    resize: vertical;
    min-height: 4rem;
  }
</style>
