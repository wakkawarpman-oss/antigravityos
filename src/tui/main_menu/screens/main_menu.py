from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import DataTable, Input, Label, Static

from tui.main_menu.screens.log_view import LogStrip
from tui.main_menu.widgets.menu_list import MenuList


class MainMenuScreen(Screen[None]):
    def compose(self) -> ComposeResult:
        yield Static("HANNA v3.2 - Main Menu", id="hanna-header")
        yield Static("Use Up/Down or j/k, Enter execute, h/? help, Esc exit", id="hanna-subtitle")

        with Horizontal(id="menu-layout"):
            with Vertical(id="menu-left"):
                yield Label("Target:", classes="form-label")
                yield Input(placeholder="email/phone/username/domain/IP", id="input-target")
                yield MenuList()

            with Vertical(id="menu-right"):
                table = DataTable(id="status-table")
                table.zebra_stripes = True
                table.cursor_type = "row"
                yield table

            yield LogStrip(id="log-strip")
        yield Static("Ready", id="status-bar")

    def on_mount(self) -> None:
        table = self.query_one("#status-table", DataTable)
        table.add_columns("Action", "Description", "Status")
        table.add_row("run", "Run OSINT pipeline", "ready")
        table.add_row("prelaunch", "Release gate", "ready")
        table.add_row("rehearsal", "Full canary rehearsal", "ready")
        table.add_row("status", "Show adapters and presets", "ready")
        table.add_row("textual_tui", "Launch Textual cockpit", "ready")
        table.add_row("prompt", "Prompt mode shell", "ready")
        table.add_row("nav_demo", "Logs/evidence navigator", "ready")
        table.add_row("shell", "Interactive CLI shell", "ready")
        table.add_row("exit", "Exit menu", "ready")

    def set_status(self, text: str) -> None:
        self.query_one("#status-bar", Static).update(text)

    def target_value(self) -> str:
        return self.query_one("#input-target", Input).value.strip()

    def menu(self) -> MenuList:
        return self.query_one("#main-menu", MenuList)
