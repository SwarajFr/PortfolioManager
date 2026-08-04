"""Instrument master cache — the symbol → provider-token map.

Previously every refresh re-downloaded the full exchange dump just to build the
screener universe, and no other feature could resolve a symbol at all.
"""
from __future__ import annotations

from collections.abc import Iterable

import pandas as pd

from ..models import InstrumentRef
from .db import connect

_COLUMNS = (
    "exchange",
    "tradingsymbol",
    "instrument_token",
    "segment",
    "instrument_type",
    "name",
    "lot_size",
    "tick_size",
)


class InstrumentRepository:
    def __init__(self, db_path: str):
        self._db = db_path
        self.init()

    def init(self) -> None:
        with connect(self._db) as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS instruments ("
                "exchange TEXT, tradingsymbol TEXT, instrument_token INTEGER, "
                "segment TEXT, instrument_type TEXT, name TEXT, "
                "lot_size INTEGER, tick_size REAL, "
                "PRIMARY KEY (exchange, tradingsymbol))"
            )

    def replace(self, exchange: str, refs: Iterable[InstrumentRef]) -> int:
        """Swap the whole exchange snapshot in one transaction.

        Replace rather than merge: an instrument dropped upstream (delisted,
        expired) must disappear here too, or symbol resolution keeps handing
        out a dead token.
        """
        rows = [
            (
                exchange,
                r.symbol,
                r.token,
                r.segment,
                r.instrument_type,
                r.name,
                r.lot_size,
                r.tick_size,
            )
            for r in refs
        ]
        with connect(self._db) as conn:
            conn.execute("DELETE FROM instruments WHERE exchange = ?", (exchange,))
            if rows:
                conn.executemany(
                    f"INSERT INTO instruments ({', '.join(_COLUMNS)}) "
                    f"VALUES ({', '.join('?' * len(_COLUMNS))})",
                    rows,
                )
        return len(rows)

    def read(self, exchange: str) -> pd.DataFrame:
        with connect(self._db) as conn:
            rows = conn.execute(
                f"SELECT {', '.join(_COLUMNS)} FROM instruments WHERE exchange = ? "
                "ORDER BY tradingsymbol ASC",
                (exchange,),
            ).fetchall()
        return pd.DataFrame(rows, columns=list(_COLUMNS))

    def resolve(self, symbol: str, exchange: str = "NSE") -> InstrumentRef | None:
        with connect(self._db) as conn:
            row = conn.execute(
                f"SELECT {', '.join(_COLUMNS)} FROM instruments "
                "WHERE exchange = ? AND tradingsymbol = ?",
                (exchange, symbol),
            ).fetchone()
        return _to_ref(row) if row else None

    def count(self, exchange: str) -> int:
        with connect(self._db) as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM instruments WHERE exchange = ?", (exchange,)
            ).fetchone()
        return int(row[0]) if row else 0


def _to_ref(row: tuple) -> InstrumentRef:
    exchange, symbol, token, segment, itype, name, lot_size, tick_size = row
    return InstrumentRef(
        symbol=symbol,
        token=int(token) if token is not None else None,
        exchange=exchange,
        segment=segment or "",
        instrument_type=itype or "",
        name=name or "",
        lot_size=int(lot_size or 0),
        tick_size=float(tick_size or 0.0),
    )
