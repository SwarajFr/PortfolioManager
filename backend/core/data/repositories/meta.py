"""Key/value notes about the cache itself: when it was last refreshed, whether
the initial seed finished, when each exchange's instrument dump was pulled.

Same `meta` table (and same `last_updated` / `seed_complete` keys) the screener
wrote before the data layer was extracted, so existing values carry over.
"""
from __future__ import annotations

from .db import connect


class MetaRepository:
    def __init__(self, db_path: str):
        self._db = db_path
        self.init()

    def init(self) -> None:
        with connect(self._db) as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)"
            )

    def get(self, key: str) -> str | None:
        with connect(self._db) as conn:
            row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return row[0] if row else None

    def set(self, key: str, value: str) -> None:
        with connect(self._db) as conn:
            conn.execute(
                "INSERT INTO meta (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )

    def all(self) -> dict[str, str]:
        with connect(self._db) as conn:
            return dict(conn.execute("SELECT key, value FROM meta").fetchall())
