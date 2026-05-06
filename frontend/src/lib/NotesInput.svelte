<script lang="ts">
  import { notesField } from "./stores/pipeline";

  let notes: string = $state("");

  function handleInput() {
    notesField.set(notes);
  }
</script>

<div class="notes">
  <textarea
    id="notes-input"
    bind:value={notes}
    oninput={handleInput}
    placeholder="Optionale Notizen manuell hier hinzufügen"
    rows={5}
  ></textarea>
</div>

<style>
  .notes {
    display: flex;
    flex-direction: column;
  }
  textarea {
    resize: vertical;
    min-height: 4rem;
  }
</style>
