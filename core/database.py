from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Iterable

SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS knowledge (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,
    name TEXT NOT NULL,
    payload TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(kind, name)
);
CREATE TABLE IF NOT EXISTS folder_snapshot (
    path TEXT PRIMARY KEY,
    parent TEXT,
    name TEXT NOT NULL,
    depth INTEGER NOT NULL,
    scanned_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS file_snapshot (
    path TEXT PRIMARY KEY,
    parent TEXT NOT NULL,
    name TEXT NOT NULL,
    extension TEXT,
    size INTEGER NOT NULL,
    modified REAL NOT NULL,
    category TEXT,
    project_hint TEXT,
    scanned_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_path TEXT,
    decision TEXT NOT NULL,
    reason TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action TEXT NOT NULL,
    target TEXT,
    result TEXT NOT NULL,
    details TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


class Database:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)

    def close(self) -> None:
        self.conn.close()

    def set_setting(self, key: str, value: object) -> None:
        self.conn.execute(
            "INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, json.dumps(value, ensure_ascii=False)),
        )
        self.conn.commit()

    def get_setting(self, key: str, default=None):
        row = self.conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        if not row:
            return default
        try:
            return json.loads(row["value"])
        except json.JSONDecodeError:
            return row["value"]

    def seed_knowledge(self, items: Iterable[dict]) -> None:
        for item in items:
            self.conn.execute(
                """INSERT INTO knowledge(kind,name,payload) VALUES(?,?,?)
                   ON CONFLICT(kind,name) DO UPDATE SET payload=excluded.payload, updated_at=CURRENT_TIMESTAMP""",
                (item["kind"], item["name"], json.dumps(item, ensure_ascii=False)),
            )
        self.conn.commit()

    def replace_scan(self, folders: list[dict], files: list[dict]) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM folder_snapshot")
            self.conn.execute("DELETE FROM file_snapshot")
            self.conn.executemany(
                "INSERT OR REPLACE INTO folder_snapshot(path,parent,name,depth) VALUES(:path,:parent,:name,:depth)",
                folders,
            )
            self.conn.executemany(
                """INSERT OR REPLACE INTO file_snapshot
                   (path,parent,name,extension,size,modified,category,project_hint)
                   VALUES(:path,:parent,:name,:extension,:size,:modified,:category,:project_hint)""",
                files,
            )

    def log_action(self, action: str, target: str | None, result: str, details: str = "") -> None:
        self.conn.execute(
            "INSERT INTO actions(action,target,result,details) VALUES(?,?,?,?)",
            (action, target, result, details),
        )
        self.conn.commit()

    def counts(self) -> dict[str, int]:
        return {
            "folders": self.conn.execute("SELECT COUNT(*) FROM folder_snapshot").fetchone()[0],
            "files": self.conn.execute("SELECT COUNT(*) FROM file_snapshot").fetchone()[0],
            "knowledge": self.conn.execute("SELECT COUNT(*) FROM knowledge").fetchone()[0],
            "decisions": self.conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0],
        }


class KnowledgeDatabase:
    """Compatibility wrapper for the repository's original knowledge API."""

    def __init__(self, root="D:/Smart-Organizer/data"):
        root_path = Path(root)
        self.root = root_path
        self.path = root_path / "knowledge.db"
        self._db: Database | None = None

    def initialize(self):
        self._db = Database(self.path)

    def save(self, key, value, category="general"):
        if self._db is None:
            self.initialize()
        assert self._db is not None
        self._db.seed_knowledge([{"kind": category, "name": key, "value": value}])

    def get(self, key):
        if self._db is None:
            self.initialize()
        assert self._db is not None
        row = self._db.conn.execute("SELECT payload FROM knowledge WHERE name=? ORDER BY id DESC LIMIT 1", (key,)).fetchone()
        if not row:
            return None
        try:
            payload = json.loads(row["payload"])
            return payload.get("value", payload)
        except Exception:
            return row["payload"]
