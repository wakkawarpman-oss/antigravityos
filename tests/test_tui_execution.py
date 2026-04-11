from __future__ import annotations

from pathlib import Path

from adapters.base import ReconHit, ReconReport
from worker import TaskResult
from tui.execution import TUIExecutionConfig, run_mode


def test_run_mode_manual_emits_expected_events(monkeypatch):
    import tui.execution as execution_mod

    class StubAdapter:
        region = "global"

        def __init__(self, proxy=None, timeout=0.0, leak_dir=None):
            self.proxy = proxy
            self.timeout = timeout
            self.leak_dir = leak_dir

        def search(self, target_name, known_phones, known_usernames):
            return [
                ReconHit(
                    observable_type="email",
                    value="stub@example.com",
                    source_module="stub_manual",
                    source_detail="fixture",
                    confidence=0.8,
                )
            ]

    monkeypatch.setattr(execution_mod, "run_preflight", lambda modules=None: [])
    monkeypatch.setitem(execution_mod.MODULES, "stub_manual", StubAdapter)
    monkeypatch.setattr(execution_mod, "_export_artifacts", lambda result, config: {})

    events: list[dict] = []
    result = run_mode(
        TUIExecutionConfig(target="Case", manual_module="stub_manual", modules=["stub_manual"]),
        "manual",
        events.append,
    )

    event_types = [event["type"] for event in events]
    assert result.mode == "manual"
    assert "run_started" in event_types
    assert "modules_resolved" in event_types
    assert "readiness" in event_types
    assert "phase" in event_types
    assert sum(1 for event in events if event["type"] == "module") >= 2
    assert event_types[-1] == "run_finished"


def test_run_mode_aggregate_emits_scheduler_driven_module_events(monkeypatch):
    import tui.execution as execution_mod

    hit = ReconHit(
        observable_type="phone",
        value="+380500000000",
        source_module="stub_aggregate",
        source_detail="fixture",
        confidence=0.7,
    )

    monkeypatch.setattr(execution_mod, "run_preflight", lambda modules=None: [])
    monkeypatch.setattr(execution_mod, "resolve_modules", lambda modules=None: list(modules or []))
    monkeypatch.setattr(execution_mod, "build_tasks", lambda *args, **kwargs: ([], []))

    async def _run_tasks(self, tasks, label=""):
        self._emit({"type": "task_queued", "lane": "fast", "module": "stub_aggregate", "priority": 1})
        self._emit({"type": "task_done", "lane": "fast", "module": "stub_aggregate", "hit_count": 1, "elapsed_sec": 0.1})
        self._emit({"type": "lane_complete", "lane": "fast", "ok_count": 1, "task_count": 1})
        self.modules_run = ["stub_aggregate"]
        self.errors = []
        self.task_results = [
            TaskResult(
                module_name="stub_aggregate",
                lane="fast",
                hits=[hit],
                error=None,
                error_kind=None,
                elapsed_sec=0.1,
                raw_log_path="",
            )
        ]
        return [hit]

    monkeypatch.setattr(execution_mod.MultiLaneDispatcher, "run_tasks", _run_tasks)
    monkeypatch.setattr(execution_mod, "_export_artifacts", lambda result, config: {})

    events: list[dict] = []
    result = run_mode(
        TUIExecutionConfig(target="Case", modules=["stub_aggregate"]),
        "aggregate",
        events.append,
    )

    assert result.mode == "aggregate"
    module_events = [event for event in events if event["type"] == "module"]
    assert any(event["status"] == "queued" for event in module_events)
    assert any(event["status"] == "done" for event in module_events)
    assert any(event["type"] == "activity" and "fast complete" in event["text"] for event in events)


