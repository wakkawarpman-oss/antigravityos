from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from textual.app import App

from tui.main_menu.screens.help import HelpScreen
from tui.main_menu.screens.main_menu import MainMenuScreen


@dataclass
class MenuSelection:
    choice: str
    target: str = ""


class HannaMainMenuApp(App[MenuSelection]):
    CSS_PATH = str(Path(__file__).resolve().parents[1] / "styles.tcss")
    BINDINGS = [
        ("up", "move_up", "Up"),
        ("down", "move_down", "Down"),
        ("k", "move_up", "Up"),
        ("j", "move_down", "Down"),
        ("enter", "submit", "Run"),
        ("h", "help", "Help"),
        ("question_mark", "help", "Help"),
        ("escape", "quit_menu", "Exit"),
        ("1", "jump_1", "1"),
        ("2", "jump_2", "2"),
        ("3", "jump_3", "3"),
        ("4", "jump_4", "4"),
        ("5", "jump_5", "5"),
        ("6", "jump_6", "6"),
        ("7", "jump_7", "7"),
        ("8", "jump_8", "8"),
        ("9", "jump_9", "9"),
    ]

    def on_mount(self) -> None:
        self._main = MainMenuScreen()
        self.push_screen(self._main)
        self.call_after_refresh(self._focus_menu)

    def _focus_menu(self) -> None:
        if getattr(self, "_main", None) is None:
            return
        try:
            self._main.menu().focus()
        except Exception:
            # Screen may already be closing; ignore best-effort focus.
            return

    def action_move_up(self) -> None:
        self._main.menu().move(-1)
        self._main.set_status(f"Selected: {self._main.menu().current_label()}")

    def action_move_down(self) -> None:
        self._main.menu().move(1)
        self._main.set_status(f"Selected: {self._main.menu().current_label()}")

    def action_help(self) -> None:
        self.push_screen(HelpScreen())

    def action_submit(self) -> None:
        choice = self._main.menu().current_choice()
        target = self._main.target_value() if choice == "run" else ""
        self.exit(MenuSelection(choice=choice, target=target))

    def action_quit_menu(self) -> None:
        self.exit(MenuSelection(choice="exit"))

    def action_jump_1(self) -> None:
        self._jump_to(0)

    def action_jump_2(self) -> None:
        self._jump_to(1)

    def action_jump_3(self) -> None:
        self._jump_to(2)

    def action_jump_4(self) -> None:
        self._jump_to(3)

    def action_jump_5(self) -> None:
        self._jump_to(4)

    def action_jump_6(self) -> None:
        self._jump_to(5)

    def action_jump_7(self) -> None:
        self._jump_to(6)

    def action_jump_8(self) -> None:
        self._jump_to(7)

    def action_jump_9(self) -> None:
        self._jump_to(8)

    def _jump_to(self, index: int) -> None:
        self._main.menu().jump_to(index)
        self._main.set_status(f"Selected: {self._main.menu().current_label()}")


def run_main_menu() -> MenuSelection:
    result = HannaMainMenuApp().run()
    return result or MenuSelection(choice="exit")
