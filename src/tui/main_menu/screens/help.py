from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Label, Static


class HelpScreen(ModalScreen[None]):
    BINDINGS = [
        ("escape", "close", "Close"),
        ("enter", "close", "Close"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(classes="screen-help"):
            yield Label("HANNA Menu Keys", classes="-key")
            yield Static("Up/Down or j/k: navigate")
            yield Static("1..9: jump to option")
            yield Static("Enter: execute selected action")
            yield Static("h or ?: open this help")
            yield Static("Esc: exit menu")

    def action_close(self) -> None:
        self.dismiss(None)
