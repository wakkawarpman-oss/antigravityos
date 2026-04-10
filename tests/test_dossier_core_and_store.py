from __future__ import annotations

import json
from pathlib import Path

from adapters.base import ReconHit
from analytics.dossier_store import DossierSessionStore
from dossier.core import DossierEngine
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
                confidence=0.95,
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


def test_dossier_core_run_and_export(tmp_path):
    engine = DossierEngine(runner_factory=_FakeRunner)
    dossier, normalized = engine.run_one_shot("user@example.com")

    assert dossier.target.value == "user@example.com"
    assert "emails" in normalized

    text_path = engine.export_dossier(dossier, normalized, "text", tmp_path / "report")
    json_path = engine.export_dossier(dossier, normalized, "json", tmp_path / "report")

    assert text_path.exists()
    assert json_path.exists()
    assert "Dossier for user@example.com" in text_path.read_text(encoding="utf-8")

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["target"]["value"] == "user@example.com"
    assert "normalized" in payload


def test_dossier_session_store_roundtrip(tmp_path):
    db_path = tmp_path / "sessions.sqlite"
    json_dir = tmp_path / "sessions"

    store = DossierSessionStore(db_path=str(db_path), json_dir=str(json_dir))
    engine = DossierEngine(runner_factory=_FakeRunner)
    dossier, normalized = engine.run_one_shot("user@example.com")

    session_id = store.create_session(dossier, normalized, source_type="test", tags=["one-shot"])
    assert session_id > 0

    sessions = store.query_sessions(limit=10)
    assert sessions
    assert sessions[0]["target"] == "user@example.com"

    full = store.get_full_session(session_id)
    assert full is not None
    assert full["session"]["id"] == session_id
    assert isinstance(full["evidences"], list)
