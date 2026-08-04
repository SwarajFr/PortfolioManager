"""Zerodha Kite Connect provider — the only module in the app that calls Kite.

It owns everything vendor-specific that used to be copied across features:
per-interval range caps and chunking, the shared request budget, symbol→exchange
key formatting, and the mapping from kiteconnect exceptions to data-layer errors.
Session and token lifecycle stay in `core.kite`; this class only borrows the
authenticated client.
"""
from __future__ import annotations

import datetime
import logging
from collections.abc import Iterator, Sequence
from typing import ClassVar

from kiteconnect.exceptions import KiteException, TokenException

from core import kite as kite_session

from ..errors import NotAuthenticatedError, ProviderError, SymbolNotFoundError
from ..models import Candle, InstrumentRef, Quote
from .base import Capability, MarketDataProvider
from .rate_limit import RateLimiter
from .registry import register

logger = logging.getLogger(__name__)

# Kite caps the span of a single historical_data call per interval.
_MAX_RANGE_DAYS: dict[str, int] = {
    "minute": 60,
    "3minute": 100,
    "5minute": 100,
    "10minute": 100,
    "15minute": 200,
    "30minute": 200,
    "60minute": 400,
    "day": 2000,
}
_DEFAULT_RANGE_DAYS = 2000

# ltp() accepts up to 500 instrument keys per request.
_QUOTE_BATCH = 500


@register
class KiteProvider(MarketDataProvider):
    name: ClassVar[str] = "kite"
    capabilities: ClassVar[frozenset[Capability]] = frozenset(
        {
            Capability.HISTORY,
            Capability.QUOTES,
            Capability.INSTRUMENTS,
            Capability.HOLDINGS,
        }
    )

    def __init__(self, rate_limit_rps: float = 3.0):
        self._limiter = RateLimiter(rate_limit_rps)

    # ── session ──────────────────────────────────────────────────────────────
    def is_available(self) -> bool:
        return kite_session.is_authenticated()

    def _client(self):
        try:
            return kite_session.get_kite()
        except Exception as exc:
            raise NotAuthenticatedError("Kite session is not authenticated") from exc

    # ── history ──────────────────────────────────────────────────────────────
    def fetch_candles(
        self,
        ref: InstrumentRef,
        start: datetime.date,
        end: datetime.date,
        interval: str = "day",
    ) -> list[Candle]:
        if ref.token is None:
            raise SymbolNotFoundError(ref.symbol, ref.exchange)

        client = self._client()
        span = _MAX_RANGE_DAYS.get(interval, _DEFAULT_RANGE_DAYS)
        candles: list[Candle] = []
        for chunk_start, chunk_end in _chunk_range(start, end, span):
            self._limiter.acquire()
            records = self._call(
                client.historical_data, ref.token, chunk_start, chunk_end, interval
            )
            candles.extend(_to_candles(records))
        return candles

    # ── quotes ───────────────────────────────────────────────────────────────
    def fetch_quotes(self, refs: Sequence[InstrumentRef]) -> dict[str, Quote]:
        if not refs:
            return {}
        client = self._client()
        by_key = {f"{r.exchange}:{r.symbol}": r for r in refs}
        keys = list(by_key)

        quotes: dict[str, Quote] = {}
        for i in range(0, len(keys), _QUOTE_BATCH):
            batch = keys[i : i + _QUOTE_BATCH]
            self._limiter.acquire()
            payload = self._call(client.ltp, batch)
            for key, entry in (payload or {}).items():
                ref = by_key.get(key)
                price = (entry or {}).get("last_price")
                if ref is None or price is None:
                    continue
                quotes[ref.symbol] = Quote(
                    symbol=ref.symbol, last_price=float(price), exchange=ref.exchange
                )
        return quotes

    # ── reference data ───────────────────────────────────────────────────────
    def fetch_instruments(self, exchange: str) -> list[InstrumentRef]:
        client = self._client()
        self._limiter.acquire()
        rows = self._call(client.instruments, exchange)
        return [_to_ref(r, exchange) for r in rows or []]

    # ── broker state ─────────────────────────────────────────────────────────
    def fetch_holdings(self) -> list[dict]:
        client = self._client()
        return self._call(client.holdings) or []

    # ── shared error mapping ─────────────────────────────────────────────────
    def _call(self, fn, *args):
        """Run a Kite call, translating vendor exceptions into data-layer ones."""
        try:
            return fn(*args)
        except TokenException as exc:
            raise NotAuthenticatedError(str(exc)) from exc
        except KiteException as exc:
            raise ProviderError(f"kite: {type(exc).__name__}: {exc}") from exc
        except Exception as exc:  # network stack, JSON decode, SDK internals
            raise ProviderError(f"kite: {type(exc).__name__}: {exc}") from exc


def _chunk_range(
    start: datetime.date, end: datetime.date, span_days: int
) -> Iterator[tuple[datetime.date, datetime.date]]:
    """Split [start, end] into consecutive windows no longer than span_days."""
    cursor = start
    step = datetime.timedelta(days=span_days - 1)
    while cursor <= end:
        chunk_end = min(cursor + step, end)
        yield cursor, chunk_end
        cursor = chunk_end + datetime.timedelta(days=1)


def _to_candles(records: list[dict] | None) -> list[Candle]:
    out: list[Candle] = []
    for r in records or []:
        day = r["date"]
        if isinstance(day, datetime.datetime):
            day = day.date()
        elif isinstance(day, str):
            day = datetime.date.fromisoformat(day[:10])
        out.append(
            Candle(
                date=day,
                open=float(r["open"]),
                high=float(r["high"]),
                low=float(r["low"]),
                close=float(r["close"]),
                volume=float(r.get("volume") or 0),
            )
        )
    return out


def _to_ref(row: dict, exchange: str) -> InstrumentRef:
    return InstrumentRef(
        symbol=str(row["tradingsymbol"]),
        token=int(row["instrument_token"]),
        exchange=str(row.get("exchange") or exchange),
        segment=str(row.get("segment") or ""),
        instrument_type=str(row.get("instrument_type") or ""),
        name=str(row.get("name") or ""),
        lot_size=int(row.get("lot_size") or 0),
        tick_size=float(row.get("tick_size") or 0.0),
    )
