"""Tests for the centralized market data service."""
from __future__ import annotations

import dataclasses
import datetime

import pandas as pd
import pytest
from conftest import TODAY, build_test_service

from core.data import (
    CapabilityNotSupportedError,
    InstrumentRef,
    NotAuthenticatedError,
    SymbolNotFoundError,
    get_market_data,
)
from core.data.service import _missing_ranges

START = datetime.date(2026, 1, 1)


def _seed_provider(provider, symbol="INFY", token=100, days=20, first=START):
    provider.set_instruments("NSE", {symbol: token})
    provider.set_series(symbol, first, [100.0 + i for i in range(days)])


# ── history: cache-first ─────────────────────────────────────────────────────
def test_get_history_fetches_then_serves_from_cache(market_data, stub_provider):
    _seed_provider(stub_provider)

    first = market_data.get_history("INFY", start=START, end=TODAY)
    assert len(first) == 20
    assert list(first.columns) == ["open", "high", "low", "close", "volume"]
    assert isinstance(first.index, pd.DatetimeIndex)
    assert len(stub_provider.candle_calls) == 1

    second = market_data.get_history("INFY", start=START, end=TODAY)
    # Same window, already stored: no second trip upstream.
    assert len(stub_provider.candle_calls) == 1
    pd.testing.assert_frame_equal(first, second)


def test_get_history_fetches_only_the_missing_tail(market_data, stub_provider):
    _seed_provider(stub_provider, days=25)

    market_data.get_history("INFY", start=START, end=datetime.date(2026, 1, 10))
    stub_provider.candle_calls.clear()

    market_data.get_history("INFY", start=START, end=datetime.date(2026, 1, 15))

    assert len(stub_provider.candle_calls) == 1
    _, fetch_start, fetch_end = stub_provider.candle_calls[0]
    assert fetch_start == datetime.date(2026, 1, 11)  # strictly after stored max
    assert fetch_end == datetime.date(2026, 1, 15)


def test_get_history_backfills_the_head_for_a_longer_window(
    market_data, stub_provider
):
    """The screener seeds a short window; fragility asks for a longer one.

    The store must grow backwards, not just forwards.
    """
    _seed_provider(stub_provider, days=40, first=datetime.date(2025, 12, 15))

    market_data.get_history(
        "INFY", start=datetime.date(2026, 1, 5), end=datetime.date(2026, 1, 10)
    )
    stub_provider.candle_calls.clear()

    frame = market_data.get_history(
        "INFY", start=datetime.date(2025, 12, 20), end=datetime.date(2026, 1, 10)
    )

    assert len(stub_provider.candle_calls) == 1
    _, fetch_start, fetch_end = stub_provider.candle_calls[0]
    assert fetch_start == datetime.date(2025, 12, 20)
    assert fetch_end == datetime.date(2026, 1, 4)  # up to the day before stored min
    assert frame.index.min().date() == datetime.date(2025, 12, 20)


def test_get_history_fills_both_ends_in_one_call(market_data, stub_provider):
    _seed_provider(stub_provider, days=40, first=datetime.date(2025, 12, 15))
    market_data.get_history(
        "INFY", start=datetime.date(2026, 1, 1), end=datetime.date(2026, 1, 5)
    )
    stub_provider.candle_calls.clear()

    market_data.get_history(
        "INFY", start=datetime.date(2025, 12, 20), end=datetime.date(2026, 1, 15)
    )

    ranges = [(s, e) for _, s, e in stub_provider.candle_calls]
    assert ranges == [
        (datetime.date(2025, 12, 20), datetime.date(2025, 12, 31)),
        (datetime.date(2026, 1, 6), datetime.date(2026, 1, 15)),
    ]


def test_get_history_defaults_to_configured_lookback(market_data, stub_provider):
    _seed_provider(stub_provider, days=40, first=datetime.date(2025, 12, 1))
    market_data.get_history("INFY")
    _, fetch_start, fetch_end = stub_provider.candle_calls[0]
    assert fetch_end == TODAY
    assert fetch_start == TODAY - datetime.timedelta(days=30)  # config lookback


