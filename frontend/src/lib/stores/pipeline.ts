import { writable, get } from "svelte/store";

export type RunState = "idle" | "running" | "done" | "failed";

export interface LogLine {
  timestamp: string;
  stage: string;
  status: string;
  message: string;
}

export interface RunResult {
  success: boolean;
  markdown?: string;
  html?: string;
  file_paths?: Record<string, string>;
  error?: string;
  draft_id?: number;
  article_id?: number;
}

export interface StepState {
  stage: string;
  label: string;
  status: "pending" | "running" | "done" | "error";
  message?: string;
  timestamp?: string;
}

// Deutsche Labels für die Pipeline-Schritte
const STEP_LABELS: Record<string, string> = {
  process_gpx: "GPX-Datei analysiert",
  load_images: "Bilder geladen",
  extract_metadata: "Metadaten extrahiert",
  clustering_images: "Bilder geclustert",
  generate_map_image: "Karte generiert",
  load_tour_notes: "Notizen laden",
  select_images: "Bilder auswählen",
  generate_blog_post: "Blogpost generiert",
  enrich_weather: "Wetterdaten abrufen",
  enrich_poi: "POIs suchen",
  review_content: "Inhalte prüfen",
  design_blogpost: "Design anwenden",
  persist_article: "Artikel speichern",
  save_draft: "Entwurf speichern",
  generate_pdf: "PDF generieren",
  generate_enriched_map: "Angereicherte Karte",
  select_photobook_images: "Fotobuch-Bilder auswählen",
  plan_photobook: "Fotobuch-Layout planen",
  generate_photobook: "Fotobuch-Seiten generieren",
  render_photobook: "Fotobuch rendern",
  generate_photobook_pdf: "Fotobuch-PDF erstellen",
  persist_photobook: "Fotobuch speichern",
};

// Session-ID lazy erzeugen (kein Side-Effect beim Modul-Import).
let _sessionId: string | null = null;

function getSessionId(): string {
  if (!_sessionId) {
    _sessionId = crypto.randomUUID();
    document.cookie = `session_id=${_sessionId};path=/;SameSite=Lax`;
  }
  return _sessionId;
}

export const logLines = writable<LogLine[]>([]);
export const pipelineSteps = writable<StepState[]>([]);
export const runState = writable<RunState>("idle");
export const currentRunId = writable<string | null>(null);
export const result = writable<RunResult | null>(null);
export const sessionId = writable<string>(getSessionId());

// Pipeline form fields — shared via stores (Svelte 5 runes mode:
// export function creates props, not callable instance methods via bind:this)
export const selectedModel = writable<string>("");
export const pipelineFiles = writable<{ gpxFile: string; imageFiles: string[]; txtFile: string | null }>({
  gpxFile: "",
  imageFiles: [],
  txtFile: null,
});
export const outputDir = writable<string>("output");
export const notesField = writable<string>("");
export const wildcardCount = writable<number>(12);
export const articleLength = writable<string>("normal");
export const stylePersona = writable<string>("mountain_veteran");
export const pdfExport = writable<boolean>(false);
export const pipelineMode = writable<"blog" | "photobook">("blog");
export const photobookSize = writable<"short" | "normal" | "detailed">("normal");
export const photobookPreset = writable<
  "nature_outdoor" | "culture_architecture" | "people" | "nature_collage" | "mixed"
>("mixed");

export const reviewEnabled = writable<boolean>(false);
export const currentDraftId = writable<number | null>(null);

let eventSource: EventSource | null = null;

export function addLine(stage: string, status: string, message: string) {
  const timestamp = new Date().toLocaleTimeString("de-DE");

  // Bestehende logLines weiter pflegen
  logLines.update((lines) => [...lines, { timestamp, stage, status, message }]);

  // Steps aggregieren: ein Eintrag pro Stage, Status wird aktualisiert
  // Meta-Stages wie __done__ und connection nicht in der Timeline anzeigen
  if (stage.startsWith("__") || stage === "connection") return;

  pipelineSteps.update((steps) => {
    const idx = steps.findIndex((s) => s.stage === stage);
    const label = STEP_LABELS[stage] || stage;
    const stepStatus = status === "done" || status === "success" ? "done"
      : status === "error" ? "error"
      : status === "running" ? "running"
      : "pending";

    if (idx >= 0) {
      const updated = [...steps];
      updated[idx] = { ...updated[idx], status: stepStatus, message, timestamp };
      return updated;
    }
    return [...steps, { stage, label, status: stepStatus, message, timestamp }];
  });
}

export function startStream(runId: string) {
  runState.set("running");
  currentRunId.set(runId);

  stopStream();  // Vorhandene Verbindung schliessen bevor neue geöffnet wird

  const url = `/api/pipeline/stream/${runId}`;
  eventSource = new EventSource(url);

  eventSource.addEventListener("progress", (e: MessageEvent) => {
    const data = JSON.parse(e.data);
    addLine(data.stage, data.status, data.message);
  });

  eventSource.addEventListener("error", (e: MessageEvent) => {
    if (e.data) {
      const data = JSON.parse(e.data);
      addLine(data.stage, "error", data.message);
    }
  });

  eventSource.addEventListener("done", async (e: MessageEvent) => {
    eventSource?.close();
    const data = JSON.parse(e.data);
    const isSuccess = data.status === "success";
    addLine("__done__", data.status, `Pipeline ${isSuccess ? "erfolgreich" : "fehlgeschlagen"}.`);
    runState.set(isSuccess ? "done" : "failed");

    if (data.pdf_available) {
      if (data.article_id) {
        window.open(`/api/articles/${data.article_id}/pdf`, "_blank");
      } else if (data.photobook_id) {
        window.open(`/api/photobooks/${data.photobook_id}/pdf`, "_blank");
      }
    }

    if (data.draft_id) {
      currentDraftId.set(data.draft_id);
      result.set({
        success: true,
        draft_id: data.draft_id,
      });
    } else {
      try {
        const res = await fetch(`/api/pipeline/result/${runId}`);
        if (res.ok) {
          result.set(await res.json());
        }
      } catch (err) {
        console.error("Failed to fetch result:", err);
      }
    }
  });

  eventSource.onerror = () => {
    if (eventSource?.readyState === EventSource.CLOSED) {
      const state = get(runState);
      if (state !== "done" && state !== "failed" && state !== "idle") {
        addLine("connection", "error", "Verbindung zum Server verloren.");
        runState.set("failed");
      }
    }
  };
}

export function stopStream() {
  eventSource?.close();
  eventSource = null;
}

export function resetPipeline() {
  stopStream();
  logLines.set([]);
  pipelineSteps.set([]);
  runState.set("idle");
  currentRunId.set(null);
  result.set(null);
  currentDraftId.set(null);
}
