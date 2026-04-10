from __future__ import annotations

from pathlib import Path

from textual.widgets import Static


def _latest_prelaunch_bundle() -> Path | None:
    root = Path(__file__).resolve().parents[3] / ".cache" / "prelaunch"
    if not root.exists():
        return None
    dirs = [p for p in root.iterdir() if p.is_dir()]
    if not dirs:
        return None
    return max(dirs, key=lambda p: p.stat().st_mtime)


def _tail_lines(path: Path, count: int) -> list[str]:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return []
    return lines[-count:]


class LogStrip(Static):
    """Wide and low-height log preview showing 5-6 latest lines."""

    def on_mount(self) -> None:
        self.refresh_preview()

    def refresh_preview(self) -> None:
        bundle = _latest_prelaunch_bundle()
        if bundle is None:
            self.update("[logs] no prelaunch bundle found")
            return

        files = [
            bundle / "pytest.err",
            bundle / "full-rehearsal.err",
            bundle / "gate-result.json",
            bundle / "final-summary.json",
        ]
        rows: list[str] = []
        for path in files:
            if not path.exists():
                continue
            for line in _tail_lines(path, 2):
                rows.append(f"[{path.name}] {line}")
            if len(rows) >= 6:
                break

        if not rows:
            rows = [f"[logs] bundle: {bundle.name}", "[logs] files are empty"]

        self.update("\n".join(rows[:6]))