def test_get_history_rejects_inverted_window(market_data):
    with pytest.raises(ValueError):
        market_data.get_history("INFY", start=TODAY, end=START)


# ── history: degraded provider ───────────────────────────────────────────────
def test_get_history_serves_cache_when_provider_unavailable(
    market_data, stub_provider
):
    _seed_provider(stub_provider, days=20)
    market_data.get_history("INFY", start=START, end=TODAY)

    stub_provider.available = False
    stub_provider.candle_calls.clear()

    frame = market_data.get_history("INFY", start=START, end=TODAY)

    assert not stub_provider.candle_calls  # never attempted
    assert len(frame) == 20


def test_get_history_raises_when_nothing_cached_and_provider_unavailable(
    market_data, stub_provider
):
    stub_provider.available = False
    with pytest.raises(NotAuthenticatedError):
        market_data.get_history("INFY", start=START, end=TODAY)


def test_history_fill_ttl_suppresses_repeat_fetches(stub_provider, data_config):
    """After hours the tail gap never closes; without a TTL every page load
    would re-ask upstream for a bar that does not exist yet."""
    config = dataclasses.replace(data_config, history_fill_ttl_seconds=600)
    service = build_test_service(stub_provider, config)
    _seed_provider(stub_provider, days=5)  # store ends well before TODAY

    service.get_history("INFY", start=START, end=TODAY)
    service.get_history("INFY", start=START, end=TODAY)

    assert len(stub_provider.candle_calls) == 1


# ── history: token hints and batching ────────────────────────────────────────
def test_get_history_uses_token_hint_without_instrument_lookup(
    market_data, stub_provider
):
    """Holdings rows already carry a token — no instrument master needed."""
    stub_provider.set_series("INFY", START, [100.0, 101.0, 102.0])

    frame = market_data.get_history(
        InstrumentRef(symbol="INFY", token=100), start=START, end=TODAY
    )

    assert len(frame) == 3
    assert stub_provider.instrument_calls == 0


def test_get_history_batch_skips_failing_symbols(market_data, stub_provider):
    stub_provider.set_instruments("NSE", {"AAA": 1, "BBB": 2})
    stub_provider.set_series("AAA", START, [10.0, 11.0])
    stub_provider.set_series("BBB", START, [20.0, 21.0])
    stub_provider.fail_symbols.add("BBB")

    out = market_data.get_history_batch(["AAA", "BBB"], start=START, end=TODAY)

    assert set(out) == {"AAA"}  # one bad symbol does not sink the batch


def test_get_history_batch_deduplicates(market_data, stub_provider):
    _seed_provider(stub_provider, days=3)
    out = market_data.get_history_batch(["INFY", "infy "], start=START, end=TODAY)
    assert list(out) == ["INFY"]


def test_get_close_frame_is_wide_and_sorted(market_data, stub_provider):
    stub_provider.set_instruments("NSE", {"AAA": 1, "BBB": 2})
    stub_provider.set_series("AAA", START, [10.0, 11.0, 12.0])
    stub_provider.set_series("BBB", START, [20.0, 21.0, 22.0])

    frame = market_data.get_close_frame(["AAA", "BBB"], start=START, end=TODAY)

    assert list(frame.columns) == ["AAA", "BBB"]
    assert frame["AAA"].tolist() == [10.0, 11.0, 12.0]
    assert frame.index.is_monotonic_increasing


def test_get_close_frame_empty_when_nothing_resolves(market_data, stub_provider):
    stub_provider.available = False
    assert market_data.get_close_frame(["AAA"], start=START, end=TODAY).empty


# ── bulk refresh ─────────────────────────────────────────────────────────────
def _refs(*symbols):
    return [InstrumentRef(symbol=s, token=i + 1) for i, s in enumerate(symbols)]


