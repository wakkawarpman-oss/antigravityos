#!/usr/bin/env python3
"""Textual-based operator menu for HANNA.

Business actions are unchanged: this module only maps menu selections to
existing CLI and script entrypoints.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _run_cli(parts: list[str], capture: bool = True) -> int:
    cli_path = _repo_root() / "src" / "cli.py"
    if capture:
        result = subprocess.run([sys.executable, str(cli_path), *parts], text=True, capture_output=True)
        if result.stdout:
            print(result.stdout, end="")
        if result.stderr:
            print("Stderr:", file=sys.stderr)
            print(result.stderr, file=sys.stderr, end="")
        return int(result.returncode)
    return int(subprocess.call([sys.executable, str(cli_path), *parts]))


def _run_prelaunch() -> int:
    script = _repo_root() / "scripts" / "prelaunch_check.sh"
    return int(subprocess.call(["bash", str(script)], cwd=str(_repo_root())))


def _run_rehearsal() -> int:
    script = _repo_root() / "scripts" / "prelaunch_check.sh"
    env = os.environ.copy()
    env.setdefault("HANNA_RUN_FULL_REHEARSAL", "1")
    env.setdefault("HANNA_FULL_REHEARSAL_TARGET", "example.com")
    env.setdefault("HANNA_FULL_REHEARSAL_MODULES", "pd-infra-quick")
    return int(subprocess.call(["bash", str(script)], cwd=str(_repo_root()), env=env))


def _dispatch(choice: str, target_override: str = "") -> None:
    if choice == "run":
        target = (target_override or "").strip()
        if not target:
            try:
                target = input("Target (email/phone/username/domain/IP): ").strip()
            except (KeyboardInterrupt, EOFError):
                return
        if not target:
            print("Empty target, skipped.")
            return
        _run_cli(["aggregate", "--target", target])
        return

    if choice == "prelaunch":
        _run_prelaunch()
        return

    if choice == "rehearsal":
        _run_rehearsal()
        return

    if choice == "status":
        _run_cli(["list"])
        return

    if choice == "textual_tui":
        try:
            from tui import HannaTUIApp, build_default_session_state

            app = HannaTUIApp(session_state=build_default_session_state(), plain=True)
            app.run()
        except Exception:
            _run_cli(["tui", "--plain"], capture=False)
        return

    if choice == "prompt":
        try:
            from tui.interactive_shell import _prompt_loop

            _prompt_loop()
        except Exception as exc:
            print(f"Prompt mode unavailable: {exc}")
        return

    if choice == "nav_demo":
        try:
            from tui.interactive_shell import _nav_demo

            _nav_demo()
        except Exception as exc:
            print(f"Nav demo unavailable: {exc}")
        return

    if choice == "shell":
        try:
            from tui.interactive_shell import main as shell_main

            shell_main()
        except Exception as exc:
            print(f"Interactive shell unavailable: {exc}")
        return


def main() -> int:
    try:
        from tui.main_menu.app import run_main_menu
    except Exception as exc:
        print(f"Textual main menu unavailable ({exc}), switching to interactive menu.", file=sys.stderr)
        try:
            from tui.interactive_shell import main as shell_main

            return int(shell_main())
        except Exception as inner_exc:
            print(f"Interactive menu fallback failed: {inner_exc}", file=sys.stderr)
            return 1

    while True:
        selection = run_main_menu()
        if not selection or selection.choice == "exit":
            print("Goodbye")
            return 0
        _dispatch(selection.choice, target_override=selection.target)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
