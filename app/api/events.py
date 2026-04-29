"""SSE event emitter for pipeline progress tracking."""
import asyncio
import json
import uuid
from typing import Optional


class PipelineEventManager:
    """Manages per-run asyncio.Queues for SSE streaming."""

    def __init__(self):
        self._runs: dict[str, asyncio.Queue] = {}
        self._results: dict[str, dict] = {}
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def set_loop(self, loop: asyncio.AbstractEventLoop):
        """Store the event loop reference for thread-safe queue access."""
        self._loop = loop

    def create_run(self, run_id: str):
        """Initialise a queue and result slot for a new pipeline run."""
        self._runs[run_id] = asyncio.Queue()

    def emit(self, run_id: str, stage: str, status: str, message: str):
        """Emit a progress event. Thread-safe — callable from executor threads."""
        queue = self._runs.get(run_id)
        if queue is None or self._loop is None:
            return
        event = {"stage": stage, "status": status, "message": message}
        self._loop.call_soon_threadsafe(queue.put_nowait, event)

    def complete_run(self, run_id: str, status: str, output_dir: str = ""):
        """Signal pipeline completion and store the result."""
        queue = self._runs.get(run_id)
        if queue is None or self._loop is None:
            return
        event = {"stage": "__done__", "status": status, "output_dir": output_dir}
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
        while True:
            event = await queue.get()
            if event["stage"] == "__done__":
                yield {"event": "done", "data": json.dumps(event)}
                break
            elif event["status"] == "error":
                yield {"event": "error", "data": json.dumps(event)}
            else:
                yield {"event": "progress", "data": json.dumps(event)}


# Singleton instance
event_manager = PipelineEventManager()
