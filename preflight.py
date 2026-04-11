"""Compatibility wrapper for src/preflight.py.

This module exists at repository root so `python3 preflight.py` works,
while preserving import compatibility expected by tests and runtime modules.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Optional


def _load_src_preflight():
    repo_root = Path(__file__).resolve().parent
    src_dir = repo_root / "src"
    module_path = src_dir / "preflight.py"
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))

    spec = importlib.util.spec_from_file_location("hanna_src_preflight", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load preflight module: {module_path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


_SRC = _load_src_preflight()

# Re-export data model and helpers used by imports/tests.
PreflightCheck = _SRC.PreflightCheck
format_preflight_report = _SRC.format_preflight_report
has_hard_failures = _SRC.has_hard_failures
preflight_summary = _SRC.preflight_summary

# Mirror policy globals so monkeypatch on this module works in tests.
TOR_ENABLED = _SRC.TOR_ENABLED
TOR_PROXY_URL = _SRC.TOR_PROXY_URL
TOR_REQUIRE_SOCKS5H = _SRC.TOR_REQUIRE_SOCKS5H
TOR_CONTROL_ENABLED = _SRC.TOR_CONTROL_ENABLED
TOR_CONTROL_PORT = _SRC.TOR_CONTROL_PORT


def _sync_policy_globals() -> None:
    _SRC.TOR_ENABLED = TOR_ENABLED
    _SRC.TOR_PROXY_URL = TOR_PROXY_URL
    _SRC.TOR_REQUIRE_SOCKS5H = TOR_REQUIRE_SOCKS5H
    _SRC.TOR_CONTROL_ENABLED = TOR_CONTROL_ENABLED
    _SRC.TOR_CONTROL_PORT = TOR_CONTROL_PORT


def run_preflight(modules: Optional[list[str]] = None):
    _sync_policy_globals()
    return _SRC.run_preflight(modules=modules)


if __name__ == "__main__":
    checks = run_preflight()
    print(format_preflight_report(checks))
    raise SystemExit(1 if has_hard_failures(checks) else 0)
