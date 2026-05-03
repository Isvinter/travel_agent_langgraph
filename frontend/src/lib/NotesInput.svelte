<script lang="ts">
  import { notesField } from "./stores/pipeline";

  let notes: string = $state("");

  function handleInput() {
    notesField.set(notes);
  }
</script>

<div class="notes">
  <label for="notes-input">Tour-Notizen</label>
  <textarea
    id="notes-input"
    bind:value={notes}
    oninput={handleInput}
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