def test_refresh_history_seeds_then_appends_incrementally(
    market_data, stub_provider
):
    stub_provider.set_series("AAA", START, [10.0, 11.0, 12.0])

    seeded = market_data.refresh_history(_refs("AAA"), lookback_days=30, seed=True)
    assert seeded.updated == 1
    assert seeded.updated_symbols == ["AAA"]

    # A new bar lands; the incremental pass must resume after the stored max.
    stub_provider.set_series("AAA", START, [10.0, 11.0, 12.0, 13.0])
    stub_provider.candle_calls.clear()

    again = market_data.refresh_history(_refs("AAA"), lookback_days=30)

    _, fetch_start, _ = stub_provider.candle_calls[0]
    assert fetch_start == datetime.date(2026, 1, 4)  # day after the stored max
    assert again.updated == 1
    assert len(market_data.get_history("AAA", start=START, end=TODAY, refresh=False)) == 4


def test_refresh_history_is_a_noop_when_nothing_new(market_data, stub_provider):
    stub_provider.set_series("AAA", START, [10.0, 11.0])
    market_data.refresh_history(_refs("AAA"), lookback_days=30, seed=True)

    report = market_data.refresh_history(_refs("AAA"), lookback_days=30)

    assert report.updated == 0
    assert report.updated_symbols == []


def test_refresh_history_skips_and_logs_a_dead_symbol(market_data, stub_provider):
    stub_provider.fail_symbols.add("DELISTED")
    report = market_data.refresh_history(_refs("DELISTED"), lookback_days=30)
    assert report.skipped == 1
    assert report.errors[0][0] == "DELISTED"


def test_refresh_history_notifies_only_updated_symbols(market_data, stub_provider):
    stub_provider.set_series("AAA", START, [10.0])
    seen: list[str] = []

    market_data.refresh_history(
        _refs("AAA", "EMPTY"), lookback_days=30, seed=True, on_updated=seen.append
    )

    assert seen == ["AAA"]  # EMPTY returned no candles, so no recompute


def test_refresh_history_stamps_meta(market_data, stub_provider):
    stub_provider.set_series("AAA", START, [10.0])
    market_data.refresh_history(_refs("AAA"), lookback_days=30, seed=True)

    status = market_data.status()
    assert status["seed_complete"] is True
    assert status["last_updated"] is not None
    assert status["symbol_count"] == 1


# ── live state ───────────────────────────────────────────────────────────────
def test_get_holdings_returns_a_defensive_copy(market_data, stub_provider):
    stub_provider.holdings = [
        {"tradingsymbol": "INFY", "quantity": 10, "last_price": 150.0}
    ]
    frame = market_data.get_holdings()
    frame.loc[0, "quantity"] = 999
    assert market_data.get_holdings().loc[0, "quantity"] == 10


def test_get_holdings_ttl_collapses_repeat_calls(stub_provider, data_config):
    config = dataclasses.replace(data_config, holdings_ttl_seconds=60)
    service = build_test_service(stub_provider, config)
    stub_provider.holdings = [{"tradingsymbol": "INFY", "quantity": 1}]

    service.get_holdings()
    service.get_holdings()

    assert stub_provider.holdings_calls == 1


def test_get_quote_returns_found_symbols_only(market_data, stub_provider):
    stub_provider.quotes = {"INFY": 1500.5}
    quotes = market_data.get_quote(["INFY", "NOPE"])
    assert set(quotes) == {"INFY"}
    assert quotes["INFY"].last_price == 1500.5


def test_get_quote_accepts_a_bare_string(market_data, stub_provider):
    stub_provider.quotes = {"INFY": 10.0}
    assert set(market_data.get_quote("infy")) == {"INFY"}


def test_get_quote_ttl_collapses_repeat_calls(stub_provider, data_config):
    config = dataclasses.replace(data_config, quote_ttl_seconds=60)
    service = build_test_service(stub_provider, config)
    stub_provider.quotes = {"INFY": 10.0}

    service.get_quote(["INFY"])
    service.get_quote(["INFY"])

    assert len(stub_provider.quote_calls) == 1


# ── reference data ───────────────────────────────────────────────────────────
def test_get_instruments_caches_between_calls(market_data, stub_provider):
    stub_provider.set_instruments("NSE", {"AAA": 1, "BBB": 2})

    first = market_data.get_instruments("NSE")
    second = market_data.get_instruments("NSE")

    assert len(first) == len(second) == 2
    assert stub_provider.instrument_calls == 1


