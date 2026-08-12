import sqlite3
from pathlib import Path


class KnowledgeDatabase:
    def __init__(self, root="D:/Smart-Organizer/data"):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "knowledge.db"

    def initialize(self):
        with sqlite3.connect(self.path) as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS knowledge (
                    id INTEGER PRIMARY KEY,
                    key TEXT UNIQUE,
                    value TEXT,
                    category TEXT
                )
            """)
            db.commit()

    def save(self, key, value, category="general"):
        with sqlite3.connect(self.path) as db:
            db.execute(
                "INSERT OR REPLACE INTO knowledge(key,value,category) VALUES(?,?,?)",
                (key, value, category)
            )
            db.commit()

    def get(self, key):
        with sqlite3.connect(self.path) as db:
            row = db.execute(
                "SELECT value FROM knowledge WHERE key=?",
                (key,)
            ).fetchone()
            return row[0] if row else None
