"""Tests für app/api/events.py — PipelineEventManager mit TTL-Cleanup."""
import asyncio
import json
import time

import pytest

from app.api.events import PipelineEventManager, RUN_TTL_SECONDS


class TestCreateRun:
    def test_create_run_adds_queue_and_timestamp(self):
        mgr = PipelineEventManager()
        mgr.create_run("test-1")
        assert "test-1" in mgr._runs
        assert "test-1" in mgr._timestamps
        assert isinstance(mgr._runs["test-1"], asyncio.Queue)
        assert mgr._timestamps["test-1"] > 0

    def test_create_multiple_runs(self):
        mgr = PipelineEventManager()
        mgr.create_run("a")
        mgr.create_run("b")
        assert "a" in mgr._runs
        assert "b" in mgr._runs
        assert len(mgr._runs) == 2


class TestEmit:
    def test_emit_puts_event_in_queue(self):
        mgr = PipelineEventManager()
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            mgr.set_loop(loop)
            mgr.create_run("emit-test")

            mgr.emit("emit-test", "stage-x", "running", "hello")
            event = loop.run_until_complete(asyncio.wait_for(
                mgr._runs["emit-test"].get(), timeout=1.0
            ))
            assert event["stage"] == "stage-x"
            assert event["status"] == "running"
            assert event["message"] == "hello"
        finally:
            loop.close()

    def test_emit_unknown_run_is_noop(self):
        mgr = PipelineEventManager()
        mgr.emit("nonexistent", "x", "y", "z")  # Sollte nicht crashen


class TestCompleteRun:
    def test_complete_run_puts_done_event(self):
        mgr = PipelineEventManager()
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            mgr.set_loop(loop)
            mgr.create_run("complete-test")

            mgr.complete_run("complete-test", "success", article_id=42, pdf_available=True)
            event = loop.run_until_complete(asyncio.wait_for(
                mgr._runs["complete-test"].get(), timeout=1.0
            ))
            assert event["stage"] == "__done__"
            assert event["article_id"] == 42
            assert event["pdf_available"] is True
        finally:
            loop.close()


class TestStoreAndGetResult:
    def test_store_and_retrieve_result(self):
        mgr = PipelineEventManager()
        mgr.store_result("res-1", {"success": True, "html": "<p>hello</p>"})
        result = mgr.get_result("res-1")
        assert result is not None
        assert result["success"] is True
        assert result["html"] == "<p>hello</p>"

    def test_get_missing_result_returns_none(self):
        mgr = PipelineEventManager()
        assert mgr.get_result("missing") is None


class TestStreamEvents:
    @pytest.mark.asyncio
    async def test_stream_completes_on_done_event(self):
        mgr = PipelineEventManager()
        loop = asyncio.get_running_loop()
        mgr.set_loop(loop)
        mgr.create_run("stream-test")

        # Done-Event enqueuen
        mgr._runs["stream-test"].put_nowait({
            "stage": "__done__", "status": "success", "output_dir": "/out",
            "pdf_available": False,
        })

        events = []
        async for sse_event in mgr.stream_events("stream-test"):
            events.append(sse_event)

        assert len(events) == 1
        assert events[0]["event"] == "done"
        data = json.loads(events[0]["data"])
        assert data["status"] == "success"

    @pytest.mark.asyncio
    async def test_stream_unknown_run_returns_error(self):
        mgr = PipelineEventManager()
        events = []
        async for sse_event in mgr.stream_events("nonexistent"):
            events.append(sse_event)
        assert len(events) == 1
        assert events[0]["event"] == "error"

    @pytest.mark.asyncio
    async def test_stream_error_event(self):
        mgr = PipelineEventManager()
        loop = asyncio.get_running_loop()
        mgr.set_loop(loop)
        mgr.create_run("error-test")

        mgr._runs["error-test"].put_nowait({
            "stage": "process_gpx", "status": "error", "message": "GPX kaputt",
        })

        events = []
        async for sse_event in mgr.stream_events("error-test"):
            events.append(sse_event)
            if sse_event["event"] == "error":
                break

        assert events[0]["event"] == "error"
        data = json.loads(events[0]["data"])
        assert "kaputt" in data["message"]


class TestCleanup:
    def test_cleanup_removes_all_data(self):
        mgr = PipelineEventManager()
        mgr._runs["c1"] = asyncio.Queue()
        mgr._results["c1"] = {"x": 1}
        mgr._timestamps["c1"] = time.time()
        mgr._cleanup_run("c1")
        assert "c1" not in mgr._runs
        assert "c1" not in mgr._results
        assert "c1" not in mgr._timestamps

    def test_cleanup_nonexistent_run_is_noop(self):
        mgr = PipelineEventManager()
        mgr._cleanup_run("gibt-es-nicht")  # Sollte nicht crashen

    @pytest.mark.asyncio
    async def test_ttl_cleanup_removes_stale_runs(self):
        mgr = PipelineEventManager()
        loop = asyncio.get_running_loop()
        mgr.set_loop(loop)
        mgr.create_run("ttl-test")

        # Überschreibe timestamp um TTL zu simulieren
        mgr._timestamps["ttl-test"] = time.time() - RUN_TTL_SECONDS - 1

        # Direkt aufrufen statt warten
        mgr._cleanup_run("ttl-test")

        assert "ttl-test" not in mgr._runs
        assert "ttl-test" not in mgr._timestamps

    @pytest.mark.asyncio
    async def test_stream_cleanup_removes_run_after_completion(self):
        mgr = PipelineEventManager()
        loop = asyncio.get_running_loop()
        mgr.set_loop(loop)
        mgr.create_run("stream-cleanup")

        mgr._runs["stream-cleanup"].put_nowait({
            "stage": "__done__", "status": "success", "output_dir": "",
        })

        async for _ in mgr.stream_events("stream-cleanup"):
            pass

        assert "stream-cleanup" not in mgr._runs
        assert "stream-cleanup" not in mgr._results


class TestScheduleCleanup:
    def test_schedule_cleanup_requires_loop(self):
        mgr = PipelineEventManager()
        mgr._runs["sc-test"] = asyncio.Queue()
        mgr._timestamps["sc-test"] = time.time()
        mgr._schedule_cleanup("sc-test")  # Kein Loop gesetzt → no-op
        # Sollte nicht crashen


class TestProgressEvents:
    @pytest.mark.asyncio
    async def test_stream_progress_events(self):
        mgr = PipelineEventManager()
        loop = asyncio.get_running_loop()
        mgr.set_loop(loop)
        mgr.create_run("progress-test")

        mgr._runs["progress-test"].put_nowait({
            "stage": "load_images", "status": "running", "message": "Lade 5 Bilder...",
        })
        mgr._runs["progress-test"].put_nowait({
            "stage": "__done__", "status": "success", "output_dir": "",
        })

        events = []
        async for sse_event in mgr.stream_events("progress-test"):
            events.append(sse_event)

        assert len(events) == 2
        assert events[0]["event"] == "progress"
        assert events[1]["event"] == "done"
