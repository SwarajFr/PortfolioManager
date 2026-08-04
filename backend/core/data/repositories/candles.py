"""Append-only daily OHLC store.

Schema is byte-identical to the one the screener created, so an existing
``screener_cache.db`` is picked up as-is. A settled daily bar never changes,
which is what makes the store append-only and `INSERT OR IGNORE` safe in both
fill directions (older head, newer tail).
"""
from __future__ import annotations

import datetime
from collections.abc import Iterable

import pandas as pd

from ..models import CANDLE_COLUMNS, Candle, empty_history
from .db import connect


def _as_iso(value: datetime.date | str) -> str:
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


class CandleRepository:
    def __init__(self, db_path: str):
        self._db = db_path
        self.init()

    def init(self) -> None:
        with connect(self._db) as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS candles ("
                "symbol TEXT, date TEXT, open REAL, high REAL, low REAL, "
                "close REAL, volume REAL, PRIMARY KEY (symbol, date))"
            )

    # ── writes ───────────────────────────────────────────────────────────────
    def upsert(self, symbol: str, candles: Iterable[Candle]) -> int:
        """Insert bars that are not already stored. Returns the number added."""
        rows = [
            (symbol, c.date.isoformat(), c.open, c.high, c.low, c.close, c.volume)
            for c in candles
        ]
        if not rows:
            return 0
        with connect(self._db) as conn:
            before = conn.total_changes
            conn.executemany(
                "INSERT OR IGNORE INTO candles "
                "(symbol, date, open, high, low, close, volume) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                rows,
            )
            return conn.total_changes - before

    # ── reads ────────────────────────────────────────────────────────────────
    def read(
        self,
        symbol: str,
        start: datetime.date | None = None,
        end: datetime.date | None = None,
    ) -> pd.DataFrame:
        sql = "SELECT date, open, high, low, close, volume FROM candles WHERE symbol = ?"
        params: list = [symbol]
        if start is not None:
            sql += " AND date >= ?"
            params.append(_as_iso(start))
        if end is not None:
            sql += " AND date <= ?"
            params.append(_as_iso(end))
        sql += " ORDER BY date ASC"

        with connect(self._db) as conn:
            rows = conn.execute(sql, params).fetchall()
        return _to_frame(rows)

    def date_range(self, symbol: str) -> tuple[str | None, str | None]:
        """(first, last) stored ISO dates, or (None, None) when unseeded."""
        with connect(self._db) as conn:
            row = conn.execute(
                "SELECT MIN(date), MAX(date) FROM candles WHERE symbol = ?", (symbol,)
            ).fetchone()
        return (row[0], row[1]) if row else (None, None)

    def last_date(self, symbol: str) -> str | None:
        return self.date_range(symbol)[1]

    def symbols(self) -> list[str]:
        with connect(self._db) as conn:
            return [r[0] for r in conn.execute("SELECT DISTINCT symbol FROM candles")]

    def symbol_count(self) -> int:
        with connect(self._db) as conn:
            row = conn.execute("SELECT COUNT(DISTINCT symbol) FROM candles").fetchone()
        return int(row[0]) if row else 0


def _to_frame(rows: list[tuple]) -> pd.DataFrame:
    if not rows:
        return empty_history()
    df = pd.DataFrame(rows, columns=["date", *CANDLE_COLUMNS])
    index = pd.DatetimeIndex(pd.to_datetime(df.pop("date")), name="date")
    return df.astype("float64").set_axis(index)
