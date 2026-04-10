from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path

import pytest


@pytest.fixture
def fresh_preflight_module():
    import preflight as preflight_mod

    return importlib.reload(preflight_mod)


def test_preflight_tor_policy_fails_without_socks5h_when_required(monkeypatch, fresh_preflight_module):
    preflight_mod = fresh_preflight_module
    monkeypatch.setattr(preflight_mod, "TOR_ENABLED", True)
    monkeypatch.setattr(preflight_mod, "TOR_REQUIRE_SOCKS5H", True)
    monkeypatch.setattr(preflight_mod, "TOR_PROXY_URL", "socks5://127.0.0.1:9050")
    monkeypatch.setattr(preflight_mod, "TOR_CONTROL_ENABLED", False)

    checks = preflight_mod.run_preflight(modules=["ua_phone"])
    tor_check = next(check for check in checks if check.name == "tor_policy")

    assert tor_check.status == "fail"
    assert "socks5h://" in tor_check.detail


def test_preflight_tor_policy_ok_when_disabled(monkeypatch, fresh_preflight_module):
    preflight_mod = fresh_preflight_module
    monkeypatch.setattr(preflight_mod, "TOR_ENABLED", False)

    checks = preflight_mod.run_preflight(modules=["ua_phone"])
    tor_check = next(check for check in checks if check.name == "tor_policy")

    assert tor_check.status == "ok"
    assert tor_check.detail == "disabled"


def test_run_discovery_proxy_policy_validation(monkeypatch):
    module_path = Path(__file__).resolve().parents[1] / "src" / "run_discovery.py"
    spec = importlib.util.spec_from_file_location("run_discovery_tor_policy", module_path)
    assert spec is not None and spec.loader is not None
    rd = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = rd
    spec.loader.exec_module(rd)

    monkeypatch.setattr(rd, "TOR_ENABLED", True)
    monkeypatch.setattr(rd, "TOR_REQUIRE_SOCKS5H", True)
    monkeypatch.setattr(rd, "TOR_PROXY_URL", "socks5h://tor-proxy:9050")

    assert rd._resolve_effective_proxy(None) == "socks5h://tor-proxy:9050"

    rd._validate_proxy_policy("socks5h://127.0.0.1:9050")
    with pytest.raises(SystemExit):
        rd._validate_proxy_policy("socks5://127.0.0.1:9050")


def test_tui_scheduler_event_emits_tor_rotation_messages():
    module_path = Path(__file__).resolve().parents[1] / "src" / "tui" / "execution.py"
    spec = importlib.util.spec_from_file_location("tui_execution_tor_events", module_path)
    assert spec is not None and spec.loader is not None
    execution_mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = execution_mod
    spec.loader.exec_module(execution_mod)

    events: list[dict] = []
    sink = events.append

    execution_mod._emit_scheduler_event(
        sink,
        {
            "type": "tor_rotation_policy",
            "policy": "batch_on_error",
            "cooldown_sec": 10,
        },
    )
    execution_mod._emit_scheduler_event(
        sink,
        {
            "type": "tor_rotation_requested",
            "reason": "task_timeout",
            "module": "ua_phone",
        },
    )
    execution_mod._emit_scheduler_event(
        sink,
        {
            "type": "tor_rotation_checkpoint",
            "reason": "dispatch_complete",
            "policy": "batch_on_error",
        },
    )

    activity_texts = [event.get("text", "") for event in events if event.get("type") == "activity"]
    assert any("TOR rotation policy active" in text for text in activity_texts)
    assert any("TOR rotation requested" in text for text in activity_texts)
    assert any("TOR rotation checkpoint" in text for text in activity_texts)


def test_prelaunch_tor_policy_payload_can_be_required():
    gate_path = Path(__file__).resolve().parents[1] / "scripts" / "prelaunch_gate.py"
    spec = importlib.util.spec_from_file_location("prelaunch_gate_tor_req", gate_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    payload = {
        "checks": {
            "preflight": {"status": "pass"},
            "smart_summary": {"status": "pass"},
            "focused_regression": {"status": "pass"},
            "live_smoke": {"status": "not-run"},
            "tor_policy": {"status": "pass"},
            "full_rollout_rehearsal": {"status": "not-run"},
        }
    }

    failures = module.evaluate_required_checks(payload, ["tor_policy"])
    assert failures == []
