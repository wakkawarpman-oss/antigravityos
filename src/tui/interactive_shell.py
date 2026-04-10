#!/usr/bin/env python3
"""Interactive shell entrypoint for HANNA CLI.

This module provides a simple operator menu and a command prompt loop.
It invokes existing CLI commands through the same python runtime so the
behavior stays identical to direct `hanna` CLI usage.
"""

from __future__ import annotations

import shlex
import subprocess
import sys
from pathlib import Path
from typing import Optional

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
        print("\n1. Run OSINT pipeline")
        print("2. Release gate (prelaunch)")
        print("3. Full canary rehearsal")
        print("4. Status/info")
        print("5. Launch main TUI")
        print("6. Prompt mode")
        print("7. Nav demo (logs/evidence search)")
        print("8. Exit")
        try:
            choice = input("Choice: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye")
            return

        if choice == "1":
            target = _menu_target_prompt()
            if target:
                _run_hanna(["aggregate", "--target", target])
        elif choice == "2":
            _run_hanna(["preflight"])  # prelaunch wrapper remains script-driven
        elif choice == "3":
            print("Use scripts/prelaunch_check.sh with rehearsal flags for full canary.")
        elif choice == "4":
            _run_hanna(["list"])
        elif choice == "5":
            _run_hanna(["tui", "--plain"])
        elif choice == "6":
            _prompt_loop()
        elif choice == "7":
            _nav_demo()
        elif choice == "8":
            print("Goodbye")
            return
        else:
            print("Invalid choice. Use 1-8.")


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
