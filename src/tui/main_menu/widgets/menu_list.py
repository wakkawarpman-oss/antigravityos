from __future__ import annotations

from typing import Iterable

from textual.widgets import Label, ListItem, ListView


CHOICES: list[tuple[str, str]] = [
    ("run", "Run OSINT pipeline"),
    ("prelaunch", "Release gate (prelaunch)"),
    ("rehearsal", "Full canary rehearsal"),
    ("status", "Status/info"),
    ("textual_tui", "Launch main Textual TUI"),
    ("prompt", "Prompt mode"),
    ("nav_demo", "Nav demo (logs/evidence search)"),
    ("shell", "Interactive CLI shell"),
    ("exit", "Exit"),
]


class MenuList(ListView):
    """Keyboard-friendly list of available HANNA menu actions."""

    def __init__(self, entries: Iterable[tuple[str, str]] | None = None) -> None:
        self.entries = list(entries or CHOICES)
        items = [
            ListItem(
                Label(f"{index + 1}. {label}", classes="menu-label"),
                Label(key, classes="-meta"),
                classes="menu-item",
            )
            for index, (key, label) in enumerate(self.entries)
        ]
        super().__init__(*items, id="main-menu")
        self._index = 0

    def on_mount(self) -> None:
        self._sync_selection()

    def move(self, delta: int) -> None:
        if not self.entries:
            return
        self._index = max(0, min(len(self.entries) - 1, self._index + delta))
        self._sync_selection()

    def jump_to(self, index: int) -> None:
        if not self.entries:
            return
        self._index = max(0, min(len(self.entries) - 1, index))
        self._sync_selection()

    def current_choice(self) -> str:
        if not self.entries:
            return "exit"
        return self.entries[self._index][0]

    def current_label(self) -> str:
        if not self.entries:
            return "Exit"
        return self.entries[self._index][1]

    def _sync_selection(self) -> None:
        for index, item in enumerate(self.query(ListItem)):
            if index == self._index:
                item.add_class("-highlighted")
            else:
                item.remove_class("-highlighted")
