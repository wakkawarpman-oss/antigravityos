from dossier import Dossier, DossierEngine, Evidence, Target


def run_cli_dossier(*args, **kwargs):
    from dossier.cli import run_cli_dossier as _run

    return _run(*args, **kwargs)


def run_interactive_shell(*args, **kwargs):
    from dossier.cli_shell import run_interactive_shell as _run

    return _run(*args, **kwargs)


def run_cyber_boot(*args, **kwargs):
    from dossier.cyber_boot import run_cyber_boot as _run

    return _run(*args, **kwargs)


def run_tui_dossier_app() -> None:
    from dossier.tui import run_tui_dossier_app as _run

    _run()

__all__ = [
    "DossierEngine",
    "Dossier",
    "Evidence",
    "Target",
    "run_cli_dossier",
    "run_interactive_shell",
    "run_cyber_boot",
    "run_tui_dossier_app",
]
