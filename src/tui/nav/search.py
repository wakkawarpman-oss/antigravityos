from __future__ import annotations


def show_search_panes(contents: list[str], title: str = "Searchable Contents") -> None:
    """Render searchable list view for logs/evidence lines."""
    from prompt_toolkit.application import Application
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.layout import HSplit, Layout, Window
    from prompt_toolkit.layout.controls import FormattedTextControl
    from prompt_toolkit.widgets import SearchToolbar

    search_field = SearchToolbar(text="Search (Ctrl+S): ", ignore_case=True)

    def _filter_lines(query: str) -> list[str]:
        if not query.strip():
            return contents
        q = query.lower()
        return [line for line in contents if q in line.lower()]

    def _content_text() -> list[tuple[str, str]]:
        filtered = _filter_lines(search_field.text)
        fragments: list[tuple[str, str]] = [("class:header", f"{title}\n\n")]
        for line in filtered:
            fragments.append(("class:line", f"{line}\n"))
        return fragments

    kb = KeyBindings()

    @kb.add("escape")
    def _escape(event) -> None:
        event.app.exit()

    @kb.add("c-s")
    def _focus_search(event) -> None:
        event.app.layout.focus(search_field)

    app = Application(
        layout=Layout(
            HSplit(
                [
                    Window(content=FormattedTextControl(_content_text)),
                    Window(content=search_field, height=1),
                ]
            )
        ),
        key_bindings=kb,
        full_screen=True,
    )
    app.run()
