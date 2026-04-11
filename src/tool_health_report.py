from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
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


def _read_gitmodules_tools(repo_root: Path) -> list[str]:
    gitmodules = repo_root / ".gitmodules"
    if not gitmodules.exists():
        return []
    paths: list[str] = []
    for line in gitmodules.read_text(encoding="utf-8", errors="replace").splitlines():
        raw = line.strip()
        if raw.startswith("path = "):
            path = raw.split("=", 1)[1].strip()
            if path.startswith("tools/"):
                paths.append(path)
    return sorted(dict.fromkeys(paths))


def _parse_submodule_state(line: str) -> tuple[str, str]:
    if not line:
        return ("unknown", "empty status line")
    marker = line[0]
    detail = line.strip()
    if marker == " ":
        return ("clean", detail)
    if marker == "-":
        return ("missing", detail)
    if marker == "+":
        return ("dirty", detail)
    if marker == "U":
        return ("conflict", detail)
    return ("unknown", detail)


def _severity_for_state(state: str) -> str:
    if state in {"conflict", "missing"}:
        return "high"
    if state in {"dirty", "unknown"}:
        return "medium"
    return "low"


def _overall_status(items: list[dict]) -> str:
    severities = {item.get("severity") for item in items}
    if "high" in severities:
        return "degraded"
    if "medium" in severities:
        return "watch"
    return "healthy"


def collect_tool_health_report(repo_root: Path, run: Runner | None = None) -> dict:
    runner = run or _default_runner
    tools = _read_gitmodules_tools(repo_root)

    items: list[dict] = []
    for tool_path in tools:
        submodule = runner(f"git submodule status -- {tool_path}")
        line = (submodule.stdout or "").strip().splitlines()
        status_line = line[0] if line else ""
        state, detail = _parse_submodule_state(status_line)

        worktree = runner(f"git status --short -- {tool_path}")
        worktree_lines = [ln.strip() for ln in (worktree.stdout or "").splitlines() if ln.strip()]

        if worktree_lines and state == "clean":
            state = "dirty"
            detail = "worktree has local changes"

        severity = _severity_for_state(state)
        recommendation = "none"
        if state == "missing":
            recommendation = "initialize submodule before optional tool runs"
        elif state == "dirty":
            recommendation = "keep outside core lane or isolate in dedicated tools branch"
        elif state == "conflict":
            recommendation = "resolve submodule conflict before any tool-dependent operation"

        items.append(
            {
                "tool_path": tool_path,
                "state": state,
                "severity": severity,
                "detail": detail,
                "worktree_lines": worktree_lines,
                "recommendation": recommendation,
            }
        )

    # Track non-submodule tools like tookie-osint in the same report.
    tookie_path = repo_root / "tools" / "tookie-osint"
    if tookie_path.exists():
        tookie_status = runner("git status --short -- tools/tookie-osint")
        worktree_lines = [ln.strip() for ln in (tookie_status.stdout or "").splitlines() if ln.strip()]
        state = "dirty" if worktree_lines else "clean"
        items.append(
            {
                "tool_path": "tools/tookie-osint",
                "state": state,
                "severity": "medium" if state == "dirty" else "low",
                "detail": "optional external tool checkout",
                "worktree_lines": worktree_lines,
                "recommendation": "keep non-blocking in core lane; isolate changes in dedicated tools workflow",
            }
        )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "overall_status": _overall_status(items),
        "policy": {
            "lane": "non-blocking tool health",
            "core_release_blocking": False,
            "intent": "detect tool drift early without blocking core release lane",
        },
        "items": items,
    }


def render_markdown(report: dict) -> str:
    lines = [
        "# Tool Health Report",
        "",
        f"- Generated: {report.get('generated_at', 'unknown')}",
        f"- Overall status: **{report.get('overall_status', 'unknown')}**",
        "- Lane: non-blocking tool health",
        "",
        "## Items",
    ]

    for item in report.get("items", []):
        lines.append(f"- {item.get('tool_path')}: state={item.get('state')} severity={item.get('severity')}")
        lines.append(f"  detail: {item.get('detail')}")
        rec = item.get("recommendation")
        if rec:
            lines.append(f"  recommendation: {rec}")

    return "\n".join(lines) + "\n"


def to_json(report: dict) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2)
