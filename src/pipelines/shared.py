"""Shared helpers for orchestration pipelines."""
from __future__ import annotations
from typing import Optional, List

from models import RunResult
from runners.aggregate import AggregateRunner


def run_preset(
    preset: str,
    target: str,
    phones: Optional[List[str]] = None,
    usernames: Optional[List[str]] = None,
    proxy: Optional[str] = None,
    leak_dir: Optional[str] = None,
    workers: int = 4,
) -> RunResult:
    runner = AggregateRunner(proxy=proxy, leak_dir=leak_dir, max_workers=workers)
    return runner.run(
        target_name=target,
        known_phones=phones or [],
        known_usernames=usernames or [],
        modules=[preset],
    )
