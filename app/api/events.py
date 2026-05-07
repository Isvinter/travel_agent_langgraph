"""SSE event emitter for pipeline progress tracking."""
import asyncio
import json
import time
from typing import Optional

RUN_TTL_SECONDS = 600  # Runs älter als 10 Minuten werden automatisch bereinigt


class PipelineEventManager:
    """Manages per-run asyncio.Queues for SSE streaming."""

    def __init__(self):
        self._runs: dict[str, asyncio.Queue] = {}
        self._results: dict[str, dict] = {}
        self._timestamps: dict[str, float] = {}
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def set_loop(self, loop: asyncio.AbstractEventLoop):
        """Store the event loop reference for thread-safe queue access."""
        self._loop = loop

    def create_run(self, run_id: str):
        """Initialise a queue and result slot for a new pipeline run."""
        self._runs[run_id] = asyncio.Queue()
        self._timestamps[run_id] = time.time()
        self._schedule_cleanup(run_id)

    def emit(self, run_id: str, stage: str, status: str, message: str):
        """Emit a progress event. Thread-safe — callable from executor threads."""
        queue = self._runs.get(run_id)
        if queue is None or self._loop is None:
            return
        event = {"stage": stage, "status": status, "message": message}
        self._loop.call_soon_threadsafe(queue.put_nowait, event)

    def complete_run(self, run_id: str, status: str, output_dir: str = "",
                     article_id: int = None, photobook_id: int = None,
                     pdf_available: bool = False):
        """Signal pipeline completion and store the result."""
        queue = self._runs.get(run_id)
        if queue is None or self._loop is None:
            return
        event = {"stage": "__done__", "status": status, "output_dir": output_dir}
        if article_id is not None:
            event["article_id"] = article_id
        if photobook_id is not None:
            event["photobook_id"] = photobook_id
        event["pdf_available"] = pdf_available
        self._loop.call_soon_threadsafe(queue.put_nowait, event)

    def store_result(self, run_id: str, result: dict):
        """Store the final pipeline result for later retrieval."""
        self._results[run_id] = result

    def get_result(self, run_id: str) -> Optional[dict]:
        """Retrieve the stored pipeline result."""
        return self._results.get(run_id)

    async def stream_events(self, run_id: str):
        """Async generator yielding SSE-formatted events for a given run."""
        queue = self._runs.get(run_id)
        if queue is None:
            yield {"event": "error", "data": json.dumps({"message": f"Run {run_id} not found"})}
            return
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=300)
                except asyncio.TimeoutError:
                    yield {"event": "error", "data": json.dumps({"message": "Pipeline timed out after 5 minutes"})}
                    break
                if event["stage"] == "__done__":
                    yield {"event": "done", "data": json.dumps(event)}
                    break
                elif event["status"] == "error":
                    yield {"event": "error", "data": json.dumps(event)}
                else:
                    yield {"event": "progress", "data": json.dumps(event)}
        finally:
            self._cleanup_run(run_id)

    def _cleanup_run(self, run_id: str):
        """Entfernt alle Daten für einen Run."""
        self._runs.pop(run_id, None)
        self._results.pop(run_id, None)
        self._timestamps.pop(run_id, None)

    def _schedule_cleanup(self, run_id: str):
        """Plant die automatische Bereinigung eines Runs nach TTL-Ablauf."""
        if self._loop is None:
            return

        async def _cleanup_after_ttl():
            await asyncio.sleep(RUN_TTL_SECONDS)
            if run_id in self._runs:
                self._cleanup_run(run_id)

        self._loop.create_task(_cleanup_after_ttl())


# Singleton instance
event_manager = PipelineEventManager()
