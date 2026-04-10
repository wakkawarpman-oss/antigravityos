from __future__ import annotations

try:
    from textual.app import App, ComposeResult
    from textual.widgets import Static
except Exception as exc:  # pragma: no cover - optional dependency
    raise RuntimeError("Textual is required to run dossier boot screen") from exc


CYBERPUNK_ASCII = """
 █████╗ ███████╗ ██████╗  ██████╗  ██████╗  ██╗   ██╗
██╔══██╗╚══███╔╝██╔════╝ ██╔═══██╗██╔═══██╗██║   ██║
███████║  ███╔╝ ██║      ██║   ██║██║   ██║██║   ██║
██╔══██║ ███╔╝  ██║      ██║   ██║██║   ██║╚██╗ ██╔╝
██║  ██║███████╗╚██████╗ ╚██████╔╝╚██████╔╝ ╚████╔╝
╚═╝  ╚═╝╚══════╝ ╚═════╝  ╚═════╝  ╚═════╝   ╚═══╝

    H A N N A   |   ONE-SHOT-DOSSIER
            CYBERPUNK BOOT SEQUENCE
"""


class CyberPunkBootScreen(App[dict]):
    """Cyberpunk splash screen shown before opening the main menu."""

    CSS = """
    Screen { layout: vertical; background: black; color: #00ff99; }
    #ascii { height: 1fr; text-align: center; padding: 1; color: #00e5ff; }
    #status { height: 3; text-align: center; color: #ff5cff; }
    """

    def compose(self) -> ComposeResult:
        yield Static(CYBERPUNK_ASCII, id="ascii")
        yield Static("Initializing ONE-SHOT-Dossier engine...", id="status")

    def on_mount(self) -> None:
        self.run_worker(self._worker_bootstrap(), exclusive=True)

    async def _worker_bootstrap(self):
        status = self.query_one("#status", Static)
        phases = [
            "LOADING hanna.dossier.core...",
            "INITIALIZING dossier engine...",
            "WARMING UP AI-assisted probes...",
            "SYNCING STIX schemas...",
            "BUILDING integration matrix...",
            "READY FOR ONE-SHOT-DOSSIER.",
        ]
        for line in phases:
            status.update(line)
            await self.sleep(0.35)
        self.exit({"booted": True})


def show_boot_screen() -> bool:
    result = CyberPunkBootScreen().run()
    return bool(isinstance(result, dict) and result.get("booted"))
