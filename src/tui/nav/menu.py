from __future__ import annotations

from typing import Optional


def show_menu(choices: list[tuple[str, str]], title: str = "Menu", header: str = "Use Up/Down + Enter, Esc") -> Optional[str]:
    """Render a full-screen menu and return selected key or None."""
    from prompt_toolkit.application import Application
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.layout import HSplit, Layout, Window
    from prompt_toolkit.layout.controls import FormattedTextControl
    from prompt_toolkit.styles import Style

    if not choices:
        return None

    kb = KeyBindings()
    selected = 0

    @kb.add("down")
    def _down(event) -> None:
        nonlocal selected
        selected = (selected + 1) % len(choices)
        event.app.invalidate()

    @kb.add("up")
    def _up(event) -> None:
        nonlocal selected
        selected = (selected - 1) % len(choices)
        event.app.invalidate()

    @kb.add("enter")
    def _enter(event) -> None:
        event.app.exit(result=choices[selected][0])

    @kb.add("escape")
    def _escape(event) -> None:
        event.app.exit(result=None)

    def _menu_text() -> list[tuple[str, str]]:
        text: list[tuple[str, str]] = [
            ("class:header", f"{title}\n"),
            ("class:subtitle", f"{header}\n\n"),
        ]
        for idx, (_key, desc) in enumerate(choices):
            if idx == selected:
                text.append(("class:choice.selected", f" > {desc}\n"))
            else:
                text.append(("class:choice", f"   {desc}\n"))
        return text

    app = Application(
        layout=Layout(HSplit([Window(content=FormattedTextControl(_menu_text))])),
        key_bindings=kb,
        style=Style.from_dict(
            {
                "header": "bold #8888fd",
                "subtitle": "#aaaaaa",
                "choice": "#888888",
                "choice.selected": "bg:#008888 #ffffff bold",
            }
        ),
        full_screen=True,
    )
    return app.run()
