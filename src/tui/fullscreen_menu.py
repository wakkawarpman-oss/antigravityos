#!/usr/bin/env python3
"""Full-screen operator menu for HANNA.

This menu is optional and uses prompt_toolkit when available.
Navigation: Up/Down arrows, Enter to execute, Escape to exit.
"""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Optional

from tui.nav import show_help

try:
    from prompt_toolkit.application import Application
    from prompt_toolkit.enums import EditingMode
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.layout import HSplit, Layout, Window
    from prompt_toolkit.layout.controls import FormattedTextControl
    from prompt_toolkit.styles import Style
except Exception as exc:  # pragma: no cover
    Application = None
    EditingMode = None
    KeyBindings = None
    HSplit = None
    Layout = None
    Window = None
    FormattedTextControl = None
    Style = None
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None


CHOICES: list[tuple[str, str]] = [
    ("run", "Run OSINT pipeline"),
    ("prelaunch", "Release gate (prelaunch)"),
    ("rehearsal", "Full canary rehearsal"),
    ("status", "Status/info"),
    ("textual_tui", "Launch main Textual TUI"),
    ("shell", "Interactive CLI shell"),
    ("exit", "Exit"),
]


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


def _dispatch(choice: str) -> None:
    if choice == "run":
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

    if choice == "shell":
        try:
            from tui.interactive_shell import main as shell_main

            shell_main()
        except Exception as exc:
            print(f"Interactive shell unavailable: {exc}")
        return


def _build_fragments(selected_index: int) -> list[tuple[str, str]]:
    fragments: list[tuple[str, str]] = [
        ("class:title", " HANNA Full-Screen Menu\n"),
        ("class:subtitle", " Use Up/Down + Enter. Esc to quit.\n\n"),
    ]
    for idx, (_key, label) in enumerate(CHOICES):
        if idx == selected_index:
            fragments.append(("class:choice.focus", f" > {idx + 1}. {label}\n"))
        else:
            fragments.append(("class:choice", f"   {idx + 1}. {label}\n"))
    fragments.append(("class:footer", "\nEsc exits menu."))
    return fragments


def _menu_once() -> Optional[str]:
    state = {"selected": 0}

    def _text() -> list[tuple[str, str]]:
        return _build_fragments(state["selected"])

    control = FormattedTextControl(_text)
    window = Window(content=control)

    kb = KeyBindings()

    @kb.add("up")
    def _up(event) -> None:
        state["selected"] = max(0, state["selected"] - 1)
        event.app.invalidate()

    @kb.add("down")
    def _down(event) -> None:
        state["selected"] = min(len(CHOICES) - 1, state["selected"] + 1)
        event.app.invalidate()

    @kb.add("enter")
    def _enter(event) -> None:
        event.app.exit(result=CHOICES[state["selected"]][0])

    @kb.add("escape")
    def _escape(event) -> None:
        event.app.exit(result="exit")

    @kb.add("h")
    def _help(_event) -> None:
        show_help(
            {
                "up/down": ("Move selection", None),
                "enter": ("Execute selected action", None),
                "escape": ("Exit menu", None),
                "h": ("Open this help palette", None),
            },
            title="HANNA Menu Keys",
        )

    app = Application(
        layout=Layout(HSplit([window])),
        key_bindings=kb,
        full_screen=True,
        editing_mode=EditingMode.EMACS,
        style=Style.from_dict(
            {
                "title": "#b1b1b1 bold",
                "subtitle": "#aaaaaa",
                "choice": "#ffffff",
                "choice.focus": "bg:#005f5f #ffffff bold",
                "footer": "#888888",
            }
        ),
    )
    return app.run()


def main() -> int:
    if _IMPORT_ERROR is not None:
        print("prompt_toolkit is required for full-screen menu.", file=sys.stderr)
        print("Install it with: pip install prompt_toolkit", file=sys.stderr)
        return 1

    while True:
        choice = _menu_once()
        if not choice or choice == "exit":
            print("Goodbye")
            return 0
        _dispatch(choice)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
