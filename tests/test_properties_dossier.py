from __future__ import annotations

import pytest

hypothesis = pytest.importorskip("hypothesis")
from hypothesis import given
from hypothesis import strategies as st

from adapters.base import ReconHit
from dossier.core import DossierEngine
from models import AdapterOutcome, RunResult


class _DeterministicRunner:
    def __init__(self, proxy=None, leak_dir=None, max_workers=4):
        self.proxy = proxy
        self.leak_dir = leak_dir
        self.max_workers = max_workers

    def run(self, target_name, known_phones=None, known_usernames=None, modules=None):
        modules = list(modules or ["mock"])
        hits = [
            ReconHit(
                observable_type="email",
                value="user@example.com",
                source_module=modules[0],
                source_detail="property",
                confidence=0.8,
            )
        ]
        return RunResult(
            target_name=target_name,
            mode="aggregate",
            modules_run=modules,
            outcomes=[AdapterOutcome(module_name=modules[0], lane="fast", hits=hits)],
            all_hits=hits,
            started_at="2026-04-10T00:00:00",
            finished_at="2026-04-10T00:00:01",
            extra={"queued_modules": modules},
        )


def _mk_engine():
    return DossierEngine(runner_factory=_DeterministicRunner)


@given(st.text())
def test_property_classify_target_never_crashes(value: str):
    engine = _mk_engine()
    result = engine.classify_target(value)
    assert result in {"email", "phone", "url", "ip", "hash", "domain", "username", "unknown"}


@given(st.lists(st.text(min_size=0, max_size=64), min_size=1, max_size=20))
def test_property_normalize_always_deduplicates(values: list[str]):
    engine = _mk_engine()
    run = engine.run_one_shot_full("property_target", export_formats=[])

    evidences = []
    for idx, value in enumerate(values):
        base = run.dossier.evidences[idx % len(run.dossier.evidences)]
        evidences.append(type(base)(
            source=base.source,
            field=base.field,
            value=value,
            layer=base.layer,
            confidence=base.confidence,
            score=base.score,
            details=base.details,
        ))
        evidences.append(type(base)(
            source=base.source,
            field=base.field,
            value=value,
            layer=base.layer,
            confidence=base.confidence,
            score=base.score,
            details=base.details,
        ))

    normalized = engine.normalize_evidences(evidences)
    for key, bucket in normalized.items():
        assert len(bucket) == len(set(bucket)), key
