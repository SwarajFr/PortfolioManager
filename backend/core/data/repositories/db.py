"""One place that knows how to open the market-data SQLite file.

WAL lets a screen read while a background refresh writes; the busy timeout
absorbs the brief contention that remains. Both were previously set ad-hoc in
the screener cache module.
"""
from __future__ import annotations

import contextlib
import sqlite3
from collections.abc import Generator

_TIMEOUT_SECONDS = 5.0


@contextlib.contextmanager
def connect(path: str) -> Generator[sqlite3.Connection, None, None]:
    """Open a connection, commit on success, roll back on error, always close."""
    conn = sqlite3.connect(path, timeout=_TIMEOUT_SECONDS)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        with conn:
            yield conn
    finally:
        conn.close()
