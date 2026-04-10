from __future__ import annotations

from typing import Optional

try:
    from textual.app import App, ComposeResult
    from textual.containers import Vertical
    from textual.widgets import Button, Label
except Exception as exc:  # pragma: no cover - optional dependency
    raise RuntimeError("Textual is required to run dossier main menu") from exc


class DossierMainMenu(App[str]):
    """Main menu shown after cyber boot screen."""

    BINDINGS = [
        ("d", "open_dossier", "Run dossier"),
        ("h", "open_history", "History"),
        ("s", "open_shell", "Shell"),
        ("q", "quit_menu", "Exit"),
        ("escape", "quit_menu", "Exit"),
        ("enter", "open_dossier", "Run dossier"),
    ]

    CSS = """
    Screen { layout: vertical; background: black; color: #00ff99; }
    #root { align: center middle; width: 60; height: auto; border: round #00ffcc; padding: 1; }
    Label { content-align: center middle; color: #ff66ff; margin-bottom: 1; }
    Button { margin: 0 0 1 0; }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="root"):
            yield Label("MAIN MENU")
            yield Label("Hotkeys: [D] dossier  [H] history  [S] shell  [Q/Esc] exit")
            yield Button("Run ONE-SHOT-Dossier", id="dossier")
            yield Button("View dossier history", id="history")
            yield Button("Launch dossier shell", id="shell")
            yield Button("Exit", id="exit")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        action = event.button.id or "exit"
        self.exit(action)

    def action_open_dossier(self) -> None:
        self.exit("dossier")

    def action_open_history(self) -> None:
        self.exit("history")

    def action_open_shell(self) -> None:
        self.exit("shell")

    def action_quit_menu(self) -> None:
        self.exit("exit")


def run_main_menu() -> Optional[str]:
    result = DossierMainMenu().run()
    if isinstance(result, str):
        return result
    return None
