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
    reviewEnabled,
    photobookSize,
    photobookPreset,
    calendarPreset,
    calendarYear,
    calendarInstructions,
    pipelineMode,
  } from "./stores/pipeline";

  let loading: boolean = $state(false);

  async function handleRun() {
    resetPipeline();

    const mode = get(pipelineMode);
    const model = get(selectedModel);
    const { gpxFile, imageFiles, txtFile } = get(pipelineFiles);
    const dir = get(outputDir);
    const notes = get(notesField);

    // Kalender: kein GPX nötig, nur Bilder
    if (mode === "calendar") {
      if (!imageFiles || imageFiles.length === 0) {
        addLine("validation", "error", "Keine Bilder ausgewählt.");
        return;
      }

      loading = true;
      try {
        const res = await fetch("/api/calendar/generate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            model,
            preset: get(calendarPreset),
            year: get(calendarYear),
            custom_instructions: get(calendarInstructions) || null,
            image_files: imageFiles,
          }),
          credentials: "include",
        });

        if (!res.ok) {
          const err = await res.json();
          addLine("validation", "error", err.detail || "Fehler beim Starten der Kalender-Generierung.");
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
      return;
    }

    // Blog braucht zwingend GPX, Fotobuch nicht
    if (mode === "blog" && !gpxFile) {
      addLine("validation", "error", "Keine GPX-Datei ausgewählt.");
      return;
    }

    // Für Fotobuch ohne GPX: nur Bilder prüfen
    if (mode === "photobook" && !gpxFile && (!imageFiles || imageFiles.length === 0)) {
      addLine("validation", "error", "Keine Bilder ausgewählt.");
      return;
    }

    loading = true;

    try {
      const body: Record<string, unknown> = {
        model,
        output_dir: dir,
        notes,
        txt_file: txtFile || "",
        gpx_file: gpxFile || "",
        image_files: imageFiles,
        mode,
      };

      if (mode === "blog") {
        body.wildcard_max = get(wildcardCount);
        body.article_length = get(articleLength);
        body.style_persona = get(stylePersona);
        body.pdf_export = get(pdfExport);
        body.review_enabled = get(reviewEnabled);
      } else {
        body.photobook_size = get(photobookSize);
        body.photobook_preset = get(photobookPreset);
      }

      const res = await fetch("/api/pipeline/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
        credentials: "include",
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
  let buttonLabel = $derived(
    rs === "done"
      ? "✓ Abgeschlossen"
      : rs === "failed"
        ? "✗ Fehlgeschlagen — Erneut"
        : "▶ Pipeline starten"
  );
</script>

<button
  class="run-btn"
  disabled={rs === "running" || loading}
  onclick={handleRun}
>
  {#if rs === "running" || loading}
    <span class="spinner"></span>
    Läuft…
  {:else}
    {buttonLabel}
  {/if}
</button>

<style>
  .run-btn {
    width: 100%;
    padding: 0.6rem;
    background: var(--accent);
    color: white;
    font-weight: bold;
    font-size: 0.75rem;
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
