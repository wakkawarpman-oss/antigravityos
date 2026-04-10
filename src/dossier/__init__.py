from .core import DossierEngine
from .engine import Dossier, DossierRun, Evidence, Target


def run_cli_dossier(*args, **kwargs):
    from .cli import run_cli_dossier as _run

    return _run(*args, **kwargs)


def run_interactive_shell(*args, **kwargs):
    from .cli_shell import run_interactive_shell as _run

    return _run(*args, **kwargs)


def run_boot_then_menu(*args, **kwargs):
    from .launch import run_boot_then_menu as _run

    return _run(*args, **kwargs)


def run_main_menu(*args, **kwargs):
    from .menu import run_main_menu as _run

    return _run(*args, **kwargs)


def show_cyberpunk_boot(*args, **kwargs):
    from .prompt_boot import show_cyberpunk_boot as _run

    return _run(*args, **kwargs)


def run_cyber_boot(*args, **kwargs):
    from .cyber_boot import run_cyber_boot as _run

    return _run(*args, **kwargs)


def run_tui_dossier_app() -> None:
    from .tui import run_tui_dossier_app as _run

    _run()

__all__ = [
    "Dossier",
    "DossierEngine",
    "DossierRun",
    "Evidence",
    "Target",
    "run_cli_dossier",
    "run_interactive_shell",
    "run_boot_then_menu",
    "run_main_menu",
    "show_cyberpunk_boot",
    "run_cyber_boot",
    "run_tui_dossier_app",
]
