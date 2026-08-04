"""Transport types for the data layer.

Providers and repositories exchange these; the service converts price series to
pandas at its own boundary because every consumer (`compute.py`, `engine.py`)
already speaks DataFrames.
"""
from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

#: Column order of every OHLC frame the service hands out.
CANDLE_COLUMNS = ("open", "high", "low", "close", "volume")


@dataclass(frozen=True, slots=True)
class InstrumentRef:
    """A tradable instrument. `token` is the provider-specific handle.

    Kite addresses historical data by ``instrument_token``; other providers
    address it by symbol. Carrying both lets each provider use what it needs
    without the service caring which.
    """

    symbol: str
    token: int | None = None
    exchange: str = "NSE"
    segment: str = ""
    instrument_type: str = ""
    name: str = ""
    lot_size: int = 0
    tick_size: float = 0.0


@dataclass(frozen=True, slots=True)
class Candle:
    date: datetime.date
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


@dataclass(frozen=True, slots=True)
class Quote:
    symbol: str
    last_price: float
    exchange: str = "NSE"
    timestamp: datetime.datetime | None = None


@dataclass(frozen=True, slots=True)
class Fundamentals:
    """Provider-shaped fundamentals. `fields` stays open because no two
    fundamentals sources agree on a schema."""

    symbol: str
    fields: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class RefreshReport:
    """Outcome of a bulk history refresh."""

    updated: int = 0
    skipped: int = 0
    updated_symbols: list[str] = field(default_factory=list)
    errors: list[tuple[str, str]] = field(default_factory=list)

    def record_update(self, symbol: str) -> None:
        self.updated += 1
        self.updated_symbols.append(symbol)

    def record_skip(self, symbol: str, reason: str) -> None:
        self.skipped += 1
        self.errors.append((symbol, reason))


def empty_history() -> pd.DataFrame:
    """An OHLC frame with the right dtypes but no rows.

    Consumers index by column and call ``.iloc[-1]``; handing back a correctly
    shaped empty frame keeps them on one code path.
    """
    return pd.DataFrame(
        {c: pd.Series(dtype="float64") for c in CANDLE_COLUMNS},
        index=pd.DatetimeIndex([], name="date"),
    )
