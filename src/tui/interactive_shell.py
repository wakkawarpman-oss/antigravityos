#!/usr/bin/env python3
"""Interactive shell entrypoint for HANNA CLI.

This module provides a simple operator menu and a command prompt loop.
It invokes existing CLI commands through the same python runtime so the
behavior stays identical to direct `hanna` CLI usage.
"""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Optional

from tui.main_menu.widgets.menu_list import CHOICES

try:
    from prompt_toolkit import prompt as pt_prompt
    from prompt_toolkit.completion import WordCompleter
except Exception:  # pragma: no cover - optional dependency
    pt_prompt = None
    WordCompleter = None


def _run_hanna(parts: list[str]) -> int:
    """Execute src/cli.py with given argument parts."""
    cli_path = Path(__file__).resolve().parents[1] / "cli.py"
    result = subprocess.run(
        [sys.executable, str(cli_path), *parts],
        text=True,
        capture_output=True,
    )
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print("Stderr:", file=sys.stderr)
        print(result.stderr, file=sys.stderr, end="")
    return int(result.returncode)


def _menu_target_prompt() -> Optional[str]:
    try:
        value = input("Target (email/phone/username/domain/IP): ").strip()
        return value or None
    except (KeyboardInterrupt, EOFError):
        return None


def _menu_loop() -> None:
    print("Hanna OSINT Interactive Menu")
    print("=" * 40)
    while True:
        for idx, (_key, label) in enumerate(CHOICES, start=1):
            print(f"{idx}. {label}")
        try:
            choice = input("Choice: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye")
            return

        key = _resolve_choice_key(choice)
        if not key:
            print(f"Invalid choice. Use 1-{len(CHOICES)}.")
            continue

        if not _dispatch_menu_choice(key):
            print("Goodbye")
            return


def _resolve_choice_key(choice: str) -> Optional[str]:
    if choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(CHOICES):
            return CHOICES[idx][0]
    names = {key for key, _label in CHOICES}
    if choice in names:
        return choice
    return None


def _dispatch_menu_choice(key: str) -> bool:
    if key == "run":
        target = _menu_target_prompt()
        if target:
            _run_hanna(["aggregate", "--target", target])
        return True

    if key == "prelaunch":
        _run_prelaunch_script(rehearsal=False)
        return True

    if key == "rehearsal":
        _run_prelaunch_script(rehearsal=True)
        return True

    if key == "status":
        _run_hanna(["list"])
        return True

    if key == "textual_tui":
        _run_hanna(["tui", "--plain"])
        return True

    if key == "prompt":
        _prompt_loop()
        return True

    if key == "nav_demo":
        _nav_demo()
        return True

    if key == "shell":
        _prompt_loop()
        return True

    if key == "exit":
        return False

    print(f"Unsupported choice: {key}")
    return True


def _run_prelaunch_script(rehearsal: bool) -> int:
    script = Path(__file__).resolve().parents[2] / "scripts" / "prelaunch_check.sh"
    env = os.environ.copy()
    if rehearsal:
        env.setdefault("HANNA_RUN_FULL_REHEARSAL", "1")
        env.setdefault("HANNA_FULL_REHEARSAL_TARGET", "example.com")
        env.setdefault("HANNA_FULL_REHEARSAL_MODULES", "pd-infra-quick")
    return int(subprocess.call(["bash", str(script)], cwd=str(script.parent.parent), env=env))


def _read_head_lines(path: Path, limit: int = 300) -> list[str]:
    try:
        with path.open("r", encoding="utf-8", errors="replace") as f:
            return [line.rstrip("\n") for _, line in zip(range(limit), f)]
    except Exception:
        return [f"[unreadable] {path}"]


def _latest_prelaunch_bundle() -> Optional[Path]:
    root = Path(__file__).resolve().parents[2] / ".cache" / "prelaunch"
    if not root.exists():
        return None
    dirs = [p for p in root.iterdir() if p.is_dir()]
    if not dirs:
        return None
    return max(dirs, key=lambda p: p.stat().st_mtime)


def _nav_demo() -> None:
    try:
        from tui.nav import show_menu, show_search_panes
    except Exception as exc:
        print(f"Navigation demo unavailable: {exc}")
        return

    bundle = _latest_prelaunch_bundle()
    if bundle is None:
        print("No prelaunch bundle found under .cache/prelaunch.")
        return

    gate = bundle / "gate-result.json"
    summary = bundle / "final-summary.json"
    pytest_err = bundle / "pytest.err"

    choice = show_menu(
        [
            ("summary", f"Summary: {summary.name}"),
            ("gate", f"Gate: {gate.name}"),
            ("pytest", f"Pytest: {pytest_err.name}"),
            ("back", "Back"),
        ],
        title=f"Nav Demo Bundle: {bundle.name}",
        header="Pick file to open searchable view",
    )
    if choice in {None, "back"}:
        return

    selected_path = {
        "summary": summary,
        "gate": gate,
        "pytest": pytest_err,
    }.get(choice)
    if selected_path is None or not selected_path.exists():
        print(f"File missing: {selected_path}")
        return

    lines = _read_head_lines(selected_path)
    show_search_panes(lines, title=f"Search: {selected_path.name}")


def _prompt_loop() -> None:
    commands = [
        "chain",
        "aggregate",
        "manual",
        "tui",
        "list",
        "preflight",
        "reset",
        "summarize",
        "nav-demo",
        "help",
        "menu",
        "exit",
        "quit",
    ]
    completer = WordCompleter(commands) if WordCompleter else None
    print("Prompt mode: type 'help', 'menu', or 'exit'.")
    while True:
        try:
            if pt_prompt:
                line = pt_prompt("hanna> ", completer=completer)
            else:
                line = input("hanna> ")
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye")
            return
        cmd = (line or "").strip()
        if not cmd:
            continue
        if cmd in {"exit", "quit"}:
            return
        if cmd == "menu":
            return
        if cmd == "help":
            _run_hanna(["--help"])
            continue
        if cmd == "nav-demo":
            _nav_demo()
            continue
        _run_hanna(shlex.split(cmd))


def main() -> int:
    _menu_loop()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
