from __future__ import annotations

import time
from pathlib import Path

from dossier.core import DossierEngine

try:
    from textual import on
    from textual.app import App, ComposeResult
    from textual.containers import Horizontal, Vertical
    from textual.widgets import Button, Collapsible, Input, Label, RichLog, Static
except Exception as exc:  # pragma: no cover - optional dependency
    raise RuntimeError("Textual is required to run dossier TUI") from exc


_CYCLES = ("surface", "deep", "pivot")


class StepStatus(Static):
    def __init__(self, cycle: str, tool: str):
        super().__init__("[ ]")
        self.cycle = cycle
        self.tool = tool

    def set_status(self, status: str) -> None:
        if status == "ok":
            self.update("[OK]")
            self.styles.color = "green"
        elif status == "warn":
            self.update("[WARN]")
            self.styles.color = "yellow"
        elif status == "error":
            self.update("[FAIL]")
            self.styles.color = "red"
        elif status == "running":
            self.update("[RUN]")
            self.styles.color = "cyan"
        else:
            self.update("[ ]")
            self.styles.color = "white"


class ActivityStream(Static):
    def __init__(self, engine: DossierEngine):
        super().__init__()
        self.engine = engine
        self.step_widgets: dict[tuple[str, str], StepStatus] = {}

    def compose(self) -> ComposeResult:
        yield Label("Activity Stream (surface/deep/pivot)")
        for cycle in _CYCLES:
            tools = self.engine._split_to_layers(
                target=type("_T", (), {"type_hint": "unknown"})(),
            )[cycle]
            with Horizontal():
                yield Label(f"{cycle.upper()}: ")
                for tool in tools:
                    step = StepStatus(cycle, tool)
                    self.step_widgets[(cycle, tool)] = step
                    yield Label(f"{tool}")
                    yield step

    def reset(self) -> None:
        for widget in self.step_widgets.values():
            widget.set_status("idle")

    def mark_cycle_running(self, cycle: str) -> None:
        for (c_name, _tool), widget in self.step_widgets.items():
            if c_name == cycle:
                widget.set_status("running")

    def mark_from_run(self, dossier) -> None:
        for evidence in dossier.evidences:
            source = evidence.source.replace("hanna::", "")
            status = "error" if evidence.field == "error" else "ok"
            key = (evidence.layer, source)
            widget = self.step_widgets.get(key)
            if widget:
                widget.set_status(status)


class DossierTUI(App):
    CSS = """
    Screen { layout: vertical; }
    .log { height: 1fr; }
    """

    def __init__(self):
        super().__init__()
        self.engine = DossierEngine()
        self.dossier = None
        self.normalized = None
        self.activity_stream = ActivityStream(self.engine)

    def compose(self) -> ComposeResult:
        yield Vertical(
            Label("ONE-SHOT-Dossier TUI"),
            Horizontal(
                Input(placeholder="Enter target", id="target"),
                Button("Generate dossier", id="generate"),
                Button("Exit", id="exit"),
            ),
            Collapsible(self.activity_stream, title="Activity Stream"),
            RichLog(id="log", wrap=True, classes="log"),
            Horizontal(
                Button("Show DOSSIER", id="show"),
                Button("Export Text", id="export_text"),
                Button("Export JSON", id="export_json"),
            ),
        )

    @on(Button.Pressed, "#generate")
    def on_generate(self) -> None:
        target = self.query_one("#target", Input).value.strip()
        log = self.query_one("#log", RichLog)
        if not target:
            log.write("Enter a valid target.")
            return

        self.activity_stream.reset()
        log.write(f"Running one-shot dossier for {target}...")

        try:
            full_run = self.engine.run_one_shot_full(target)
            self.dossier = full_run.dossier
            self.normalized = full_run.normalized
            self.activity_stream.mark_from_run(self.dossier)
            log.write("Dossier created.")
        except Exception as exc:
            log.write(f"Error: {exc}")

    @on(Button.Pressed, "#show")
    def on_show(self) -> None:
        log = self.query_one("#log", RichLog)
        if not self.dossier or not self.normalized:
            log.write("No dossier yet.")
            return
        log.write(f"DOSSIER for {self.dossier.target.value}")
        for key, values in self.normalized.items():
            if values:
                log.write(f"{key}: {len(values)}")

    def _do_export(self, fmt: str) -> None:
        log = self.query_one("#log", RichLog)
        if not self.dossier or self.normalized is None:
            log.write("No dossier to export.")
            return

        now = str(int(time.time()))
        path = Path.cwd() / f"dossier_{now}_{fmt}"
        try:
            self.engine.export_dossier(self.dossier, self.normalized, fmt, path)
            log.write(f"Saved dossier to {path}")
        except Exception as exc:
            log.write(f"Export failed: {exc}")

    @on(Button.Pressed, "#export_text")
    def on_export_text(self) -> None:
        self._do_export("text")

    @on(Button.Pressed, "#export_json")
    def on_export_json(self) -> None:
        self._do_export("json")

    @on(Button.Pressed, "#exit")
    def on_exit(self) -> None:
        self.exit()


def run_tui_dossier_app() -> None:
    DossierTUI().run()


if __name__ == "__main__":
    run_tui_dossier_app()
