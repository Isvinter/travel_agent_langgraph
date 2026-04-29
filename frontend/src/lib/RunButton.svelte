<script lang="ts">
  import { pipeline } from "./stores/pipeline";

  let { getModel, getFiles, getOutputDir, getNotes }: {
    getModel: () => string;
    getFiles: () => { gpxFile: string; imageFiles: string[]; txtFile: string | null };
    getOutputDir: () => string;
    getNotes: () => string;
  } = $props();

  let loading: boolean = $state(false);

  async function handleRun() {
    const model = getModel();
    const { gpxFile, imageFiles } = getFiles();
    const outputDir = getOutputDir();
    const notes = getNotes();

    if (!gpxFile) {
      pipeline.addLine("validation", "error", "Keine GPX-Datei ausgewählt.");
      return;
    }

    pipeline.reset();
    loading = true;

    try {
      const res = await fetch("/api/pipeline/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          model,
          output_dir: outputDir,
          notes,
          gpx_file: gpxFile,
          image_files: imageFiles,
        }),
      });

      if (!res.ok) {
        const err = await res.json();
        pipeline.addLine("validation", "error", err.detail || "Fehler beim Starten der Pipeline.");
        loading = false;
        return;
      }

      const data = await res.json();
      pipeline.startStream(data.run_id);
    } catch (e: any) {
      pipeline.addLine("connection", "error", `Verbindungsfehler: ${e.message}`);
    } finally {
      loading = false;
    }
  }

  let runState = $derived($pipeline.runState);
</script>

<button
  class="run-btn"
  disabled={runState === "running" || loading}
  onclick={handleRun}
>
  {#if runState === "running" || loading}
    <span class="spinner"></span>
    Läuft…
  {:else if runState === "done"}
    ✓ Abgeschlossen
  {:else if runState === "failed"}
    ✗ Fehlgeschlagen — Erneut
  {:else}
    ▶ Pipeline starten
  {/if}
</button>

<style>
  .run-btn {
    width: 100%;
    padding: 0.75rem;
    background: var(--accent);
    color: white;
    font-weight: bold;
    letter-spacing: 0.03em;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
    transition: background 0.2s;
  }
  .run-btn:hover:not(:disabled) {
    background: var(--accent-hover);
  }
  .run-btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
  .spinner {
    width: 14px;
    height: 14px;
    border: 2px solid rgba(255, 255, 255, 0.3);
    border-top-color: white;
    border-radius: 50%;
    animation: spin 0.6s linear infinite;
  }
  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }
</style>
