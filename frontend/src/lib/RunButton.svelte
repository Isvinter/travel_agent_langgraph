<script lang="ts">
  import { get } from "svelte/store";
  import {
    runState,
    addLine,
    startStream,
    resetPipeline,
    selectedModel,
    pipelineFiles,
    outputDir,
    notesField,
    wildcardCount,
    articleLength,
    stylePersona,
    pdfExport,
  } from "./stores/pipeline";

  let loading: boolean = $state(false);

  async function handleRun() {
    const model = get(selectedModel);
    const { gpxFile, imageFiles, txtFile } = get(pipelineFiles);
    const dir = get(outputDir);
    const notes = get(notesField);
    const wc = get(wildcardCount);
    const length = get(articleLength);
    const persona = get(stylePersona);
    const pdf = get(pdfExport);

    if (!gpxFile) {
      addLine("validation", "error", "Keine GPX-Datei ausgewählt.");
      return;
    }

    resetPipeline();
    loading = true;

    try {
      const res = await fetch("/api/pipeline/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          model,
          output_dir: dir,
          notes,
          txt_file: txtFile || "",
          gpx_file: gpxFile,
          image_files: imageFiles,
          wildcard_max: wc,
          article_length: length,
          style_persona: persona,
          pdf_export: pdf,
        }),
      });

      if (!res.ok) {
        const err = await res.json();
        addLine("validation", "error", err.detail || "Fehler beim Starten der Pipeline.");
        loading = false;
        return;
      }

      const data = await res.json();
      startStream(data.run_id);
    } catch (e: any) {
      addLine("connection", "error", `Verbindungsfehler: ${e.message}`);
    } finally {
      loading = false;
    }
  }

  let rs = $derived($runState);
</script>

<button
  class="run-btn"
  disabled={rs === "running" || loading}
  onclick={handleRun}
>
  {#if rs === "running" || loading}
    <span class="spinner"></span>
    Läuft…
  {:else if rs === "done"}
    ✓ Abgeschlossen
  {:else if rs === "failed"}
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
