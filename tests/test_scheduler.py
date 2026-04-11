from __future__ import annotations

import asyncio
import time

from adapters.base import ReconHit
from adapters.base import ReconAdapter
from schedulers.dispatcher import MultiLaneDispatcher
from schedulers.lanes import LaneScheduler
from schedulers.lanes import dedup_and_confirm
from worker import ReconTask


def test_scheduler_emit_noop_without_callback():
    LaneScheduler._emit(None, {"type": "dispatch_started"})


def test_scheduler_emit_calls_callback():
    events = []

    LaneScheduler._emit(events.append, {"type": "dispatch_started", "task_count": 2})

    assert events == [{"type": "dispatch_started", "task_count": 2}]


def test_dedup_and_confirm_boosts_cross_confirmed_hits():
    h1 = ReconHit(
        observable_type="email",
        value="x@example.com",
        source_module="a",
        source_detail="a",
        confidence=0.4,
    )
    h2 = ReconHit(
        observable_type="email",
        value="x@example.com",
        source_module="b",
        source_detail="b",
        confidence=0.6,
    )

    deduped, cross = dedup_and_confirm([h1, h2])

    assert len(deduped) == 1
    assert len(cross) == 1
    assert cross[0].confidence > 0.6


def test_scheduler_emits_tor_rotation_events_for_empty_dispatch(monkeypatch):
    import schedulers.lanes as lanes_mod

    monkeypatch.setattr(lanes_mod, "TOR_ENABLED", True)
    monkeypatch.setattr(lanes_mod, "TOR_ROTATION_POLICY", "batch_on_error")
    monkeypatch.setattr(lanes_mod, "TOR_ROTATION_COOLDOWN_SEC", 10)

    events = []
    lanes_mod.LaneScheduler.dispatch(
        tasks=[],
        max_workers=1,
        log_dir=".",
        label="test",
        event_callback=events.append,
    )

    event_types = [event.get("type") for event in events]
    assert "tor_rotation_policy" in event_types
    assert "tor_rotation_checkpoint" in event_types


class _HangingAdapter(ReconAdapter):
    name = "hanging"
    region = "global"

    def search(self, target_name, known_phones, known_usernames):
        return []

    async def search_async(self, target_name, known_phones, known_usernames):
        await asyncio.sleep(0.2)
        if False:
            yield  # pragma: no cover


def test_async_dispatcher_enforces_worker_timeout_for_hanging_task():
    task = ReconTask(
        module_name="hanging",
        priority=1,
        adapter_cls=_HangingAdapter,
        target_name="example.com",
        known_phones=[],
        known_usernames=[],
        lane="fast",
        proxy="socks5h://127.0.0.1:9050",
        timeout=1.0,
        worker_timeout=0.05,
        leak_dir=None,
    )

    dispatcher = MultiLaneDispatcher(max_parallel_tasks=1)

    started = time.monotonic()
    hits = asyncio.run(dispatcher.run_tasks([task], label="timeout-test"))
    elapsed = time.monotonic() - started

    assert hits == []
    assert any(err.get("module") == "hanging" and err.get("error_kind") == "timeout" for err in dispatcher.errors)
    assert elapsed < 0.2
