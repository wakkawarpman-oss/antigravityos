from __future__ import annotations

from dossier.bootscreen import show_boot_screen
from dossier.cli_shell import run_interactive_shell
from dossier.menu import run_main_menu
from dossier.tui import run_tui_dossier_app


def run_boot_then_menu() -> int:
    booted = show_boot_screen()
    if not booted:
        return 1

    while True:
        action = run_main_menu()
        if action == "dossier":
            run_tui_dossier_app()
        elif action == "history":
            from analytics.ui_dossier_history import main as history_main

            history_main()
        elif action == "shell":
            run_interactive_shell(show_boot=False)
        else:
            return 0


def main() -> None:
    raise SystemExit(run_boot_then_menu())


if __name__ == "__main__":
    main()
