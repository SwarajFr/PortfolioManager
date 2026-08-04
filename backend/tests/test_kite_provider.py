"""Tests for the Kite provider: the only module that speaks Kite."""
from __future__ import annotations

import datetime
import time

import pytest
from kiteconnect.exceptions import DataException, TokenException

from core.data import (
    Capability,
    InstrumentRef,
    NotAuthenticatedError,
    ProviderError,
    SymbolNotFoundError,
)
from core.data.providers.kite import (
    KiteProvider,
    _chunk_range,
    _to_candles,
    _to_ref,
)
from core.data.providers.rate_limit import RateLimiter
from core.data.providers.registry import REGISTRY


class FakeKite:
    def __init__(self, **behaviour):
        self.calls: list[tuple] = []
        self.behaviour = behaviour

    def historical_data(self, token, from_date, to_date, interval):
        self.calls.append(("historical_data", token, from_date, to_date, interval))
        error = self.behaviour.get("historical_error")
        if error:
            raise error
        return self.behaviour.get("candles", [])

    def ltp(self, keys):
        self.calls.append(("ltp", tuple(keys)))
        return self.behaviour.get("ltp", {})

    def instruments(self, exchange):
        self.calls.append(("instruments", exchange))
        return self.behaviour.get("instruments", [])

    def holdings(self):
        self.calls.append(("holdings",))
        return self.behaviour.get("holdings", [])


@pytest.fixture()
def provider(monkeypatch):
    """A provider whose session is stubbed out; rate limiting disabled."""
    import core.data.providers.kite as kite_provider

    fake = FakeKite()
    monkeypatch.setattr(kite_provider.kite_session, "is_authenticated", lambda: True)
    monkeypatch.setattr(kite_provider.kite_session, "get_kite", lambda: fake)
    p = KiteProvider(rate_limit_rps=0)
    p.fake = fake
    return p


def _set(provider, **behaviour):
    provider.fake.behaviour.update(behaviour)


# ── registration and capabilities ────────────────────────────────────────────
def test_kite_provider_is_registered():
    assert REGISTRY["kite"] is KiteProvider


def test_capabilities_exclude_fundamentals():
    p = KiteProvider(rate_limit_rps=0)
    assert p.supports(Capability.HISTORY)
    assert p.supports(Capability.HOLDINGS)
    assert not p.supports(Capability.FUNDAMENTALS)


# ── session handling ─────────────────────────────────────────────────────────
def test_unauthenticated_session_maps_to_not_authenticated(monkeypatch):
    import core.data.providers.kite as kite_provider

    def boom():
        raise Exception("Not authenticated")

    monkeypatch.setattr(kite_provider.kite_session, "get_kite", boom)
    monkeypatch.setattr(kite_provider.kite_session, "is_authenticated", lambda: False)

    p = KiteProvider(rate_limit_rps=0)
    assert p.is_available() is False
    with pytest.raises(NotAuthenticatedError):
        p.fetch_holdings()


def test_token_exception_maps_to_not_authenticated(provider):
    _set(provider, historical_error=TokenException("expired"))
    with pytest.raises(NotAuthenticatedError):
        provider.fetch_candles(
            InstrumentRef("INFY", 1), datetime.date(2026, 1, 1), datetime.date(2026, 1, 2)
        )


def test_other_kite_errors_map_to_provider_error(provider):
    _set(provider, historical_error=DataException("bad gateway"))
    with pytest.raises(ProviderError):
        provider.fetch_candles(
            InstrumentRef("INFY", 1), datetime.date(2026, 1, 1), datetime.date(2026, 1, 2)
        )


def test_missing_token_raises_symbol_not_found(provider):
    with pytest.raises(SymbolNotFoundError):
        provider.fetch_candles(
            InstrumentRef("INFY"), datetime.date(2026, 1, 1), datetime.date(2026, 1, 2)
        )


# ── history ──────────────────────────────────────────────────────────────────
def test_fetch_candles_normalizes_kite_rows(provider):
    _set(
        provider,
        candles=[
            {
                "date": datetime.datetime(2026, 1, 2, 0, 0),
                "open": 1,
                "high": 2,
                "low": 0.5,
                "close": 1.5,
                "volume": 100,
            }
        ],
    )
    candles = provider.fetch_candles(
        InstrumentRef("INFY", 1), datetime.date(2026, 1, 1), datetime.date(2026, 1, 3)
    )
    assert candles[0].date == datetime.date(2026, 1, 2)  # datetime -> date
    assert candles[0].close == 1.5


