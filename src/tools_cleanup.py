from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


@dataclass
class CommandResult:
    code: int
    stdout: str
    stderr: str


@dataclass
class CleanupAction:
    kind: str
    tool_path: str
    command: str
    reason: str


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
    tools: list[str] = []
    for line in gitmodules.read_text(encoding="utf-8", errors="replace").splitlines():
        raw = line.strip()
        if raw.startswith("path = "):
            path = raw.split("=", 1)[1].strip()
            if path.startswith("tools/"):
                tools.append(path)
    return sorted(dict.fromkeys(tools))


def _read_gitlink_tools(repo_root: Path, run: Runner | None = None) -> list[str]:
    runner = run or _default_runner
    out = runner("git ls-files --stage -- tools")
    paths: list[str] = []
    for line in (out.stdout or "").splitlines():
        raw = line.strip()
        if not raw:
            continue
        # format: <mode> <sha> <stage>\t<path>
        if "\t" not in raw:
            continue
        header, path = raw.split("\t", 1)
        mode = header.split()[0] if header.split() else ""
        if mode == "160000" and path.startswith("tools/"):
            paths.append(path)
    return sorted(dict.fromkeys(paths))


def _submodule_marker(status_line: str) -> str:
    if not status_line:
        return "?"
    return status_line[0]


def plan_cleanup_actions(repo_root: Path, run: Runner | None = None, include_tookie: bool = False) -> list[CleanupAction]:
    runner = run or _default_runner
    actions: list[CleanupAction] = []

    all_tool_paths = sorted(dict.fromkeys(_read_gitmodules_tools(repo_root) + _read_gitlink_tools(repo_root, runner)))

    for tool_path in all_tool_paths:
        status = runner(f"git submodule status -- {tool_path}")
        line = (status.stdout or "").strip().splitlines()
        status_line = line[0] if line else ""
        marker = _submodule_marker(status_line)

        if marker == "-":
            actions.append(
                CleanupAction(
                    kind="init",
                    tool_path=tool_path,
                    command=f"git submodule update --init --checkout -- {tool_path}",
                    reason="submodule missing locally",
                )
            )
            continue

        worktree = runner(f"git status --short -- {tool_path}")
        has_local_changes = bool((worktree.stdout or "").strip())
        if marker in {"+", "U"} or has_local_changes:
            actions.append(
                CleanupAction(
                    kind="reset",
                    tool_path=tool_path,
                    command=(
                        f"git -C {tool_path} reset --hard && "
                        f"git -C {tool_path} clean -fdx && "
                        f"git submodule update --checkout -- {tool_path}"
                    ),
                    reason="local submodule drift",
                )
            )

    if include_tookie and (repo_root / "tools" / "tookie-osint").exists():
        status = runner("git status --short -- tools/tookie-osint")
        if (status.stdout or "").strip():
            actions.append(
                CleanupAction(
                    kind="remove",
                    tool_path="tools/tookie-osint",
                    command="rm -rf tools/tookie-osint",
                    reason="optional external checkout cleanup",
                )
            )

    return actions


def apply_cleanup_actions(
    actions: list[CleanupAction],
    repo_root: Path,
    run: Runner | None = None,
    allow_destructive: bool = False,
) -> list[dict]:
    runner = run or _default_runner
    results: list[dict] = []

    for action in actions:
        destructive = action.kind in {"reset", "remove"}
        if destructive and not allow_destructive:
            results.append(
                {
                    "tool_path": action.tool_path,
                    "kind": action.kind,
                    "status": "skipped",
                    "reason": "destructive action requires --allow-destructive",
                }
            )
            continue

        out = runner(action.command)
        results.append(
            {
                "tool_path": action.tool_path,
                "kind": action.kind,
                "status": "applied" if out.code == 0 else "failed",
                "exit_code": out.code,
                "output_tail": (out.stdout + out.stderr).strip()[-1000:],
            }
        )

    return results
