"""
schedulers.dispatcher — Async Multi-Lane Dispatcher (Base v4)
============================================================

Replaces LaneScheduler with an asyncio-native prioritized queue 
and semaphore-controlled concurrency.

Features:
  - Real-time streaming: yielded hits are processed IMMEDIATELY.
  - Priority-aware: P0 tasks jump to the front of the queue.
  - Hybrid support: runs native search_async and legacy search (via to_thread).
  - Multi-lane: unified queue with different concurrency pools.
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, AsyncIterator, Callable, Dict, List, Optional, Set, Tuple

from adapters.base import ReconAdapter, ReconHit
from config import CROSS_CONFIRM_BOOST
from worker import ReconTask, TaskResult

log = logging.getLogger("hanna.dispatcher")


@dataclass(order=True)
class _PrioritizedTask:
    priority: int
    task: ReconTask = field(compare=False)


class MultiLaneDispatcher:
    """
    Async-native dispatcher for recon tasks.
    Supports real-time outcome reporting and managed concurrency.
    """

    def __init__(
        self,
        max_parallel_tasks: int = 10,
        event_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ):
        self.max_parallel_tasks = max_parallel_tasks
        self.event_callback = event_callback
        self.queue = asyncio.PriorityQueue()
        self.semaphores = {
            "fast": asyncio.Semaphore(max_parallel_tasks),
            "slow": asyncio.Semaphore(max(1, max_parallel_tasks // 2)),
        }
        self.all_hits: List[ReconHit] = []
        self.errors: List[Dict[str, Any]] = []
        self.modules_run: Set[str] = set()

    def _emit(self, payload: Dict[str, Any]) -> None:
        if self.event_callback:
            self.event_callback(payload)

    async def run_tasks(self, tasks: List[ReconTask], label: str = "") -> List[ReconHit]:
        """Entry point to dispatch and run a list of tasks."""
        self._emit({
            "type": "dispatch_started",
            "label": label,
            "task_count": len(tasks),
            "workers": self.max_parallel_tasks,
        })

        # Fill the queue
        for task in tasks:
            # lower priority value = higher priority in queue
            await self.queue.put(_PrioritizedTask(task.priority, task))
            self._emit({
                "type": "task_queued",
                "label": label,
                "lane": task.lane,
                "module": task.module_name,
                "priority": task.priority,
                "region": task.adapter_cls.region,
            })

        # Start workers
        workers = [
            asyncio.create_task(self._worker(label))
            for _ in range(self.max_parallel_tasks)
        ]

        # Wait for queue to empty
        await self.queue.join()

        # Stop workers
        for w in workers:
            w.cancel()

        self._emit({
            "type": "dispatch_complete",
            "label": label,
            "modules_run": list(self.modules_run),
            "errors": len(self.errors),
            "hits": len(self.all_hits),
        })

        return self.all_hits

    async def _worker(self, label: str) -> None:
        """Continuously pulls tasks from the queue and executes them."""
        while True:
            p_task = await self.queue.get()
            task = p_task.task
            lane = task.lane or "slow"
            
            async with self.semaphores.get(lane, self.semaphores["slow"]):
                await self._execute_task(task, label)
            
            self.queue.task_done()

    async def _execute_task(self, task: ReconTask, label: str) -> None:
        """Excutes a single ReconTask, supporting both async and sync adapters."""
        t0 = time.monotonic()
        mod_name = task.module_name
        self.modules_run.add(mod_name)

        self._emit({
            "type": "task_started",
            "label": label,
            "lane": task.lane,
            "module": mod_name,
        })

        adapter = None
        try:
            adapter = task.adapter_cls(
                proxy=task.proxy,
                timeout=task.timeout,
                leak_dir=task.leak_dir
            )
            
            hit_count = 0
            # 1. Prefer native search_async
            # 2. Fall back to search_async default (which wraps sync search in thread)
            async for hit in adapter.search_async(
                task.target_name,
                task.known_phones,
                task.known_usernames
            ):
                hit_count += 1
                self.all_hits.append(hit)
                
                # EMIT HIT IMMEDIATELY TO UI
                self._emit({
                    "type": "hit_found",
                    "label": label,
                    "module": mod_name,
                    "hit": hit.to_dict(),
                    "total_hits": hit_count
                })

            elapsed = time.monotonic() - t0
            self._emit({
                "type": "task_done",
                "label": label,
                "lane": task.lane,
                "module": mod_name,
                "elapsed_sec": round(elapsed, 2),
                "hit_count": hit_count,
            })

        except Exception as exc:
            elapsed = time.monotonic() - t0
            err_msg = str(exc)
            self.errors.append({"module": mod_name, "error": err_msg})
            self._emit({
                "type": "task_error",
                "label": label,
                "lane": task.lane,
                "module": mod_name,
                "error": err_msg,
                "elapsed_sec": round(elapsed, 2),
            })
            log.error("[%s] Task failed: %s", mod_name, err_msg)
