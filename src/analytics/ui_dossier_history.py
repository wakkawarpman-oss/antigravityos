from __future__ import annotations

from analytics.dossier_store import DossierSessionStore

try:
    from textual.app import App, ComposeResult
    from textual.widgets import DataTable, Label
except Exception as exc:  # pragma: no cover
    raise RuntimeError("Textual is required to run dossier history UI") from exc


class DossierHistoryApp(App):
    CSS = """
    DataTable { height: 1fr; }
    """

    def __init__(self, db_path: str = ".hanna/dossier_sessions.sqlite"):
        super().__init__()
        self.store = DossierSessionStore(db_path=db_path)

    def compose(self) -> ComposeResult:
        yield Label("Dossier Session History")
        table = DataTable(id="history")
        table.add_columns("ID", "Created", "Target", "Type", "Source", "Tags")
        for item in self.store.query_sessions(limit=200):
            table.add_row(
                str(item["id"]),
                item["created_at"],
                item["target"],
                item["target_type"] or "",
                item["source_type"] or "",
                ",".join(item["tags"]),
            )
        yield table


def main() -> None:
    DossierHistoryApp().run()


if __name__ == "__main__":
    main()