def test_get_instruments_force_refresh_refetches(market_data, stub_provider):
    stub_provider.set_instruments("NSE", {"AAA": 1})
    market_data.get_instruments("NSE")
    market_data.get_instruments("NSE", refresh=True)
    assert stub_provider.instrument_calls == 2


def test_get_instruments_replaces_delisted_rows(market_data, stub_provider):
    stub_provider.set_instruments("NSE", {"AAA": 1, "GONE": 2})
    market_data.get_instruments("NSE")

    stub_provider.set_instruments("NSE", {"AAA": 1})
    frame = market_data.get_instruments("NSE", refresh=True)

    assert frame["tradingsymbol"].tolist() == ["AAA"]


def test_resolve_finds_token_and_raises_for_unknown(market_data, stub_provider):
    stub_provider.set_instruments("NSE", {"AAA": 42})

    assert market_data.resolve("aaa").token == 42
    with pytest.raises(SymbolNotFoundError):
        market_data.resolve("NOSUCH")


def test_get_instruments_survives_an_unavailable_provider(market_data, stub_provider):
    stub_provider.set_instruments("NSE", {"AAA": 1})
    market_data.get_instruments("NSE")

    stub_provider.available = False
    assert len(market_data.get_instruments("NSE", refresh=True)) == 1  # stale is fine


# ── capabilities ─────────────────────────────────────────────────────────────
def test_get_fundamentals_raises_capability_error(market_data, stub_provider):
    stub_provider.set_instruments("NSE", {"INFY": 1})
    with pytest.raises(CapabilityNotSupportedError) as exc:
        market_data.get_fundamentals("INFY")
    assert exc.value.capability == "fundamentals"


def test_status_reports_provider_and_capabilities(market_data):
    status = market_data.status()
    assert status["provider"] == "stub"
    assert status["authenticated"] is True
    assert "history" in status["capabilities"]
    assert "fundamentals" not in status["capabilities"]


def test_container_singleton_is_the_installed_service(market_data):
    assert get_market_data() is market_data


# ── repositories ─────────────────────────────────────────────────────────────
def test_candle_store_is_append_only(data_config):
    from core.data import Candle
    from core.data.repositories import CandleRepository

    repo = CandleRepository(data_config.db_path)
    rows = [
        Candle(datetime.date(2026, 1, 1), 1, 2, 1, 1.5, 10),
        Candle(datetime.date(2026, 1, 2), 1.5, 2.5, 1.4, 2.0, 12),
    ]
    assert repo.upsert("RELIANCE", rows) == 2
    # Re-inserting the same dates plus one new date appends only the new one.
    assert repo.upsert("RELIANCE", [*rows, Candle(datetime.date(2026, 1, 3), 2, 3, 2, 2.5, 9)]) == 1

    stored = repo.read("RELIANCE")
    assert [d.date().isoformat() for d in stored.index] == [
        "2026-01-01", "2026-01-02", "2026-01-03"
    ]
    assert repo.date_range("RELIANCE") == ("2026-01-01", "2026-01-03")
    assert repo.symbol_count() == 1


def test_candle_store_read_of_unknown_symbol_is_empty(data_config):
    from core.data.repositories import CandleRepository

    frame = CandleRepository(data_config.db_path).read("NOSUCH")
    assert frame.empty
    assert list(frame.columns) == ["open", "high", "low", "close", "volume"]


# ── batched reads ────────────────────────────────────────────────────────────
# read_many exists purely to collapse N point queries into one range scan, so
# every test here is really asking the same thing: is it *indistinguishable*
# from calling read() in a loop?
def _seed(repo, symbol, days, base=100.0):
    from core.data import Candle

    repo.upsert(
        symbol,
        [
            Candle(datetime.date(2026, 1, 1) + datetime.timedelta(days=i),
                   base + i, base + i + 1, base + i - 1, base + i + 0.5, 1000 + i)
            for i in range(days)
        ],
    )


