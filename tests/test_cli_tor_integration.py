from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest


@dataclass(frozen=True)
class TorCase:
    name: str
    env: dict[str, str]
    expected_exit: int
    expected_status: str


REPO_ROOT = Path(__file__).resolve().parents[1]
CLI_PATH = REPO_ROOT / "src" / "cli.py"


# Exit code contract for strict preflight:
# 0 -> no hard failures
# 2 -> hard failure detected (fail-fast)
CASES = [
    TorCase(
        name="tor_disabled_ignores_non_socks5h_proxy",
        env={
            "HANNA_TOR_ENABLED": "0",
            "HANNA_TOR_PROXY_URL": "socks5://127.0.0.1:9050",
            "HANNA_TOR_REQUIRE_SOCKS5H": "1",
        },
        expected_exit=0,
        expected_status="ok",
    ),
    TorCase(
        name="tor_enabled_socks5h_passes",
        env={
            "HANNA_TOR_ENABLED": "1",
            "HANNA_TOR_PROXY_URL": "socks5h://127.0.0.1:9050",
            "HANNA_TOR_REQUIRE_SOCKS5H": "1",
            "HANNA_TOR_CONTROL_ENABLED": "0",
        },
        expected_exit=0,
        expected_status="ok",
    ),
    TorCase(
        name="tor_enabled_socks5_fails_when_socks5h_required",
        env={
            "HANNA_TOR_ENABLED": "1",
            "HANNA_TOR_PROXY_URL": "socks5://127.0.0.1:9050",
            "HANNA_TOR_REQUIRE_SOCKS5H": "1",
        },
        expected_exit=2,
        expected_status="fail",
    ),
    TorCase(
        name="tor_enabled_http_fails_when_socks5h_required",
        env={
            "HANNA_TOR_ENABLED": "1",
            "HANNA_TOR_PROXY_URL": "http://127.0.0.1:8080",
            "HANNA_TOR_REQUIRE_SOCKS5H": "1",
        },
        expected_exit=2,
        expected_status="fail",
    ),
    TorCase(
        name="tor_enabled_socks5_passes_when_socks5h_not_required",
        env={
            "HANNA_TOR_ENABLED": "1",
            "HANNA_TOR_PROXY_URL": "socks5://127.0.0.1:9050",
            "HANNA_TOR_REQUIRE_SOCKS5H": "0",
        },
        expected_exit=0,
        expected_status="ok",
    ),
    TorCase(
        name="tor_control_enabled_with_valid_port_passes",
        env={
            "HANNA_TOR_ENABLED": "1",
            "HANNA_TOR_PROXY_URL": "socks5h://127.0.0.1:9050",
            "HANNA_TOR_REQUIRE_SOCKS5H": "1",
            "HANNA_TOR_CONTROL_ENABLED": "1",
            "HANNA_TOR_CONTROL_PORT": "9051",
        },
        expected_exit=0,
        expected_status="ok",
    ),
    TorCase(
        name="tor_control_enabled_with_invalid_port_fails",
        env={
            "HANNA_TOR_ENABLED": "1",
            "HANNA_TOR_PROXY_URL": "socks5h://127.0.0.1:9050",
            "HANNA_TOR_REQUIRE_SOCKS5H": "1",
            "HANNA_TOR_CONTROL_ENABLED": "1",
            "HANNA_TOR_CONTROL_PORT": "0",
        },
        expected_exit=2,
        expected_status="fail",
    ),
]


@pytest.mark.parametrize("case", CASES, ids=[case.name for case in CASES])
def test_cli_preflight_tor_policy_matrix(case: TorCase):
    env = os.environ.copy()
    env.update(case.env)

    proc = subprocess.run(
        [sys.executable, str(CLI_PATH), "preflight", "--modules", "ua_phone", "--strict", "--json-only"],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == case.expected_exit, proc.stderr

    payload = json.loads(proc.stdout.strip())
    checks = payload.get("checks", [])
    tor_check = next((item for item in checks if item.get("name") == "tor_policy"), None)

    assert tor_check is not None
    assert tor_check.get("status") == case.expected_status
