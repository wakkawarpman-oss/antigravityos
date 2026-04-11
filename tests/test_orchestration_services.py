from __future__ import annotations

from pathlib import Path

from services.orchestration import ingest_metadata_exports, run_verification_stage


class _EngineStub:
    def __init__(self, status_by_file: dict[str, str]):
        self.status_by_file = status_by_file
        self.verify_profiles_calls = []
        self.verify_content_calls = []

    def ingest_metadata(self, path: Path):
        return {"status": self.status_by_file.get(path.name, "skipped")}

    def verify_profiles(self, **kwargs):
        self.verify_profiles_calls.append(kwargs)

    def verify_content(self, **kwargs):
        self.verify_content_calls.append(kwargs)


def test_ingest_metadata_exports_counts_statuses(tmp_path):
    (tmp_path / "a.json").write_text("{}", encoding="utf-8")
    (tmp_path / "b.json").write_text("{}", encoding="utf-8")
    (tmp_path / "c.json").write_text("{}", encoding="utf-8")

    engine = _EngineStub({"a.json": "ingested", "b.json": "rejected", "c.json": "unknown"})
    counts = ingest_metadata_exports(engine, tmp_path)

    assert counts == {"ingested": 1, "rejected": 1, "skipped": 1}


def test_run_verification_stage_uses_expected_limits():
    engine = _EngineStub({})

    run_verification_stage(engine, verify=True, verify_all=False, verify_content=True, proxy="socks5h://127.0.0.1:9050")

    assert engine.verify_profiles_calls == [{"max_checks": 200, "timeout": 4.0, "proxy": "socks5h://127.0.0.1:9050"}]
    assert engine.verify_content_calls == [{"max_checks": 200, "timeout": 8.0, "proxy": "socks5h://127.0.0.1:9050"}]
