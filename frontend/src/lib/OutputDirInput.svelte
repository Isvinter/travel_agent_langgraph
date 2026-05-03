<script lang="ts">
  import { outputDir } from "./stores/pipeline";

  let dir: string = $state("output");

  function handleInput() {
    outputDir.set(dir || "output");
  }
</script>

<div class="output-dir">
  <label for="output-dir">Ausgabe-Verzeichnis</label>
  <input id="output-dir" type="text" bind:value={dir} oninput={handleInput} placeholder="output" />
</div>

<style>
  .output-dir {
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
</style>
