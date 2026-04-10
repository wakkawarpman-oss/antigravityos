from __future__ import annotations


def show_panes(panes: dict[str, tuple[str, list[str]]], title: str = "Panes", header_keys: str = "Left/Right, Esc") -> None:
    """Render tab-like panes and navigate between them."""
    from prompt_toolkit.application import Application
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.layout import HSplit, Layout, Window
    from prompt_toolkit.layout.controls import FormattedTextControl
    from prompt_toolkit.styles import Style

    if not panes:
        return

    keys = list(panes.keys())
    active_index = 0

    kb = KeyBindings()

    @kb.add("left")
    def _left(event) -> None:
        nonlocal active_index
        active_index = (active_index - 1) % len(keys)
        event.app.invalidate()

    @kb.add("right")
    def _right(event) -> None:
        nonlocal active_index
        active_index = (active_index + 1) % len(keys)
        event.app.invalidate()

    @kb.add("escape")
    def _escape(event) -> None:
        event.app.exit()

    def _tab_line() -> list[tuple[str, str]]:
        fragments: list[tuple[str, str]] = [("class:header", f"{title} ({header_keys})\n")]
        for idx, key in enumerate(keys):
            name = panes[key][0]
            if idx == active_index:
                fragments.append(("class:tab.active", f" {name} "))
            else:
                fragments.append(("class:tab.inactive", f" {name} "))
        return fragments

    def _pane_text() -> list[tuple[str, str]]:
        pane_key = keys[active_index]
        pane_name, lines = panes[pane_key]
        text: list[tuple[str, str]] = [
            ("class:pane.title", f"\n{pane_name}\n\n"),
        ]
        for line in lines:
            text.append(("class:pane.item", f"{line}\n"))
        return text

    app = Application(
        layout=Layout(
            HSplit(
                [
                    Window(content=FormattedTextControl(_tab_line), height=1),
                    Window(content=FormattedTextControl(_pane_text)),
                ]
            )
        ),
        key_bindings=kb,
        style=Style.from_dict(
            {
                "header": "bold #8888fd",
                "tab.active": "bg:#008888 #ffffff bold",
                "tab.inactive": "bg:#444444 #888888",
                "pane.title": "bold #b1b1b1",
                "pane.item": "#ffffff",
            }
        ),
        full_screen=True,
    )
    app.run()
