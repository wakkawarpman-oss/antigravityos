"""
tui.history — SQLite-backed command history for the HANNA terminal.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List

from config import RUNS_ROOT


class CommandHistory:
    """Manages persistent TUI command history."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or (RUNS_ROOT / "tui_history.db")
        self._init_db()

    def _init_db(self) -> None:
        """Create the history table if it doesn't exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS history ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "command TEXT NOT NULL, "
                "timestamp DATETIME DEFAULT CURRENT_TIMESTAMP"
                ")"
            )

    def append(self, command: str) -> None:
        """Save a command to the history."""
        if not command.strip():
            return
        with sqlite3.connect(self.db_path) as conn:
            # Avoid duplicate consecutive entries
            res = conn.execute("SELECT command FROM history ORDER BY id DESC LIMIT 1").fetchone()
            if res and res[0] == command:
                return
            conn.execute("INSERT INTO history (command) VALUES (?)", (command,))

    def get_all(self, limit: int = 100) -> List[str]:
        """Retrieve the most recent commands."""
        with sqlite3.connect(self.db_path) as conn:
            res = conn.execute(
                "SELECT command FROM history ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
            # Return in chronological order for the TUI buffer
            return [row[0] for row in reversed(res)]

    def search(self, query: str, limit: int = 50) -> List[str]:
        """Search history for a command snippet (Ctrl+R bridge)."""
        with sqlite3.connect(self.db_path) as conn:
            res = conn.execute(
                "SELECT DISTINCT command FROM history "
                "WHERE command LIKE ? ORDER BY id DESC LIMIT ?",
                (f"%{query}%", limit)
            ).fetchall()
            return [row[0] for row in res]
