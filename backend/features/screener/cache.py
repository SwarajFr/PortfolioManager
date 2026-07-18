from __future__ import annotations

import json
import sqlite3

import pandas as pd

_CANDLE_COLS = ("date", "open", "high", "low", "close", "volume")


def _connect(path: str) -> sqlite3.Connection:
    # WAL lets a screen read concurrently with the background refresh's writes
    # without "database is locked"; the 5s busy timeout absorbs brief contention.
    conn = sqlite3.connect(path, timeout=5.0)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init(path: str) -> None:
    with _connect(path) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS candles ("
            "symbol TEXT, date TEXT, open REAL, high REAL, low REAL, "
            "close REAL, volume REAL, PRIMARY KEY (symbol, date))"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS signals ("
            "symbol TEXT PRIMARY KEY, as_of_date TEXT, "
            "scores_json TEXT, passes_json TEXT)"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)"
        )


def upsert_candles(path: str, symbol: str, rows: list[dict]) -> int:
    if not rows:
        return 0
    with _connect(path) as conn:
        before = conn.total_changes
        conn.executemany(
            "INSERT OR IGNORE INTO candles "
            "(symbol, date, open, high, low, close, volume) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (symbol, r["date"], r["open"], r["high"], r["low"], r["close"], r["volume"])
                for r in rows
            ],
        )
        return conn.total_changes - before


def last_candle_date(path: str, symbol: str) -> str | None:
    with _connect(path) as conn:
        row = conn.execute(
            "SELECT MAX(date) FROM candles WHERE symbol = ?", (symbol,)
        ).fetchone()
    return row[0] if row else None


def read_candles(path: str, symbol: str) -> pd.DataFrame:
    with _connect(path) as conn:
        rows = conn.execute(
            "SELECT date, open, high, low, close, volume FROM candles "
            "WHERE symbol = ? ORDER BY date ASC",
            (symbol,),
        ).fetchall()
    return pd.DataFrame(rows, columns=list(_CANDLE_COLS))


def upsert_signal(path: str, symbol: str, as_of_date: str, scores: dict, passes: dict) -> None:
    with _connect(path) as conn:
        conn.execute(
            "INSERT INTO signals (symbol, as_of_date, scores_json, passes_json) "
            "VALUES (?, ?, ?, ?) ON CONFLICT(symbol) DO UPDATE SET "
            "as_of_date = excluded.as_of_date, scores_json = excluded.scores_json, "
            "passes_json = excluded.passes_json",
            (symbol, as_of_date, json.dumps(scores), json.dumps(passes)),
        )


def read_signals(path: str) -> list[dict]:
    with _connect(path) as conn:
        rows = conn.execute(
            "SELECT symbol, as_of_date, scores_json, passes_json FROM signals"
        ).fetchall()
    return [
        {
            "symbol": s,
            "as_of_date": d,
            "scores": json.loads(sj),
            "passes": json.loads(pj),
        }
        for s, d, sj, pj in rows
    ]


def get_meta(path: str, key: str) -> str | None:
    with _connect(path) as conn:
        row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return row[0] if row else None


def set_meta(path: str, key: str, value: str) -> None:
    with _connect(path) as conn:
        conn.execute(
            "INSERT INTO meta (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )


def symbol_count(path: str) -> int:
    with _connect(path) as conn:
        row = conn.execute("SELECT COUNT(DISTINCT symbol) FROM candles").fetchone()
    return int(row[0]) if row else 0
