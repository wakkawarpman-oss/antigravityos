import sqlite3
import json
import logging
from pathlib import Path
from typing import Any, Union, Optional, List, Dict, Tuple
from models.observables import Observable, IdentityCluster, TIER_CONFIRMED, TIER_PROBABLE, TIER_UNVERIFIED

log = logging.getLogger("hanna.repository")

class DiscoveryRepository:
    """Encapsulates all SQLite operations for the Discovery Engine."""

    def __init__(self, db_path: Union[str, Path]):
        self.db_path = str(db_path)
        self.db = sqlite3.connect(self.db_path)
        self.db.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self):
        self.db.execute("PRAGMA journal_mode = WAL")
        self.db.execute("PRAGMA busy_timeout = 5000")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS observables (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                obs_type    TEXT NOT NULL,
                value       TEXT NOT NULL,
                raw         TEXT,
                source_tool TEXT,
                source_target TEXT,
                source_file TEXT,
                depth       INTEGER DEFAULT 0,
                is_original_target INTEGER DEFAULT 0,
                corroboration_count INTEGER DEFAULT 1,
                tier        TEXT DEFAULT 'unverified',
                discovered_at TEXT DEFAULT (datetime('now')),
                raw_log_ref TEXT,
                UNIQUE(obs_type, value)
            );
            CREATE TABLE IF NOT EXISTS discovery_queue (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                obs_type    TEXT NOT NULL,
                value       TEXT NOT NULL,
                suggested_tools TEXT,
                reason      TEXT,
                priority    INTEGER DEFAULT 0,
                state       TEXT DEFAULT 'pending',
                depth       INTEGER DEFAULT 0,
                created_at  TEXT DEFAULT (datetime('now')),
                started_at  TEXT,
                finished_at TEXT,
                UNIQUE(obs_type, value)
            );
            CREATE TABLE IF NOT EXISTS entity_links (
                obs_a_type  TEXT NOT NULL,
                obs_a_value TEXT NOT NULL,
                obs_b_type  TEXT NOT NULL,
                obs_b_value TEXT NOT NULL,
                link_reason TEXT,
                confidence  REAL DEFAULT 0.5,
                PRIMARY KEY (obs_a_type, obs_a_value, obs_b_type, obs_b_value)
            );
            CREATE TABLE IF NOT EXISTS profile_urls (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                username    TEXT NOT NULL,
                platform    TEXT,
                url         TEXT NOT NULL,
                source_tool TEXT,
                status      TEXT DEFAULT 'unchecked',
                content_match INTEGER DEFAULT 0,
                checked_at  TEXT,
                valid_until TEXT,
                last_checked_at TEXT,
                raw_log_ref TEXT,
                UNIQUE(url)
            );
            CREATE TABLE IF NOT EXISTS rejected_targets (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                source_file TEXT,
                raw_target  TEXT,
                reason      TEXT,
                rejected_at TEXT DEFAULT (datetime('now'))
            );
        """)
        self.db.commit()

    def register_observable(
        self, obs_type: str, value: str, raw: str, source_tool: str,
        source_target: str, source_file: str, depth: int, is_original_target: bool,
        tier: str = TIER_UNVERIFIED
    ):
        """Register or update an observable with corroboration tracking."""
        self.db.execute(
            "INSERT INTO observables (obs_type, value, raw, source_tool, source_target, source_file, depth, is_original_target, tier) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(obs_type, value) DO UPDATE SET "
            "corroboration_count = corroboration_count + 1, "
            "tier = CASE WHEN excluded.is_original_target = 1 OR excluded.tier = 'confirmed' THEN 'confirmed' "
            "WHEN corroboration_count >= 2 THEN 'probable' ELSE tier END",
            (obs_type, value, raw, source_tool, source_target, source_file, depth, 1 if is_original_target else 0, tier),
        )
        self.db.commit()

    def update_observable_tier(self, obs_type: str, value: str, tier: str):
        self.db.execute(
            "UPDATE observables SET tier = ? WHERE obs_type = ? AND value = ?",
            (tier, obs_type, value),
        )
        self.db.commit()

    def update_corroboration(self, obs_type: str, value: str, source_tool: str):
        self.db.execute(
            "UPDATE observables SET corroboration_count = corroboration_count + 1, "
            "tier = CASE WHEN corroboration_count >= 2 THEN 'probable' ELSE tier END "
            "WHERE obs_type = ? AND value = ? AND source_tool != ?",
            (obs_type, value, source_tool),
        )
        self.db.commit()

    def record_rejected_target(self, source_file: str, raw_target: str, reason: str):
        self.db.execute(
            "INSERT OR IGNORE INTO rejected_targets (source_file, raw_target, reason) VALUES (?, ?, ?)",
            (source_file, raw_target, reason),
        )
        self.db.commit()

    def add_profile_url(self, username: str, platform: str, url: str, source_tool: str):
        self.db.execute(
            "INSERT OR IGNORE INTO profile_urls (username, platform, url, source_tool) VALUES (?, ?, ?, ?)",
            (username, platform, url, source_tool),
        )
        self.db.commit()

    def enqueue_discovery(self, obs_type: str, value: str, suggested_tools: list[str], reason: str, depth: int):
        self.db.execute(
            "INSERT OR IGNORE INTO discovery_queue (obs_type, value, suggested_tools, reason, depth) VALUES (?, ?, ?, ?, ?)",
            (obs_type, value, json.dumps(suggested_tools), reason, depth),
        )
        self.db.commit()

    def get_entity_links(self) -> List[Tuple[str, str, str, str, float]]:
        links = self.db.execute("SELECT obs_a_type, obs_a_value, obs_b_type, obs_b_value, confidence FROM entity_links").fetchall()
        return [tuple(link) for link in links]

    def get_profile_urls_for_username(self, username: str) -> List[str]:
        urls = self.db.execute("SELECT url FROM profile_urls WHERE username = ?", (username,)).fetchall()
        return [url["url"] for url in urls]

    def link_observables(self, key_a: tuple[str, str], key_b: tuple[str, str], reason: str, confidence: float):
        if key_a > key_b:
            key_a, key_b = key_b, key_a
        self.db.execute(
            "INSERT OR REPLACE INTO entity_links (obs_a_type, obs_a_value, obs_b_type, obs_b_value, link_reason, confidence) "
            "VALUES (?, ?, ?, ?, ?, max(?, coalesce((SELECT confidence FROM entity_links WHERE obs_a_type=? AND obs_a_value=? AND obs_b_type=? AND obs_b_value=?), 0)))",
            (*key_a, *key_b, reason, confidence, *key_a, *key_b),
        )
        self.db.commit()





    def get_stats(self) -> Dict[str, int]:
        return {
            "observables": self.db.execute("SELECT COUNT(*) FROM observables").fetchone()[0],
            "rejected_targets": self.db.execute("SELECT COUNT(*) FROM rejected_targets").fetchone()[0],
            "entity_links": self.db.execute("SELECT COUNT(*) FROM entity_links").fetchone()[0],
            "profile_urls": self.db.execute("SELECT COUNT(*) FROM profile_urls").fetchone()[0],
            "pending_queue": self.db.execute("SELECT COUNT(*) FROM discovery_queue WHERE state='pending'").fetchone()[0],
        }

    def get_rejected_targets(self, limit: int = 20) -> List[Tuple[str, str, str]]:
        rejected = self.db.execute("SELECT raw_target, reason, source_file FROM rejected_targets LIMIT ?", (limit,)).fetchall()
        return [tuple(r) for r in rejected]

    def get_all_observables(self) -> List[Observable]:
        """Fetch all observables as a list of rich objects."""
        obs_rows = self.db.execute(
            "SELECT obs_type, value, raw, source_tool, source_target, source_file, depth, is_original_target, tier "
            "FROM observables"
        ).fetchall()
        return [
            Observable(
                obs_type=obs["obs_type"],
                value=obs["value"],
                raw=obs["raw"] or "",
                source_tool=obs["source_tool"],
                source_target=obs["source_target"],
                source_file=obs["source_file"],
                depth=obs["depth"],
                is_original_target=bool(obs["is_original_target"]),
                tier=obs["tier"],
            )
            for obs in obs_rows
        ]

    def get_discovery_queue(self) -> List[Dict[str, Any]]:
        """Fetch all pending tasks in the discovery queue."""
        queue_rows = self.db.execute(
            "SELECT obs_type, value, suggested_tools, reason, depth, state FROM discovery_queue"
        ).fetchall()
        return [dict(q) for q in queue_rows]

    def get_edges(self) -> List[Tuple[str, str, str, str, float, str]]:
        edge_rows = self.db.execute("SELECT obs_a_type, obs_a_value, obs_b_type, obs_b_value, confidence, link_reason FROM entity_links").fetchall()
        return [tuple(e) for e in edge_rows]

    def get_profile_status(self, url: str) -> Optional[str]:
        status_row = self.db.execute("SELECT status FROM profile_urls WHERE url = ?", (url,)).fetchone()
        return status_row["status"] if status_row else None

    def update_profile_status(self, url_id: int, status: str, content_match: int = 0):
        self.db.execute(
            "UPDATE profile_urls SET status = ?, content_match = ?, checked_at = datetime('now') WHERE id = ?",
            (status, content_match, url_id),
        )
        self.db.commit()

    def get_database_path(self) -> Optional[str]:
        db_list_row = self.db.execute("PRAGMA database_list").fetchone()
        return db_list_row[2] if db_list_row else None

    def close(self):
        if self.db:
            self.db.close()
