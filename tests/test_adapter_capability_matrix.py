from __future__ import annotations

import subprocess

import adapters.base as base_mod
from adapters import cli_common

from registry import MODULES, MODULE_PRESETS, MODULE_LANE, MODULE_PRIORITY, resolve_modules


def test_all_preset_modules_are_registered():
    registered = set(MODULES.keys())
    for preset, modules in MODULE_PRESETS.items():
        missing = [name for name in modules if name not in registered]
        assert not missing, f"Preset {preset} has unregistered modules: {missing}"


def test_registered_modules_have_lane_and_priority():
    for module_name in MODULES.keys():
        assert module_name in MODULE_LANE, f"Missing lane for module {module_name}"
        assert module_name in MODULE_PRIORITY, f"Missing priority for module {module_name}"


def test_resolve_modules_accepts_presets_without_duplicates():
    resolved = resolve_modules(["pd-infra-quick", "pd-infra-quick", "naabu"])
    assert resolved.count("naabu") == 1
    assert "httpx_probe" in resolved
    assert "nuclei" in resolved
    assert "dnsx" in resolved


def test_critical_presets_contain_expected_modules():
    assert {"httpx_probe", "katana", "nuclei", "naabu", "dnsx"}.issubset(set(MODULE_PRESETS["pd-infra-quick"]))
    assert "ua_phone" in MODULE_PRESETS["person-deep"]
    assert "ghunt" in MODULE_PRESETS["email-chain"]
    assert "gau" in MODULE_PRESETS["recon-auto"]


def test_all_registered_adapters_require_proxy_when_policy_enforced(monkeypatch):
    monkeypatch.setattr(base_mod, "REQUIRE_PROXY", True)
    failures: list[str] = []
    for module_name, adapter_cls in MODULES.items():
        try:
            adapter_cls(proxy=None, timeout=1.0)
        except RuntimeError:
            continue
        except Exception as exc:  # pragma: no cover - diagnostic branch
            failures.append(f"{module_name}:unexpected:{type(exc).__name__}")
            continue
        failures.append(f"{module_name}:missing_runtime_error")
    assert failures == []


def test_all_registered_adapters_allow_init_with_proxy(monkeypatch):
    monkeypatch.setattr(base_mod, "REQUIRE_PROXY", True)
    failures: list[str] = []
    for module_name, adapter_cls in MODULES.items():
        try:
            adapter_cls(proxy="socks5h://127.0.0.1:9050", timeout=1.0)
        except Exception as exc:  # pragma: no cover - diagnostic branch
            failures.append(f"{module_name}:{type(exc).__name__}:{exc}")
    assert failures == []


def test_cli_timeout_burst_cleanup_meets_acceptance(monkeypatch):
    cli_common.reset_process_lifecycle_stats()

    def _fake_run(*_args, **_kwargs):
        exc = subprocess.TimeoutExpired(cmd=["dummy"], timeout=0.01, output="", stderr="err")
        exc.pid = 4321  # type: ignore[attr-defined]
        raise exc

    monkeypatch.setattr(cli_common.subprocess, "run", _fake_run)
    monkeypatch.setattr(cli_common, "_resolve_executable", lambda exe, _path: exe)
    monkeypatch.setattr(cli_common.os, "getpgid", lambda pid: pid)
    monkeypatch.setattr(cli_common.os, "killpg", lambda _pgid, _sig: None)

    for _ in range(25):
        proc = cli_common.run_cli(["dummy"], timeout=0.01, proxy="socks5h://127.0.0.1:9050")
        assert proc is not None
        assert proc.returncode == 124

    verdict = cli_common.process_lifecycle_acceptance(min_success_ratio=1.0, max_failed_kills=0)

    assert verdict["ok"] is True
    assert verdict["timeout_events"] == 25
    assert verdict["kill_attempted"] == 25
    assert verdict["kill_succeeded"] == 25
    assert verdict["kill_failed"] == 0
    assert verdict["kill_success_ratio"] == 1.0
