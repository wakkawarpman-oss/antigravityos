from __future__ import annotations

from typing import Callable


class KeyBindingsHelper:
    """Helper to display a keybindings help palette."""

    def __init__(self, kb_map: dict[str, tuple[str, Callable | None]]):
        self.kb_map = kb_map

    def show(self, title: str = "Help Palette") -> None:
        from prompt_toolkit.application import Application
        from prompt_toolkit.key_binding import KeyBindings
        from prompt_toolkit.layout import HSplit, Layout, Window
        from prompt_toolkit.layout.controls import FormattedTextControl
        from prompt_toolkit.styles import Style

        rows: list[tuple[str, str]] = [
            ("class:title", f"{title}\n\n"),
        ]
        for key, (desc, _handler) in self.kb_map.items():
            rows.append(("class:key", f" {key:<10} "))
            rows.append(("class:desc", f"{desc}\n"))

        kb = KeyBindings()

        @kb.add("q")
        @kb.add("escape")
        def _exit(event) -> None:
            event.app.exit()

        app = Application(
            layout=Layout(HSplit([Window(content=FormattedTextControl(rows))])),
            key_bindings=kb,
            style=Style.from_dict(
                {
                    "title": "bold #8888fd",
                    "key": "bold #ffffff",
                    "desc": "#aaaaaa",
                }
            ),
            full_screen=True,
        )
        app.run()


def show_help(kb_map: dict[str, tuple[str, Callable | None]], title: str = "Help Palette") -> None:
    """Convenience wrapper for one-shot key help display."""
    KeyBindingsHelper(kb_map).show(title=title)
