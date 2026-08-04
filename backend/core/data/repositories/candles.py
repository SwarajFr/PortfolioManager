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

#: Ceiling on host parameters in one statement. SQLite's own limit is 999 on
#: builds before 3.32 and 32766 after, and the bundled version varies by
#: platform — so batched reads chunk to the old floor rather than probe for it.
#: A universe read is a handful of chunks either way.
_MAX_SQL_PARAMS = 900


def _as_iso(value: datetime.date | str) -> str:
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def _chunked(items: list[str], size: int):
    for start in range(0, len(items), size):
        yield items[start : start + size]


def _unique(symbols: Iterable[str]) -> list[str]:
    """De-duplicated, order-preserving. `dict.fromkeys` because a repeated
    symbol in an `IN (...)` list would multiply that symbol's rows."""
    return list(dict.fromkeys(s for s in symbols if s))


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

    def read_many(
        self,
        symbols: Iterable[str],
        start: datetime.date | None = None,
        end: datetime.date | None = None,
    ) -> dict[str, pd.DataFrame]:
        """`read` for many symbols, as one scan instead of one query each.

        Behaviourally identical to calling `read` in a loop — same frames, same
        window, same dtypes — but it costs one connection and one indexed range
        scan rather than *n* of each. That difference is the whole point: a
        universe-wide read was paying a connect, two PRAGMAs and a query per
        symbol, which dominated the actual row fetching.

        Symbols with no stored rows are **absent from the result** rather than
        mapped to an empty frame, so the keys describe what is genuinely cached.
        """
        unique = _unique(symbols)
        if not unique:
            return {}

        # Partition in one pass: rows arrive interleaved by symbol, and grouping
        # them in a dict is O(rows) with no re-scan per symbol.
        by_symbol: dict[str, list[tuple]] = {}
        bounds: list[str] = []
        clause = ""
        if start is not None:
            clause += " AND date >= ?"
            bounds.append(_as_iso(start))
        if end is not None:
            clause += " AND date <= ?"
            bounds.append(_as_iso(end))

        with connect(self._db) as conn:
            for chunk in _chunked(unique, _MAX_SQL_PARAMS - len(bounds)):
                placeholders = ",".join("?" * len(chunk))
                rows = conn.execute(
                    "SELECT symbol, date, open, high, low, close, volume "
                    f"FROM candles WHERE symbol IN ({placeholders}){clause} "
                    "ORDER BY symbol, date ASC",
                    (*chunk, *bounds),
                ).fetchall()
                for row in rows:
                    by_symbol.setdefault(row[0], []).append(row[1:])

        # _to_frame is shared with read(), so the frames cannot drift apart.
        return {symbol: _to_frame(rows) for symbol, rows in by_symbol.items()}

    def date_range(self, symbol: str) -> tuple[str | None, str | None]:
        """(first, last) stored ISO dates, or (None, None) when unseeded."""
        with connect(self._db) as conn:
            row = conn.execute(
                "SELECT MIN(date), MAX(date) FROM candles WHERE symbol = ?", (symbol,)
            ).fetchone()
        return (row[0], row[1]) if row else (None, None)

    def date_ranges(
        self, symbols: Iterable[str]
    ) -> dict[str, tuple[str | None, str | None]]:
        """`date_range` for many symbols, in one grouped query.

        Every symbol asked for appears in the result; unseeded ones report
        `(None, None)`, matching `date_range`, so callers need no membership
        check before indexing.
        """
        unique = _unique(symbols)
        if not unique:
            return {}

        found: dict[str, tuple[str | None, str | None]] = {}
        with connect(self._db) as conn:
            for chunk in _chunked(unique, _MAX_SQL_PARAMS):
                placeholders = ",".join("?" * len(chunk))
                for symbol, first, last in conn.execute(
                    "SELECT symbol, MIN(date), MAX(date) FROM candles "
                    f"WHERE symbol IN ({placeholders}) GROUP BY symbol",
                    tuple(chunk),
                ):
                    found[symbol] = (first, last)

        return {symbol: found.get(symbol, (None, None)) for symbol in unique}

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
