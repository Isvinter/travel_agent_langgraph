<script lang="ts">
  let dir: string = $state("output");

  export function getOutputDir(): string {
    return dir || "output";
  }
</script>

<div class="output-dir">
  <label for="output-dir">Ausgabe-Verzeichnis</label>
  <input id="output-dir" type="text" bind:value={dir} placeholder="output" />
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
