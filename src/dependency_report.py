from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable


@dataclass
class CommandResult:
    code: int
    stdout: str
    stderr: str


Runner = Callable[[str], CommandResult]


def _default_runner(command: str) -> CommandResult:
    proc = subprocess.run(
        command,
        shell=True,
        text=True,
        capture_output=True,
        check=False,
    )
    return CommandResult(code=proc.returncode, stdout=proc.stdout or "", stderr=proc.stderr or "")


def _safe_json_loads(payload: str, fallback):
    payload = (payload or "").strip()
    if not payload:
        return fallback
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        return fallback


def _collect_python_section(run: Runner) -> dict:
    outdated = run("python -m pip list --outdated --format=json")
    outdated_items = _safe_json_loads(outdated.stdout, [])
    if not isinstance(outdated_items, list):
        outdated_items = []

    pip_check = run("python -m pip check")

    return {
        "outdated_count": len(outdated_items),
        "outdated": outdated_items,
        "pip_check": {
            "status": "pass" if pip_check.code == 0 else "fail",
            "exit_code": pip_check.code,
            "output": (pip_check.stdout + pip_check.stderr).strip()[-4000:],
        },
    }


def _collect_node_section(run: Runner) -> dict:
    npm_outdated = run("npm outdated --json")
    outdated_obj = _safe_json_loads(npm_outdated.stdout, {})
    if not isinstance(outdated_obj, dict):
        outdated_obj = {}

    npm_audit = run("npm audit --omit=dev --audit-level=high --json")
    audit_obj = _safe_json_loads(npm_audit.stdout, {})
    vulnerabilities = {}
    metadata = audit_obj.get("metadata") if isinstance(audit_obj, dict) else None
    if isinstance(metadata, dict) and isinstance(metadata.get("vulnerabilities"), dict):
        vulnerabilities = metadata["vulnerabilities"]

    high_count = int(vulnerabilities.get("high", 0) or 0)
    critical_count = int(vulnerabilities.get("critical", 0) or 0)

    return {
        "outdated_count": len(outdated_obj.keys()),
        "outdated": outdated_obj,
        "audit": {
            "status": "pass" if npm_audit.code == 0 else "fail",
            "exit_code": npm_audit.code,
            "high": high_count,
            "critical": critical_count,
            "raw_tail": (npm_audit.stdout + npm_audit.stderr).strip()[-4000:],
        },
    }


def _build_kpi(python_section: dict, node_section: dict) -> dict:
    pip_ok = python_section.get("pip_check", {}).get("status") == "pass"
    audit = node_section.get("audit", {})
    high = int(audit.get("high", 0) or 0)
    critical = int(audit.get("critical", 0) or 0)

    blocker = (not pip_ok) or high > 0 or critical > 0
    return {
        "core_dependency_lane_status": "pass" if not blocker else "fail",
        "policy": "Block release on pip_check fail or npm high/critical vulnerabilities",
        "blockers": {
            "pip_check_failed": not pip_ok,
            "npm_high": high,
            "npm_critical": critical,
        },
    }


def collect_dependency_report(run: Runner | None = None) -> dict:
    runner = run or _default_runner
    python_section = _collect_python_section(runner)
    node_section = _collect_node_section(runner)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "python": python_section,
        "node": node_section,
        "kpi": _build_kpi(python_section, node_section),
    }


def render_markdown(report: dict) -> str:
    py = report.get("python", {})
    node = report.get("node", {})
    kpi = report.get("kpi", {})
    blockers = kpi.get("blockers", {})

    lines = [
        "# Weekly Dependency Report",
        "",
        f"- Generated: {report.get('generated_at', 'unknown')}",
        f"- Core lane status: **{kpi.get('core_dependency_lane_status', 'unknown')}**",
        "",
        "## Python",
        f"- Outdated packages: {py.get('outdated_count', 0)}",
        f"- pip check: {py.get('pip_check', {}).get('status', 'unknown')}",
        "",
        "## Node",
        f"- Outdated packages: {node.get('outdated_count', 0)}",
        f"- npm audit high: {blockers.get('npm_high', 0)}",
        f"- npm audit critical: {blockers.get('npm_critical', 0)}",
        "",
        "## Release Policy",
        f"- {kpi.get('policy', 'n/a')}",
    ]
    return "\n".join(lines) + "\n"
