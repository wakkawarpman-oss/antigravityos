from __future__ import annotations

import json
from pathlib import Path

from adapters.base import ReconHit
from dossier.core import DossierEngine as CompatEngine
from dossier.engine import DossierEngine, Evidence, Target
from models import AdapterOutcome, RunResult


class _Runner:
    def __init__(self, proxy=None, leak_dir=None, max_workers=4):
        self.proxy = proxy
        self.leak_dir = leak_dir
        self.max_workers = max_workers

    def run(self, target_name, known_phones=None, known_usernames=None, modules=None):
        modules = list(modules or ["mock"])
        outcomes = []
        all_hits = []
        for idx, module in enumerate(modules):
            hit = ReconHit(
                observable_type="email" if idx % 2 == 0 else "domain",
                value="user@example.com" if idx % 2 == 0 else "example.com",
                source_module=module,
                source_detail="coverage",
                confidence=0.7,
                cross_refs=["example.com", "https://example.com/profile/user"],
            )
            all_hits.append(hit)
            outcomes.append(AdapterOutcome(module_name=module, lane="fast", hits=[hit]))

        return RunResult(
            target_name=target_name,
            mode="aggregate",
            modules_run=modules,
            outcomes=outcomes,
            all_hits=all_hits,
            started_at="2026-04-10T00:00:00",
            finished_at="2026-04-10T00:00:01",
            extra={"queued_modules": modules},
        )


def test_classify_handles_none_and_non_string_inputs():
    engine = DossierEngine(runner_factory=_Runner)

    assert engine.classify_target(None) == "unknown"
    assert engine.classify_target(1234567890) in {"phone", "unknown"}


def test_split_to_layers_override_paths():
    engine = DossierEngine(runner_factory=_Runner)
    target = Target(value="case", type_hint="email")
    layers = engine._split_to_layers(
        target,
        surface_modules=["email-chain"],
        deep_modules=["person-deep"],
        pivot_modules=["recon-auto-quick"],
    )

    assert set(layers.keys()) == {"surface", "deep", "pivot"}
    assert layers["surface"]
    assert layers["deep"]
    assert layers["pivot"]


def test_build_links_deduplicates_cross_refs():
    engine = DossierEngine(runner_factory=_Runner)
    ev = Evidence(
        source="hanna::mock",
        field="email",
        value="user@example.com",
        layer="surface",
        confidence=0.8,
        score=0.8,
        details={"cross_refs": ["example.com", "example.com", "8.8.8.8"]},
    )

    links = engine._build_links([ev, ev])
    unique_pairs = {(x["from"], x["to"], x["layer"], x["source"]) for x in links}
    assert len(links) == len(unique_pairs)


def test_render_and_export_formats(tmp_path):
    engine = DossierEngine(runner_factory=_Runner)
    run = engine.run_one_shot("user@example.com", export_formats=["json", "text", "html", "stix", "zip"], export_dir=str(tmp_path))

    assert set(run.exports.keys()) == {"json", "text", "html", "stix", "zip"}
    assert "<!doctype html>" in Path(run.exports["html"]).read_text(encoding="utf-8").lower()

    stix_payload = json.loads(Path(run.exports["stix"]).read_text(encoding="utf-8"))
    assert stix_payload["type"] == "bundle"
    assert any(obj.get("type") == "indicator" for obj in stix_payload["objects"])


def test_core_compat_export_unsupported_format(tmp_path):
    engine = CompatEngine(runner_factory=_Runner)
    dossier, normalized = engine.run_one_shot("user@example.com")

    try:
        engine.export_dossier(dossier, normalized, "html", tmp_path / "x")
        assert False
    except NotImplementedError:
        assert True


def test_run_one_shot_interactive_export(monkeypatch, tmp_path):
    engine = DossierEngine(runner_factory=_Runner)
    monkeypatch.setattr("builtins.input", lambda _prompt: "json")

    run = engine.run_one_shot("user@example.com", interactive_export=True, export_dir=str(tmp_path))
    assert "json" in run.exports