def test_read_many_matches_a_loop_of_read(data_config):
    from core.data.repositories import CandleRepository

    repo = CandleRepository(data_config.db_path)
    for symbol in ("INFY", "TCS", "WIPRO"):
        _seed(repo, symbol, 10)

    batched = repo.read_many(["INFY", "TCS", "WIPRO"])
    assert set(batched) == {"INFY", "TCS", "WIPRO"}
    for symbol, frame in batched.items():
        expected = repo.read(symbol)
        pd.testing.assert_frame_equal(frame, expected)


def test_read_many_applies_the_same_window_as_read(data_config):
    from core.data.repositories import CandleRepository

    repo = CandleRepository(data_config.db_path)
    _seed(repo, "INFY", 30)
    start, end = datetime.date(2026, 1, 10), datetime.date(2026, 1, 20)

    pd.testing.assert_frame_equal(
        repo.read_many(["INFY"], start, end)["INFY"], repo.read("INFY", start, end)
    )


def test_read_many_omits_symbols_with_no_rows(data_config):
    from core.data.repositories import CandleRepository

    repo = CandleRepository(data_config.db_path)
    _seed(repo, "INFY", 5)

    # An absent symbol is left out entirely rather than mapped to an empty
    # frame, so callers can treat the keys as "what we actually have".
    assert set(repo.read_many(["INFY", "NOSUCH"])) == {"INFY"}
    assert repo.read_many([]) == {}
    assert repo.read_many(["NOSUCH"]) == {}


def test_read_many_deduplicates_and_survives_more_symbols_than_sqlite_params(data_config):
    from core.data.repositories import CandleRepository

    repo = CandleRepository(data_config.db_path)
    symbols = [f"SYM{i:04d}" for i in range(1200)]  # exceeds the 999-param floor
    for symbol in symbols:
        _seed(repo, symbol, 2)

    batched = repo.read_many([*symbols, *symbols])  # duplicates must not double rows
    assert len(batched) == 1200
    assert all(len(frame) == 2 for frame in batched.values())


def test_date_ranges_matches_a_loop_of_date_range(data_config):
    from core.data.repositories import CandleRepository

    repo = CandleRepository(data_config.db_path)
    _seed(repo, "INFY", 10)
    _seed(repo, "TCS", 3)

    ranges = repo.date_ranges(["INFY", "TCS", "NOSUCH"])
    assert ranges["INFY"] == repo.date_range("INFY")
    assert ranges["TCS"] == repo.date_range("TCS")
    # Unknown symbols report (None, None), exactly as date_range does.
    assert ranges["NOSUCH"] == (None, None) == repo.date_range("NOSUCH")


def test_meta_roundtrip(data_config):
    from core.data.repositories import MetaRepository

    meta = MetaRepository(data_config.db_path)
    assert meta.get("seed_complete") is None
    meta.set("seed_complete", "1")
    assert meta.get("seed_complete") == "1"
    assert meta.all()["seed_complete"] == "1"


def test_database_uses_wal_journal(data_config):
    import sqlite3

    from core.data.repositories import CandleRepository

    CandleRepository(data_config.db_path)  # creates the file with the pragma
    conn = sqlite3.connect(data_config.db_path)
    mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    conn.close()
    assert mode.lower() == "wal"  # read-during-refresh must not block


# ── gap arithmetic ───────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    ("first", "last", "expected"),
    [
        (None, None, [(datetime.date(2026, 1, 1), datetime.date(2026, 1, 10))]),
        ("2026-01-01", "2026-01-10", []),
        ("2026-01-01", "2026-01-05", [(datetime.date(2026, 1, 6), datetime.date(2026, 1, 10))]),
        ("2026-01-05", "2026-01-10", [(datetime.date(2026, 1, 1), datetime.date(2026, 1, 4))]),
        (
            "2026-01-04",
            "2026-01-06",
            [
                (datetime.date(2026, 1, 1), datetime.date(2026, 1, 3)),
                (datetime.date(2026, 1, 7), datetime.date(2026, 1, 10)),
            ],
        ),
    ],
)
def test_missing_ranges(first, last, expected):
    assert (
        _missing_ranges(first, last, datetime.date(2026, 1, 1), datetime.date(2026, 1, 10))
        == expected
    )
