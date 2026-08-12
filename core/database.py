from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Iterable

SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
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
CREATE TABLE IF NOT EXISTS operation_journal (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id TEXT NOT NULL,
    sequence INTEGER NOT NULL,
    op_type TEXT NOT NULL,
    source TEXT NOT NULL,
    target TEXT,
    status TEXT NOT NULL DEFAULT 'planned',
    details TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(batch_id, sequence)
);
CREATE INDEX IF NOT EXISTS idx_operation_journal_batch ON operation_journal(batch_id, sequence);
CREATE INDEX IF NOT EXISTS idx_operation_journal_status ON operation_journal(status, id);
"""


class Database:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        with self._lock:
            self.conn.executescript(SCHEMA)

    def close(self) -> None:
        with self._lock:
            self.conn.close()

    def set_setting(self, key: str, value: object) -> None:
        with self._lock:
            self.conn.execute(
                "INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, json.dumps(value, ensure_ascii=False)),
            )
            self.conn.commit()

    def get_setting(self, key: str, default=None):
        with self._lock:
            row = self.conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        if not row:
            return default
        try:
            return json.loads(row["value"])
        except json.JSONDecodeError:
            return row["value"]

    def seed_knowledge(self, items: Iterable[dict]) -> None:
        with self._lock:
            for item in items:
                self.conn.execute(
                    """INSERT INTO knowledge(kind,name,payload) VALUES(?,?,?)
                       ON CONFLICT(kind,name) DO UPDATE SET payload=excluded.payload, updated_at=CURRENT_TIMESTAMP""",
                    (item["kind"], item["name"], json.dumps(item, ensure_ascii=False)),
                )
            self.conn.commit()

    def replace_scan(self, folders: list[dict], files: list[dict]) -> None:
        with self._lock, self.conn:
            self.conn.execute("DELETE FROM folder_snapshot")
            self.conn.execute("DELETE FROM file_snapshot")
            self.conn.executemany(
                "INSERT OR REPLACE INTO folder_snapshot(path,parent,name,depth) VALUES(:path,:parent,:name,:depth)", folders
            )
            self.conn.executemany(
                """INSERT OR REPLACE INTO file_snapshot
                   (path,parent,name,extension,size,modified,category,project_hint)
                   VALUES(:path,:parent,:name,:extension,:size,:modified,:category,:project_hint)""",
                files,
            )

    def snapshot_files(self) -> list[dict]:
        with self._lock:
            rows = self.conn.execute(
                "SELECT path,parent,name,extension,size,modified,category,project_hint FROM file_snapshot ORDER BY path"
            ).fetchall()
        return [dict(row) for row in rows]

    def snapshot_folders(self) -> list[dict]:
        with self._lock:
            rows = self.conn.execute("SELECT path,parent,name,depth FROM folder_snapshot ORDER BY depth,path").fetchall()
        return [dict(row) for row in rows]

    def log_action(self, action: str, target: str | None, result: str, details: str = "") -> None:
        with self._lock:
            self.conn.execute("INSERT INTO actions(action,target,result,details) VALUES(?,?,?,?)", (action, target, result, details))
            self.conn.commit()

    def latest_actions(self, limit: int = 20) -> list[dict]:
        with self._lock:
            rows = self.conn.execute(
                "SELECT action,target,result,details,created_at FROM actions ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(row) for row in rows]

    def add_operation_batch(self, rows: list[dict]) -> None:
        """Persist a planned batch without performing filesystem changes."""
        if not rows:
            return
        with self._lock, self.conn:
            self.conn.executemany(
                """INSERT INTO operation_journal
                   (batch_id,sequence,op_type,source,target,status,details)
                   VALUES(:batch_id,:sequence,:op_type,:source,:target,:status,:details)""",
                rows,
            )

    def operation_entries(self, batch_id: str | None = None, limit: int = 100) -> list[dict]:
        limit = max(1, min(int(limit), 5000))
        with self._lock:
            if batch_id:
                rows = self.conn.execute(
                    """SELECT id,batch_id,sequence,op_type,source,target,status,details,created_at,updated_at
                       FROM operation_journal WHERE batch_id=? ORDER BY sequence ASC LIMIT ?""",
                    (batch_id, limit),
                ).fetchall()
            else:
                rows = self.conn.execute(
                    """SELECT id,batch_id,sequence,op_type,source,target,status,details,created_at,updated_at
                       FROM operation_journal ORDER BY id DESC LIMIT ?""",
                    (limit,),
                ).fetchall()
        result: list[dict] = []
        for row in rows:
            item = dict(row)
            try:
                item["details"] = json.loads(item.get("details") or "{}")
            except json.JSONDecodeError:
                item["details"] = {"raw": item.get("details")}
            result.append(item)
        return result

    def set_operation_status(self, entry_id: int, status: str, details: dict | None = None) -> None:
        if status not in {"planned", "applied", "failed", "undone"}:
            raise ValueError(f"Unsupported operation status: {status}")
        payload = json.dumps(details or {}, ensure_ascii=False)
        with self._lock:
            cursor = self.conn.execute(
                """UPDATE operation_journal
                   SET status=?, details=?, updated_at=CURRENT_TIMESTAMP WHERE id=?""",
                (status, payload, int(entry_id)),
            )
            if cursor.rowcount != 1:
                self.conn.rollback()
                raise KeyError(f"Operation journal entry not found: {entry_id}")
            self.conn.commit()

    def counts(self) -> dict[str, int]:
        with self._lock:
            return {
                "folders": self.conn.execute("SELECT COUNT(*) FROM folder_snapshot").fetchone()[0],
                "files": self.conn.execute("SELECT COUNT(*) FROM file_snapshot").fetchone()[0],
                "knowledge": self.conn.execute("SELECT COUNT(*) FROM knowledge").fetchone()[0],
                "decisions": self.conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0],
            }


class KnowledgeDatabase:
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
        with self._db._lock:
            row = self._db.conn.execute(
                "SELECT payload FROM knowledge WHERE name=? ORDER BY id DESC LIMIT 1", (key,)
            ).fetchone()
        if not row:
            return None
        try:
            payload = json.loads(row["payload"])
            return payload.get("value", payload)
        except Exception:
            return row["payload"]
