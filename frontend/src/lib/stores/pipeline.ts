import { writable, derived } from "svelte/store";

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

function createPipelineStore() {
  const logLines = writable<LogLine[]>([]);
  const runState = writable<RunState>("idle");
  const currentRunId = writable<string | null>(null);
  const result = writable<RunResult | null>(null);
  // Regenerate on each page load; set cookie so backend receives it.
  // Cookie lifetime: session only (deleted when browser closes).
  const newSessionId = (() => {
    const id = crypto.randomUUID();
    document.cookie = `session_id=${id};path=/;SameSite=Lax`;
    return id;
  })();
  const sessionId = writable<string>(newSessionId);

  let eventSource: EventSource | null = null;

  function addLine(stage: string, status: string, message: string) {
    const line: LogLine = {
      timestamp: new Date().toLocaleTimeString("de-DE"),
      stage,
      status,
      message,
    };
    logLines.update((lines) => [...lines, line]);
  }

  function startStream(runId: string) {
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
      // If no data, it's a connection error — EventSource will auto-reconnect
    });

    eventSource.addEventListener("done", async (e: MessageEvent) => {
      eventSource?.close();
      const data = JSON.parse(e.data);
      addLine("__done__", data.status, `Pipeline ${data.status === "success" ? "erfolgreich" : "fehlgeschlagen"}.`);
      runState.set(data.status === "success" ? "done" : "failed");

      // Fetch the final result
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
      // EventSource handles reconnection automatically; if it fails permanently,
      // the browser will stop trying. We add a sentinel log line.
      if (eventSource?.readyState === EventSource.CLOSED) {
        addLine("connection", "error", "Verbindung zum Server verloren.");
        runState.set("failed");
      }
    };
  }

  function stopStream() {
    eventSource?.close();
    eventSource = null;
  }

  function reset() {
    stopStream();
    logLines.set([]);
    runState.set("idle");
    currentRunId.set(null);
    result.set(null);
  }

  return {
    logLines,
    runState,
    currentRunId,
    result,
    sessionId,
    addLine,
    startStream,
    stopStream,
    reset,
  };
}

export const pipeline = createPipelineStore();