def test_run_mode_chain_emits_detailed_phase_counters(monkeypatch, tmp_path):
    import tui.execution as execution_mod

    class FakeDB:
        def execute(self, *args, **kwargs):
            return self

        def commit(self):
            return None

    class FakeEngine:
        def __init__(self, db_path):
            self.db_path = db_path
            self.db = FakeDB()
            self._all_observables = []
            self.clusters = []

        def ingest_metadata(self, path):
            if Path(path).name.endswith("a.json"):
                return {"status": "ingested"}
            return {"status": "rejected"}

        def resolve_entities(self):
            self.clusters = [type("Cluster", (), {"label": "Case Cluster"})()]
            return self.clusters

        def verify_profiles(self, max_checks, timeout, proxy=None):
            return None

        def verify_content(self, max_checks, timeout, proxy=None):
            return None

        def render_graph_report(self, output_path, redaction_mode="shareable"):
            Path(output_path).write_text("ok", encoding="utf-8")

        def get_stats(self):
            return {"ok": True}

        def _classify_and_register(self, **kwargs):
            return object()

    report = ReconReport(
        target_name="Case",
        modules_run=["stub_chain"],
        hits=[
            ReconHit(
                observable_type="email",
                value="chain@example.com",
                source_module="stub_chain",
                source_detail="fixture",
                confidence=0.8,
            )
        ],
        errors=[],
        started_at="2026-04-08T01:00:00",
        finished_at="2026-04-08T01:00:01",
        new_emails=["chain@example.com"],
    )

    exports_dir = tmp_path / "exports"
    exports_dir.mkdir(parents=True, exist_ok=True)
    (exports_dir / "a.json").write_text("{}", encoding="utf-8")
    (exports_dir / "b.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(execution_mod, "DiscoveryEngine", FakeEngine)
    monkeypatch.setattr(execution_mod, "run_preflight", lambda modules=None: [])
    monkeypatch.setattr(execution_mod, "resolve_modules", lambda modules=None: list(modules or []))
    monkeypatch.setattr(execution_mod, "_run_deep_recon_live", lambda engine, config, modules, event_sink: report)
    monkeypatch.setattr(execution_mod, "_export_artifacts", lambda result, config: {})

    events: list[dict] = []
    result = run_mode(
        TUIExecutionConfig(
            target="Case",
            modules=["stub_chain"],
            exports_dir=str(exports_dir),
            db_path=str(tmp_path / "discovery.db"),
            verify=True,
            verify_content=True,
        ),
        "chain",
        events.append,
    )

    assert result.mode == "chain"
    counter_events = [event for event in events if event["type"] == "phase_counters"]
    phases = {event["phase"] for event in counter_events}
    assert {"ingest", "resolve", "deep_recon", "verify_profiles", "verify_content", "render"}.issubset(phases)
    ingest_updates = [event for event in counter_events if event["phase"] == "ingest"]
    assert any(event["counters"].get("total_files") == 2 for event in ingest_updates)
    assert any(event["counters"].get("ingested") == 1 for event in ingest_updates)


def test_emit_redacts_sensitive_values_in_phase_counters():
    import tui.execution as execution_mod

    events: list[dict] = []
    execution_mod._emit(
        events.append,
        "phase_counters",
        phase="verify_profiles",
        counters={
            "proxy": "socks5h://127.0.0.1:9050",
            "known_phones": ["+380991234567"],
            "known_usernames": ["sensitive_user"],
        },
    )

    payload = events[-1]
    counters = payload["counters"]
    assert counters["proxy"] == "socks5h://***:9050"
    assert counters["known_phones"][0] != "+380991234567"
    assert counters["known_usernames"][0] != "sensitive_user"


def test_emit_redacts_sensitive_values_in_event_counters_payload():
    import tui.execution as execution_mod

    events: list[dict] = []
    execution_mod._emit(
        events.append,
        "event_counters",
        counters={
            "proxy": "socks5h://10.0.0.2:9050",
            "new_phones": ["+12025550173"],
            "new_emails": ["operator@example.com"],
        },
    )

    payload = events[-1]
    counters = payload["counters"]
    assert counters["proxy"] == "socks5h://***:9050"
    assert counters["new_phones"][0] != "+12025550173"
    assert counters["new_emails"][0] != "operator@example.com"