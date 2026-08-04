"""Screener signal store: the latest {score, pass} row per symbol.

Candles, instruments and refresh metadata moved to `core.data`; what is left
here is screener-owned derived data. It shares the market-data database file on
purpose — signals are computed from those candles and are meaningless without
them, so one file keeps the two consistent and backed up together.
"""
from __future__ import annotations

import contextlib
import json
from collections.abc import Generator
from sqlite3 import Connection

from core.data import get_market_data
from core.data.repositories.db import connect

_DDL = (
    "CREATE TABLE IF NOT EXISTS signals ("
    "symbol TEXT PRIMARY KEY, as_of_date TEXT, "
    "scores_json TEXT, passes_json TEXT)"
)


def _path() -> str:
    return get_market_data().config.db_path


@contextlib.contextmanager
def _conn() -> Generator[Connection, None, None]:
    """Open the shared database with the signals table guaranteed to exist, so
    a screen served before the first refresh reads empty rather than erroring."""
    with connect(_path()) as conn:
        conn.execute(_DDL)
        yield conn


def init() -> None:
    with _conn():
        pass


def upsert_signal(symbol: str, as_of_date: str, scores: dict, passes: dict) -> None:
    with _conn() as conn:
        conn.execute(
            "INSERT INTO signals (symbol, as_of_date, scores_json, passes_json) "
            "VALUES (?, ?, ?, ?) ON CONFLICT(symbol) DO UPDATE SET "
            "as_of_date = excluded.as_of_date, scores_json = excluded.scores_json, "
            "passes_json = excluded.passes_json",
            (symbol, as_of_date, json.dumps(scores), json.dumps(passes)),
        )


def read_signals() -> list[dict]:
    with _conn() as conn:
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


def signal_count() -> int:
    with _conn() as conn:
        row = conn.execute("SELECT COUNT(*) FROM signals").fetchone()
    return int(row[0]) if row else 0