def test_fetch_candles_chunks_long_windows(provider):
    """A 900-day fragility window fits in one day-interval call; a 3000-day one
    does not."""
    start = datetime.date(2018, 1, 1)
    provider.fetch_candles(
        InstrumentRef("INFY", 1), start, start + datetime.timedelta(days=2999)
    )
    ranges = [(c[2], c[3]) for c in provider.fake.calls]
    assert len(ranges) == 2
    assert ranges[0][0] == start
    assert ranges[1][0] == ranges[0][1] + datetime.timedelta(days=1)
    assert ranges[-1][1] == start + datetime.timedelta(days=2999)


def test_fetch_candles_does_not_chunk_a_900_day_window(provider):
    start = datetime.date(2024, 1, 1)
    provider.fetch_candles(
        InstrumentRef("INFY", 1), start, start + datetime.timedelta(days=899)
    )
    assert len(provider.fake.calls) == 1


# ── quotes ───────────────────────────────────────────────────────────────────
def test_fetch_quotes_keys_by_symbol_and_drops_misses(provider):
    _set(provider, ltp={"NSE:INFY": {"last_price": 1500.0}, "NSE:TCS": {}})
    quotes = provider.fetch_quotes(
        [InstrumentRef("INFY"), InstrumentRef("TCS"), InstrumentRef("NOPE")]
    )
    assert set(quotes) == {"INFY"}
    assert quotes["INFY"].last_price == 1500.0
    assert provider.fake.calls[0][1] == ("NSE:INFY", "NSE:TCS", "NSE:NOPE")


def test_fetch_quotes_with_no_symbols_makes_no_call(provider):
    assert provider.fetch_quotes([]) == {}
    assert provider.fake.calls == []


# ── reference + broker ───────────────────────────────────────────────────────
def test_fetch_instruments_maps_rows(provider):
    _set(
        provider,
        instruments=[
            {
                "tradingsymbol": "INFY",
                "instrument_token": 408065,
                "exchange": "NSE",
                "segment": "NSE",
                "instrument_type": "EQ",
                "name": "INFOSYS",
                "lot_size": 1,
                "tick_size": 0.05,
            }
        ],
    )
    refs = provider.fetch_instruments("NSE")
    assert refs[0].symbol == "INFY"
    assert refs[0].token == 408065
    assert refs[0].segment == "NSE"


def test_fetch_holdings_passes_rows_through(provider):
    _set(provider, holdings=[{"tradingsymbol": "INFY", "quantity": 5}])
    assert provider.fetch_holdings() == [{"tradingsymbol": "INFY", "quantity": 5}]


# ── helpers ──────────────────────────────────────────────────────────────────
def test_chunk_range_covers_the_window_without_overlap():
    start, end = datetime.date(2026, 1, 1), datetime.date(2026, 1, 10)
    chunks = list(_chunk_range(start, end, 4))
    assert chunks[0][0] == start
    assert chunks[-1][1] == end
    for (_, prev_end), (next_start, _) in zip(chunks, chunks[1:]):
        assert next_start == prev_end + datetime.timedelta(days=1)
    assert all((e - s).days < 4 for s, e in chunks)


def test_chunk_range_single_day():
    day = datetime.date(2026, 1, 1)
    assert list(_chunk_range(day, day, 2000)) == [(day, day)]


def test_to_candles_accepts_dates_datetimes_and_strings():
    rows = [
        {"date": datetime.date(2026, 1, 1), "open": 1, "high": 1, "low": 1, "close": 1},
        {"date": datetime.datetime(2026, 1, 2, 9, 15), "open": 1, "high": 1, "low": 1, "close": 1},
        {"date": "2026-01-03T00:00:00+0530", "open": 1, "high": 1, "low": 1, "close": 1},
    ]
    candles = _to_candles(rows)
    assert [c.date.isoformat() for c in candles] == ["2026-01-01", "2026-01-02", "2026-01-03"]
    assert candles[0].volume == 0.0  # missing volume defaults, never KeyErrors


def test_to_ref_tolerates_sparse_rows():
    ref = _to_ref({"tradingsymbol": "X", "instrument_token": 7}, "NSE")
    assert ref.exchange == "NSE"
    assert ref.lot_size == 0


def test_rate_limiter_spaces_calls():
    limiter = RateLimiter(requests_per_second=50)  # 20ms apart
    start = time.monotonic()
    for _ in range(3):
        limiter.acquire()
    assert time.monotonic() - start >= 0.03


def test_rate_limiter_disabled_when_rps_is_zero():
    limiter = RateLimiter(requests_per_second=0)
    start = time.monotonic()
    for _ in range(100):
        limiter.acquire()
    assert time.monotonic() - start < 0.5
