"""Shared lane scheduler for deep_recon and aggregate runners."""
from __future__ import annotations

import os
import time
from collections.abc import Callable
from concurrent.futures import FIRST_COMPLETED, Future, ProcessPoolExecutor, wait
from dataclasses import dataclass, field

from adapters.base import ReconHit
from config import CROSS_CONFIRM_BOOST, TOR_ENABLED, TOR_ROTATION_COOLDOWN_SEC, TOR_ROTATION_POLICY
from tor_control import request_tor_rotation
from worker import ReconTask, TaskResult, _run_adapter_isolated


API_COOLDOWN_SEC: dict[str, float] = {
    "shodan": 60.0,
    "censys": 30.0,
    "ua_phone": 120.0,
    "getcontact": 120.0,
}


@dataclass
class SchedulerResult:
    all_hits: list[ReconHit] = field(default_factory=list)
    modules_run: list[str] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)
    task_results: list[TaskResult] = field(default_factory=list)


class LaneScheduler:
    """Dispatch recon tasks by lane with worker isolation and timeout controls."""

    @staticmethod
    def _legacy_scheduler_enabled() -> bool:
        raw = os.environ.get("HANNA_ENABLE_LEGACY_SCHEDULER", "0").strip().lower()
        return raw in {"1", "true", "yes", "on"}

    @staticmethod
    def dispatch(
        tasks: list[ReconTask],
        max_workers: int,
        log_dir: str,
        label: str = "",
        event_callback: Callable[[dict], None] | None = None,
    ) -> SchedulerResult:
        if not LaneScheduler._legacy_scheduler_enabled():
            raise RuntimeError(
                "Legacy LaneScheduler is disabled. Set HANNA_ENABLE_LEGACY_SCHEDULER=1 to enable this path."
            )
        result = SchedulerResult()
        n_workers = min(max_workers, len(tasks)) or 1
        prefix = f"[{label}] " if label else ""
        print(f"  {prefix}Dispatching {len(tasks)} task(s) across {n_workers} worker(s)  [Fast Lane -> Slow Lane | P0->P3]")
        LaneScheduler._emit(
            event_callback,
            {
                "type": "dispatch_started",
                "label": label,
                "task_count": len(tasks),
                "workers": n_workers,
            },
        )
        if TOR_ENABLED:
            LaneScheduler._emit(
                event_callback,
                {
                    "type": "tor_rotation_policy",
                    "label": label,
                    "enabled": True,
                    "policy": TOR_ROTATION_POLICY,
                    "cooldown_sec": TOR_ROTATION_COOLDOWN_SEC,
                },
            )

        for lane_name in ("fast", "slow"):
            lane_tasks = [t for t in tasks if t.lane == lane_name]
            if not lane_tasks:
                continue

            lane_workers = min(max_workers, len(lane_tasks)) or 1
            print(f"\n  {prefix}{lane_name.upper()} LANE  |  {len(lane_tasks)} task(s) across {lane_workers} worker(s)")
            LaneScheduler._emit(
                event_callback,
                {
                    "type": "lane_started",
                    "label": label,
                    "lane": lane_name,
                    "task_count": len(lane_tasks),
                    "workers": lane_workers,
                },
            )

            pool = ProcessPoolExecutor(max_workers=lane_workers)
            future_map: dict[Future, ReconTask] = {}
            submitted_at: dict[Future, float] = {}
            last_api_call: dict[str, float] = {}

            for task in lane_tasks:
                plabel = f"P{task.priority}"
                cooldown = API_COOLDOWN_SEC.get(task.module_name, 0.0)
                if cooldown > 0:
                    now = time.monotonic()
                    last = last_api_call.get(task.module_name, 0.0)
                    wait_for = cooldown - (now - last)
                    if wait_for > 0:
                        print(f"  [{task.module_name}] API cooldown: sleeping {wait_for:.1f}s")
                        time.sleep(wait_for)
                    last_api_call[task.module_name] = time.monotonic()
                print(f"  [{task.module_name}] Queued  ({plabel}, {task.adapter_cls.region.upper()} segment)")
                LaneScheduler._emit(
                    event_callback,
                    {
                        "type": "task_queued",
                        "label": label,
                        "lane": lane_name,
                        "module": task.module_name,
                        "priority": task.priority,
                        "region": task.adapter_cls.region,
                    },
                )
                fut = pool.submit(
                    _run_adapter_isolated,
                    adapter_cls_name=task.module_name,
                    region=task.adapter_cls.region,
                    proxy=task.proxy,
                    timeout=task.timeout,
                    worker_timeout=task.worker_timeout,
                    leak_dir=task.leak_dir,
                    target_name=task.target_name,
                    known_phones=task.known_phones,
                    known_usernames=task.known_usernames,
                    log_dir=log_dir,
                )
                future_map[fut] = task
                submitted_at[fut] = time.monotonic()

            pending = set(future_map)
            try:
                while pending:
                    done, pending = wait(pending, timeout=1.0, return_when=FIRST_COMPLETED)

                    for fut in done:
                        task = future_map[fut]
                        try:
                            result_dict = fut.result(timeout=10)
                        except Exception as exc:
                            msg = f"worker_crash: {exc}"
                            result.errors.append({"module": task.module_name, "error": msg, "error_kind": "worker_crash"})
                            result.task_results.append(TaskResult(
                                module_name=task.module_name,
                                lane=task.lane,
                                hits=[],
                                error=msg,
                                error_kind="worker_crash",
                                elapsed_sec=0.0,
                                raw_log_path="",
                            ))
                            print(f"  [{task.module_name}] CRASHED: {exc}")
                            LaneScheduler._emit(
                                event_callback,
                                {
                                    "type": "task_crashed",
                                    "label": label,
                                    "lane": task.lane,
                                    "module": task.module_name,
                                    "error": msg,
                                },
                            )
                            if TOR_ENABLED:
                                LaneScheduler._emit(
                                    event_callback,
                                    {
                                        "type": "tor_rotation_requested",
                                        "label": label,
                                        "module": task.module_name,
                                        "reason": "task_crashed",
                                        "policy": TOR_ROTATION_POLICY,
                                        "cooldown_sec": TOR_ROTATION_COOLDOWN_SEC,
                                    },
                                )
                                LaneScheduler._emit(
                                    event_callback,
                                    {
                                        "type": "tor_rotation_result",
                                        "label": label,
                                        **request_tor_rotation("task_crashed", task.module_name),
                                    },
                                )
                            continue

                        tr = TaskResult.from_dict(result_dict, lane=task.lane)
                        result.task_results.append(tr)
                        result.modules_run.append(tr.module_name)
                        if tr.error:
                            result.errors.append({"module": tr.module_name, "error": tr.error, "error_kind": tr.error_kind})
                            print(f"  [{tr.module_name}] ERROR: {tr.error}  ({tr.elapsed_sec:.1f}s)")
                            LaneScheduler._emit(
                                event_callback,
                                {
                                    "type": "task_error",
                                    "label": label,
                                    "lane": tr.lane,
                                    "module": tr.module_name,
                                    "error": tr.error,
                                    "elapsed_sec": tr.elapsed_sec,
                                    "hit_count": 0,
                                },
                            )
                            if TOR_ENABLED:
                                LaneScheduler._emit(
                                    event_callback,
                                    {
                                        "type": "tor_rotation_requested",
                                        "label": label,
                                        "module": tr.module_name,
                                        "reason": "task_error",
                                        "policy": TOR_ROTATION_POLICY,
                                        "cooldown_sec": TOR_ROTATION_COOLDOWN_SEC,
                                    },
                                )
                                LaneScheduler._emit(
                                    event_callback,
                                    {
                                        "type": "tor_rotation_result",
                                        "label": label,
                                        **request_tor_rotation("task_error", tr.module_name),
                                    },
                                )
                        else:
                            result.all_hits.extend(tr.hits)
                            print(f"  [{tr.module_name}] -> {len(tr.hits)} hit(s)  ({tr.elapsed_sec:.1f}s)")
                            LaneScheduler._emit(
                                event_callback,
                                {
                                    "type": "task_done",
                                    "label": label,
                                    "lane": tr.lane,
                                    "module": tr.module_name,
                                    "elapsed_sec": tr.elapsed_sec,
                                    "hit_count": len(tr.hits),
                                },
                            )

                    now = time.monotonic()
                    timed_out = [
                        f for f in pending
                        if now - submitted_at[f] >= future_map[f].worker_timeout
                    ]
                    for fut in timed_out:
                        pending.discard(fut)
                        task = future_map[fut]
                        fut.cancel()
                        msg = f"TIMEOUT ({int(task.worker_timeout)}s)"
                        result.errors.append({"module": task.module_name, "error": msg, "error_kind": "timeout"})
                        result.task_results.append(TaskResult(
                            module_name=task.module_name,
                            lane=task.lane,
                            hits=[],
                            error=msg,
                            error_kind="timeout",
                            elapsed_sec=float(task.worker_timeout),
                            raw_log_path="",
                        ))
                        print(f"  [{task.module_name}] {msg} - cancelled")
                        LaneScheduler._emit(
                            event_callback,
                            {
                                "type": "task_timeout",
                                "label": label,
                                "lane": task.lane,
                                "module": task.module_name,
                                "error": msg,
                                "elapsed_sec": float(task.worker_timeout),
                            },
                        )
                        if TOR_ENABLED:
                            LaneScheduler._emit(
                                event_callback,
                                {
                                    "type": "tor_rotation_requested",
                                    "label": label,
                                    "module": task.module_name,
                                    "reason": "task_timeout",
                                    "policy": TOR_ROTATION_POLICY,
                                    "cooldown_sec": TOR_ROTATION_COOLDOWN_SEC,
                                },
                            )
                            LaneScheduler._emit(
                                event_callback,
                                {
                                    "type": "tor_rotation_result",
                                    "label": label,
                                    **request_tor_rotation("task_timeout", task.module_name),
                                },
                            )
            finally:
                pending_cancelled = 0
                pending_killed = 0
                cancelled_modules: list[str] = []
                killed_modules: list[str] = []
                if pending:
                    pending_before_shutdown = len(pending)
                    for fut in list(pending):
                        task = future_map.get(fut)
                        if task is None:
                            pending.discard(fut)
                            continue
                        if fut.cancel():
                            pending_cancelled += 1
                            pending.discard(fut)
                            cancelled_modules.append(task.module_name)
                            msg = "CANCELLED_ON_SHUTDOWN"
                            result.errors.append(
                                {
                                    "module": task.module_name,
                                    "error": msg,
                                    "error_kind": "cancelled_on_shutdown",
                                }
                            )
                            result.task_results.append(
                                TaskResult(
                                    module_name=task.module_name,
                                    lane=task.lane,
                                    hits=[],
                                    error=msg,
                                    error_kind="cancelled_on_shutdown",
                                    elapsed_sec=0.0,
                                    raw_log_path="",
                                )
                            )
                            LaneScheduler._emit(
                                event_callback,
                                {
                                    "type": "task_cancelled_on_shutdown",
                                    "label": label,
                                    "lane": task.lane,
                                    "module": task.module_name,
                                    "error": msg,
                                },
                            )
                        else:
                            pending_killed += 1
                            pending.discard(fut)
                            killed_modules.append(task.module_name)
                            msg = "KILLED_FOR_SHUTDOWN"
                            result.errors.append(
                                {
                                    "module": task.module_name,
                                    "error": msg,
                                    "error_kind": "killed_for_shutdown",
                                }
                            )
                            result.task_results.append(
                                TaskResult(
                                    module_name=task.module_name,
                                    lane=task.lane,
                                    hits=[],
                                    error=msg,
                                    error_kind="killed_for_shutdown",
                                    elapsed_sec=0.0,
                                    raw_log_path="",
                                )
                            )
                            LaneScheduler._emit(
                                event_callback,
                                {
                                    "type": "task_killed_for_shutdown",
                                    "label": label,
                                    "lane": task.lane,
                                    "module": task.module_name,
                                    "error": msg,
                                },
                            )
                    LaneScheduler._emit(
                        event_callback,
                        {
                            "type": "scheduler_pending_cancelled",
                            "label": label,
                            "lane": lane_name,
                            "pending_before_shutdown": pending_before_shutdown,
                            "pending_cancelled": pending_cancelled,
                            "pending_killed": pending_killed,
                            "modules_cancelled": cancelled_modules,
                            "modules_killed": killed_modules,
                        },
                    )
                LaneScheduler._shutdown_pool(pool, event_callback, label=label, lane=lane_name)

            lane_ok = sum(1 for tr in result.task_results if tr.lane == lane_name and not tr.error)
            print(f"  {prefix}{lane_name.upper()} LANE complete  |  {lane_ok}/{len(lane_tasks)} task(s) finished cleanly")
            LaneScheduler._emit(
                event_callback,
                {
                    "type": "lane_complete",
                    "label": label,
                    "lane": lane_name,
                    "ok_count": lane_ok,
                    "task_count": len(lane_tasks),
                },
            )

        LaneScheduler._emit(
            event_callback,
            {
                "type": "dispatch_complete",
                "label": label,
                "modules_run": list(result.modules_run),
                "errors": len(result.errors),
                "hits": len(result.all_hits),
            },
        )
        if TOR_ENABLED:
            LaneScheduler._emit(
                event_callback,
                {
                    "type": "tor_rotation_checkpoint",
                    "label": label,
                    "reason": "dispatch_complete",
                    "policy": TOR_ROTATION_POLICY,
                    "cooldown_sec": TOR_ROTATION_COOLDOWN_SEC,
                },
            )
        return result

    @staticmethod
    def _emit(event_callback: Callable[[dict], None] | None, payload: dict) -> None:
        if event_callback:
            event_callback(payload)

    @staticmethod
    def _shutdown_pool(
        pool: ProcessPoolExecutor,
        event_callback: Callable[[dict], None] | None,
        *,
        label: str,
        lane: str,
    ) -> None:
        """Best-effort pool shutdown without touching private executor internals."""
        try:
            pool.shutdown(wait=False, cancel_futures=True)
            LaneScheduler._emit(
                event_callback,
                {
                    "type": "scheduler_pool_shutdown",
                    "label": label,
                    "lane": lane,
                    "mode": "non_blocking_cancel_futures",
                },
            )
        except TypeError:
            pool.shutdown(wait=False)
            LaneScheduler._emit(
                event_callback,
                {
                    "type": "scheduler_pool_shutdown",
                    "label": label,
                    "lane": lane,
                    "mode": "non_blocking_legacy",
                },
            )


def dedup_and_confirm(all_hits: list[ReconHit]) -> tuple[list[ReconHit], list[ReconHit]]:
    """Deduplicate hits by fingerprint and tag cross-confirmed ones."""
    seen: dict[str, ReconHit] = {}
    for hit in all_hits:
        fp = hit.fingerprint
        if fp in seen:
            existing = seen[fp]
            if hit.confidence > existing.confidence:
                existing.confidence = hit.confidence
                existing.source_detail = hit.source_detail
            existing.cross_refs = list(set(existing.cross_refs + hit.cross_refs))
        else:
            seen[fp] = hit

    deduped = list(seen.values())

    source_counts: dict[str, set[str]] = {}
    for hit in all_hits:
        source_counts.setdefault(hit.fingerprint, set()).add(hit.source_module)

    cross_confirmed = [
        h for h in deduped
        if len(source_counts.get(h.fingerprint, set())) >= 2
    ]
    for hit in cross_confirmed:
        hit.confidence = min(1.0, hit.confidence + CROSS_CONFIRM_BOOST)

    return deduped, cross_confirmed
