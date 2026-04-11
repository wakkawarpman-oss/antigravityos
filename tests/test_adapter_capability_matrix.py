from __future__ import annotations

import adapters.base as base_mod

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
