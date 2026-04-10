from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from dossier.core import Dossier


class DossierSessionStore:
    """Store dossier sessions in SQLite and JSON sidecar files."""

    DEFAULT_DB = ".hanna/dossier_sessions.sqlite"
    DEFAULT_JSON_DIR = ".hanna/sessions"

    def __init__(self, db_path: str | None = None, json_dir: str | None = None):
        self.db_path = Path(db_path or self.DEFAULT_DB)
        self.json_dir = Path(json_dir or self.DEFAULT_JSON_DIR)

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.json_dir.mkdir(parents=True, exist_ok=True)

        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._setup_tables()

    def _setup_tables(self) -> None:
        cur = self.conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS dossier_sessions (
                id INTEGER PRIMARY KEY,
                created_at TEXT NOT NULL,
                target_value TEXT NOT NULL,
                target_type TEXT,
                source_type TEXT,
                json_path TEXT NOT NULL,
                tags TEXT DEFAULT ''
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS dossier_evidences (
                id INTEGER PRIMARY KEY,
                session_id INTEGER NOT NULL,
                source TEXT,
                field TEXT,
                value TEXT,
                confidence REAL,
                score REAL,
                FOREIGN KEY(session_id) REFERENCES dossier_sessions(id)
            )
            """
        )
        self.conn.commit()

    def _save_json(self, dossier_data: dict[str, Any], target: str, ext: str = "json") -> str:
        safe_target = "".join(ch if ch.isalnum() else "_" for ch in target)[:80] or "target"
        now = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_name = f"{now}_{safe_target}.{ext}"
        path = self.json_dir / file_name
        path.write_text(json.dumps(dossier_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return str(path)

    def create_session(
        self,
        dossier: Dossier,
        normalized: dict[str, Any],
        source_type: str = "unknown",
        tags: Optional[list[str]] = None,
    ) -> int:
        cur = self.conn.cursor()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        dossier_dict = asdict(dossier)
        dossier_dict["normalized"] = normalized
        json_path = self._save_json(dossier_dict, dossier.target.value)
        tags_str = ",".join(tags or [])

        cur.execute(
            """
            INSERT INTO dossier_sessions (created_at, target_value, target_type, source_type, json_path, tags)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (now, dossier.target.value, dossier.target.type_hint, source_type, json_path, tags_str),
        )
        session_id = int(cur.lastrowid)

        for ev in dossier.evidences:
            cur.execute(
                """
                INSERT INTO dossier_evidences (session_id, source, field, value, confidence, score)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (session_id, ev.source, ev.field, str(ev.value), ev.confidence, ev.score),
            )

        self.conn.commit()
        return session_id

    def query_sessions(self, limit: int = 50) -> list[dict[str, Any]]:
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT id, created_at, target_value, target_type, source_type, json_path, tags
            FROM dossier_sessions
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = cur.fetchall()
        return [
            {
                "id": row[0],
                "created_at": row[1],
                "target": row[2],
                "target_type": row[3],
                "source_type": row[4],
                "json_path": row[5],
                "tags": [item for item in (row[6] or "").split(",") if item.strip()],
            }
            for row in rows
        ]

    def query_evidences_by_session(self, session_id: int, limit: int = 1000) -> list[dict[str, Any]]:
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT source, field, value, confidence, score
            FROM dossier_evidences
            WHERE session_id = ?
            LIMIT ?
            """,
            (session_id, limit),
        )
        rows = cur.fetchall()
        return [
            {
                "source": row[0],
                "field": row[1],
                "value": row[2],
                "confidence": row[3],
                "score": row[4],
            }
            for row in rows
        ]

    def get_full_session(self, session_id: int) -> Optional[dict[str, Any]]:
        sessions = self.query_sessions(limit=10000)
        session = next((item for item in sessions if item["id"] == session_id), None)
        if not session:
            return None
        return {
            "session": session,
            "evidences": self.query_evidences_by_session(session_id),
        }
