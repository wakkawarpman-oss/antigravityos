from __future__ import annotations

import random
import string
import time

from pydantic import BaseModel, field_validator

from adapters.base import ReconHit
from dossier.core import DossierEngine
from models import AdapterOutcome, RunResult


class _DeterministicRunner:
    def __init__(self, proxy=None, leak_dir=None, max_workers=4):
        self.proxy = proxy
        self.leak_dir = leak_dir
        self.max_workers = max_workers

    def run(self, target_name, known_phones=None, known_usernames=None, modules=None):
        modules = list(modules or [])
        outcomes = []
        hits = []
        for module in modules:
            if module.endswith("fail"):
                outcomes.append(
                    AdapterOutcome(
                        module_name=module,
                        lane="fast",
                        error="simulated failure",
                        error_kind="worker_crash",
                    )
                )
                continue

            observable_type = "username"
            value = f"{target_name}_{module}"
            if "email" in module or "holehe" in module:
                observable_type = "email"
                value = f"{target_name.split('@')[0]}@example.com"
            elif "naabu" in module or "nmap" in module:
                observable_type = "ip"
                value = "8.8.8.8"
            elif "subfinder" in module or "amass" in module:
                observable_type = "domain"
                value = "example.com"

            hit = ReconHit(
                observable_type=observable_type,
                value=value,
                source_module=module,
                source_detail="deterministic",
                confidence=0.8,
                cross_refs=["example.com", "+380501112233"],
            )
            hits.append(hit)
            outcomes.append(
                AdapterOutcome(
                    module_name=module,
                    lane="fast",
                    hits=[hit],
                )
            )

        return RunResult(
            target_name=target_name,
            mode="aggregate",
            modules_run=modules,
            outcomes=outcomes,
            all_hits=hits,
            started_at="2026-04-10T00:00:00",
            finished_at="2026-04-10T00:00:01",
            extra={"queued_modules": modules},
        )


class EvidenceContract(BaseModel):
    source: str
    field: str
    confidence: float
    score: float

    @field_validator("confidence")
    @classmethod
    def _confidence_range(cls, value: float) -> float:
        if not (0.0 <= value <= 1.0):
            raise ValueError("confidence out of bounds")
        return value


def test_unit_classify_target_edge_cases():
    engine = DossierEngine(runner_factory=_DeterministicRunner)

    assert engine.classify_target("") == "unknown"
    assert engine.classify_target("   ") == "unknown"
    assert engine.classify_target("тест") == "unknown"
    assert engine.classify_target("not-an-email@")== "unknown"
    assert engine.classify_target("255.255.255.255") == "ip"
    assert engine.classify_target("https://example.com") == "url"
    assert engine.classify_target("example.com") == "domain"
    assert engine.classify_target("abcdef" * 11) == "unknown"


def test_unit_normalize_evidences_deduplicates_and_handles_none():
    engine = DossierEngine(runner_factory=_DeterministicRunner)
    run = engine.run_one_shot_full("user@example.com", export_formats=[])

    duplicated = list(run.dossier.evidences) + list(run.dossier.evidences)
    duplicated.append(type(run.dossier.evidences[0])(
        source="hanna::mock",
        field="email",
        value=None,
        layer="pivot",
        confidence=0.3,
        score=0.2,
    ))

    normalized = engine.normalize_evidences(duplicated)
    assert len(normalized["emails"]) == len(set(normalized["emails"]))
    assert all(item is not None for values in normalized.values() for item in values)


def test_integration_pipeline_flow_email_phone_username():
    engine = DossierEngine(runner_factory=_DeterministicRunner)
    for target in ["user@example.com", "+380501112233", "hacker_name"]:
        run = engine.run_one_shot_full(target, export_formats=[])
        assert run.dossier.target.value == target
        assert run.dossier.layers == ["surface", "deep", "pivot"]
        assert isinstance(run.normalized, dict)
        assert run.stats["total_evidences"] == len(run.dossier.evidences)


def test_contract_validation_for_all_evidences():
    engine = DossierEngine(runner_factory=_DeterministicRunner)
    run = engine.run_one_shot_full("user@example.com", export_formats=[])

    for evidence in run.dossier.evidences:
        EvidenceContract(
            source=evidence.source,
            field=evidence.field,
            confidence=float(evidence.confidence),
            score=float(evidence.score),
        )


def test_data_flow_no_loss_and_confidence_valid():
    engine = DossierEngine(runner_factory=_DeterministicRunner)
    run = engine.run_one_shot_full("user@example.com", export_formats=[])

    total = len(run.dossier.evidences)
    assert total == run.stats["total_evidences"]
    assert all(ev.confidence is not None and ev.confidence >= 0 for ev in run.dossier.evidences)


def test_chaos_simulated_module_failures_collected_as_evidence():
    class _FailRunner(_DeterministicRunner):
        def run(self, target_name, known_phones=None, known_usernames=None, modules=None):
            modules = list(modules or [])
            outcomes = [
                AdapterOutcome(
                    module_name=module,
                    lane="fast",
                    error="simulated failure",
                    error_kind="worker_crash",
                )
                for module in modules
            ]
            return RunResult(
                target_name=target_name,
                mode="aggregate",
                modules_run=modules,
                outcomes=outcomes,
                all_hits=[],
                started_at="2026-04-10T00:00:00",
                finished_at="2026-04-10T00:00:01",
                extra={"queued_modules": modules},
            )

    engine = DossierEngine(runner_factory=_FailRunner)
    run = engine.run_one_shot_full(
        "user@example.com",
        surface_modules=["email-chain"],
        deep_modules=["person-deep"],
        pivot_modules=["recon-auto-quick"],
        export_formats=[],
    )

    assert any(ev.field == "error" for ev in run.dossier.evidences)


def test_performance_long_target_under_budget():
    engine = DossierEngine(runner_factory=_DeterministicRunner)
    target = "long_string_" * 1000

    started = time.perf_counter()
    run = engine.run_one_shot_full(target, export_formats=[])
    elapsed = time.perf_counter() - started

    assert run.dossier.target.value == target
    assert elapsed < 30.0


def test_fuzz_classify_and_normalize_no_crash():
    engine = DossierEngine(runner_factory=_DeterministicRunner)

    charset = string.printable + "абвгдеєжзиіїйклмнопрстуфхцчшщьюя"
    for _ in range(1000):
        sample = "".join(random.choice(charset) for _ in range(random.randint(0, 128)))
        _ = engine.classify_target(sample)

        run = engine.run_one_shot_full(sample or "fuzz", export_formats=[])
        normalized = engine.normalize_evidences(run.dossier.evidences)
        assert isinstance(normalized, dict)
