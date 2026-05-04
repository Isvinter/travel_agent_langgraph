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
}

// Regenerate on each page load; set cookie so backend receives it.
// Cookie lifetime: session only (deleted when browser closes).
const newSessionId = (() => {
  const id = crypto.randomUUID();
  document.cookie = `session_id=${id};path=/;SameSite=Lax`;
  return id;
})();

export const logLines = writable<LogLine[]>([]);
export const runState = writable<RunState>("idle");
export const currentRunId = writable<string | null>(null);
export const result = writable<RunResult | null>(null);
export const sessionId = writable<string>(newSessionId);

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

let eventSource: EventSource | null = null;

export function addLine(stage: string, status: string, message: string) {
  const line: LogLine = {
    timestamp: new Date().toLocaleTimeString("de-DE"),
    stage,
    status,
    message,
  };
  logLines.update((lines) => [...lines, line]);
}

export function startStream(runId: string) {
  runState.set("running");
  currentRunId.set(runId);

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

    try {
      const res = await fetch(`/api/pipeline/result/${runId}`);
      if (res.ok) {
        result.set(await res.json());
      }
    } catch (err) {
      console.error("Failed to fetch result:", err);
    }
  });

  eventSource.onerror = () => {
    if (eventSource?.readyState === EventSource.CLOSED) {
      addLine("connection", "error", "Verbindung zum Server verloren.");
      runState.set("failed");
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
  runState.set("idle");
  currentRunId.set(null);
  result.set(null);
}
