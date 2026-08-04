"""Shared test wiring for the market data service.

Tests run the *real* service — real cache-vs-fetch decisions, real SQLite — with
a stub provider standing in for the broker. That keeps the interesting logic
under test instead of mocked away.
"""
from __future__ import annotations

# MUST come before any import that reaches core.kite. That module restores a
# persisted session at *import* time, and the settings store defaults to
# "settings.db" relative to the working directory — so merely collecting tests
# would otherwise create tables in, and migrate the schema of, the developer's
# real settings.db.
import pathlib
import tempfile

import core.settings_store as _settings_store

_settings_store.DB_PATH = str(
    pathlib.Path(tempfile.mkdtemp(prefix="pf-tests-")) / "settings.db"
)

import datetime

import pytest

from core.data import (
    Candle,
    DataConfig,
    InstrumentRef,
    MarketDataProvider,
    MarketDataService,
    ProviderError,
    Quote,
    set_market_data,
)
from core.data.providers.base import Capability
from core.data.repositories import (
    CandleRepository,
    InstrumentRepository,
    MetaRepository,
)

TODAY = datetime.date(2026, 1, 20)


class StubProvider(MarketDataProvider):
    """An in-memory broker. Records what was asked of it so tests can assert
    that the cache actually prevented a fetch."""

    name = "stub"
    capabilities = frozenset(
        {
            Capability.HISTORY,
            Capability.QUOTES,
            Capability.INSTRUMENTS,
            Capability.HOLDINGS,
        }
    )

    def __init__(self):
        self.available = True
        self.candles: dict[str, list[Candle]] = {}
        self.quotes: dict[str, float] = {}
        self.instruments: dict[str, list[InstrumentRef]] = {}
        self.holdings: list[dict] = []
        self.fail_symbols: set[str] = set()

        self.candle_calls: list[tuple[str, datetime.date, datetime.date]] = []
        self.quote_calls: list[list[str]] = []
        self.holdings_calls = 0
        self.instrument_calls = 0

    # ── configuration helpers ────────────────────────────────────────────────
    def set_series(self, symbol: str, start: datetime.date, closes: list[float]) -> None:
        """Store `closes` as consecutive calendar-day bars starting at `start`."""
        self.candles[symbol] = [
            Candle(
                date=start + datetime.timedelta(days=i),
                open=c,
                high=c + 1,
                low=c - 1,
                close=c,
                volume=1000.0,
            )
            for i, c in enumerate(closes)
        ]

    def set_instruments(self, exchange: str, symbols: dict[str, int]) -> None:
        self.instruments[exchange] = [
            InstrumentRef(
                symbol=s, token=t, exchange=exchange, segment=exchange,
                instrument_type="EQ",
            )
            for s, t in symbols.items()
        ]

    # ── provider interface ───────────────────────────────────────────────────
    def is_available(self) -> bool:
        return self.available

    def fetch_candles(self, ref, start, end, interval="day"):
        self.candle_calls.append((ref.symbol, start, end))
        if ref.symbol in self.fail_symbols:
            raise ProviderError(f"stub failure for {ref.symbol}")
        return [c for c in self.candles.get(ref.symbol, []) if start <= c.date <= end]

    def fetch_quotes(self, refs):
        self.quote_calls.append([r.symbol for r in refs])
        return {
            r.symbol: Quote(symbol=r.symbol, last_price=self.quotes[r.symbol])
            for r in refs
            if r.symbol in self.quotes
        }

    def fetch_instruments(self, exchange):
        self.instrument_calls += 1
        return list(self.instruments.get(exchange, []))

    def fetch_holdings(self):
        self.holdings_calls += 1
        return list(self.holdings)


@pytest.fixture()
def stub_provider() -> StubProvider:
    return StubProvider()


@pytest.fixture()
def data_config(tmp_path) -> DataConfig:
    # TTLs off by default so cache-vs-fetch assertions measure the persistent
    # store, not an in-process memo. Tests that care about TTLs set their own.
    return DataConfig(
        provider="stub",
        db_path=str(tmp_path / "market.db"),
        default_lookback_days=30,
        rate_limit_rps=0,
        history_fill_ttl_seconds=0,
        holdings_ttl_seconds=0,
        quote_ttl_seconds=0,
    )


def build_test_service(provider, config, today=TODAY) -> MarketDataService:
    return MarketDataService(
        provider=provider,
        candles=CandleRepository(config.db_path),
        instruments=InstrumentRepository(config.db_path),
        meta=MetaRepository(config.db_path),
        config=config,
        today=lambda: today,
    )


@pytest.fixture()
def market_data(stub_provider, data_config) -> MarketDataService:
    """The real service, stub-backed, installed as the app-wide singleton."""
    service = build_test_service(stub_provider, data_config)
    set_market_data(service)
    yield service
    set_market_data(None)
