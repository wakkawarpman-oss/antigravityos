from __future__ import annotations

import json
import zipfile
from pathlib import Path

from adapters.base import ReconHit
from dossier.engine import DossierEngine
from models import AdapterOutcome, RunResult


class _FakeRunner:
    def __init__(self, proxy=None, leak_dir=None, max_workers=4):
        self.proxy = proxy
        self.leak_dir = leak_dir
        self.max_workers = max_workers

    def run(self, target_name, known_phones=None, known_usernames=None, modules=None):
        hits = [
            ReconHit(
                observable_type="email",
                value="user@example.com",
                source_module=(modules or ["fake"])[0],
                source_detail="fake-source",
                confidence=0.9,
                cross_refs=["example.com", "+380501112233"],
            ),
            ReconHit(
                observable_type="domain",
                value="example.com",
                source_module=(modules or ["fake"])[0],
                source_detail="fake-source",
                confidence=0.7,
            ),
        ]
        return RunResult(
            target_name=target_name,
            mode="aggregate",
            modules_run=list(modules or []),
            outcomes=[
                AdapterOutcome(
                    module_name=(modules or ["fake"])[0],
                    lane="fast",
                    hits=hits,
                )
            ],
            all_hits=hits,
            started_at="2026-04-10T00:00:00",
            finished_at="2026-04-10T00:00:01",
            extra={"queued_modules": list(modules or [])},
        )


def test_classify_target_matrix():
    engine = DossierEngine(runner_factory=_FakeRunner)

    assert engine.classify_target("user@example.com") == "email"
    assert engine.classify_target("+380501112233") == "phone"
    assert engine.classify_target("8.8.8.8") == "ip"
    assert engine.classify_target("example.com") == "domain"
    assert engine.classify_target("https://example.com/u/user") == "url"
    assert engine.classify_target("a" * 64) == "hash"
    assert engine.classify_target("hacker_name") == "username"


def test_run_one_shot_builds_normalized_and_links(tmp_path):
    engine = DossierEngine(runner_factory=_FakeRunner)
    run = engine.run_one_shot(
        "user@example.com",
        export_formats=["json", "text"],
        export_dir=str(tmp_path),
    )

    assert run.dossier.target.type_hint == "email"
    assert run.normalized["emails"] == ["user@example.com"]
    assert "example.com" in run.normalized["domains"]
    assert run.links
    assert set(run.exports.keys()) == {"json", "text"}

    json_payload = json.loads(Path(run.exports["json"]).read_text(encoding="utf-8"))
    assert json_payload["target"]["value"] == "user@example.com"
    assert json_payload["normalized"]["emails"] == ["user@example.com"]

    text_payload = Path(run.exports["text"]).read_text(encoding="utf-8")
    assert "ONE-SHOT DOSSIER" in text_payload


def test_run_one_shot_zip_only_includes_payload_files(tmp_path):
    engine = DossierEngine(runner_factory=_FakeRunner)
    run = engine.run_one_shot(
        "user@example.com",
        export_formats=["zip"],
        export_dir=str(tmp_path),
    )

    assert "zip" in run.exports
    assert "json" in run.exports
    assert "text" in run.exports

    with zipfile.ZipFile(run.exports["zip"], "r") as zf:
        members = set(zf.namelist())
    assert Path(run.exports["json"]).name in members
    assert Path(run.exports["text"]).name in members
