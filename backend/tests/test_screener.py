"""Tests for the NSE multi-strategy screener."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from features.screener import settings as screener_settings
from features.screener import cache as screener_cache


@pytest.fixture()
def db(tmp_path):
    path = str(tmp_path / "screener_cache.db")
    screener_cache.init(path)
    return path


def test_defaults_have_all_config_keys():
    d = screener_settings.get_settings()
    assert d["strategies"]["ma_crossover"] == {"fast": 20, "slow": 50}
    assert d["strategies"]["momentum_12_1"] == {"lookback": 252, "skip": 21}
    assert d["strategies"]["breakout"] == {"n_high": 20}
    assert d["strategies"]["rsi_reversion"] == {"rsi_period": 14, "oversold": 30}
    assert d["strategies"]["high_52w"] == {"window": 252, "proximity": 0.90}
    assert d["screener"]["default_k"] == "all"
    assert d["screener"]["fallback_n"] == 10
    assert d["screener"]["normalization"] == "percentile"
    assert d["universe"]["segment"] == "NSE"
    assert d["data"]["seed_lookback_days"] == 500
    assert d["data"]["kite_rate_limit_rps"] == 3.0


def test_upsert_candles_is_append_only(db):
    rows = [
        {"date": "2026-01-01", "open": 1, "high": 2, "low": 1, "close": 1.5, "volume": 10},
        {"date": "2026-01-02", "open": 1.5, "high": 2.5, "low": 1.4, "close": 2.0, "volume": 12},
    ]
    assert screener_cache.upsert_candles(db, "RELIANCE", rows) == 2
    # Re-inserting the same dates + one new date appends only the new one.
    more = rows + [{"date": "2026-01-03", "open": 2, "high": 3, "low": 2, "close": 2.5, "volume": 9}]
    assert screener_cache.upsert_candles(db, "RELIANCE", more) == 1
    df = screener_cache.read_candles(db, "RELIANCE")
    assert list(df["date"]) == ["2026-01-01", "2026-01-02", "2026-01-03"]
    assert screener_cache.last_candle_date(db, "RELIANCE") == "2026-01-03"


def test_signals_roundtrip(db):
    screener_cache.upsert_signal(
        db, "TCS", "2026-01-03", {"ma_crossover": 0.1}, {"ma_crossover": True}
    )
    rows = screener_cache.read_signals(db)
    assert rows == [
        {"symbol": "TCS", "as_of_date": "2026-01-03",
         "scores": {"ma_crossover": 0.1}, "passes": {"ma_crossover": True}}
    ]


def test_meta_roundtrip(db):
    assert screener_cache.get_meta(db, "seed_complete") is None
    screener_cache.set_meta(db, "seed_complete", "1")
    assert screener_cache.get_meta(db, "seed_complete") == "1"


from features.screener import compute


def _uptrend_df(n=300):
    """Strictly rising close/high — MA fast>slow, momentum>0, near highs, and a
    genuine breakout. The slope MUST be steep enough that the daily close
    increment exceeds the +1 high offset; otherwise yesterday's high exceeds
    today's close and `breakout_pass` (which compares to the PRIOR window via
    shift(1)) is correctly False. linspace(100, 600, 300) gives a ~1.67/day
    increment > 1.0, so today's close clears the prior 20-day high."""
    idx = pd.date_range("2025-01-01", periods=n, freq="D")
    close = pd.Series(np.linspace(100, 600, n), index=idx)
    high = close + 1.0
    low = close - 1.0
    return pd.DataFrame(
        {"open": close, "high": high, "low": low, "close": close, "volume": 1000.0},
        index=idx,
    )


def test_ma_crossover_positive_case():
    df = _uptrend_df()
    assert bool(compute.ma_crossover_pass(df, 20, 50).iloc[-1]) is True
    assert compute.ma_crossover_score(df, 20, 50).iloc[-1] > 0


def test_momentum_positive_case():
    df = _uptrend_df()
    assert bool(compute.momentum_pass(df, 252, 21).iloc[-1]) is True
    assert compute.momentum_score(df, 252, 21).iloc[-1] > 0


def test_breakout_positive_case():
    df = _uptrend_df()
    # Rising series: today's close exceeds the prior 20-day high window.
    assert bool(compute.breakout_pass(df, 20).iloc[-1]) is True
    assert compute.breakout_score(df, 20).iloc[-1] > 1.0


def test_rsi_reversion_positive_case():
    # Strictly falling close -> RSI near 0 -> oversold, high contrarian score.
    idx = pd.date_range("2025-01-01", periods=100, freq="D")
    close = pd.Series(np.linspace(200, 100, 100), index=idx)
    df = pd.DataFrame(
        {"open": close, "high": close + 1, "low": close - 1, "close": close, "volume": 1.0},
        index=idx,
    )
    assert bool(compute.rsi_reversion_pass(df, 14, 30).iloc[-1]) is True
    assert compute.rsi_reversion_score(df, 14).iloc[-1] > 70


def test_high_52w_positive_case():
    df = _uptrend_df()
    assert bool(compute.high_52w_pass(df, 252, 0.90).iloc[-1]) is True
    assert compute.high_52w_score(df, 252).iloc[-1] == pytest.approx(1.0, abs=0.02)


def test_percentile_normalize_range_and_monotonic():
    s = pd.Series([10.0, 20.0, 30.0, 40.0], index=["a", "b", "c", "d"])
    norm = compute.percentile_normalize(s)
    assert norm.min() >= 0.0 and norm.max() <= 1.0
    # Monotonic: order preserved.
    assert list(norm.sort_values().index) == ["a", "b", "c", "d"]


def test_aggregate_equal_weight_equals_mean():
    norm = pd.DataFrame(
        {"x": [0.2, 0.8], "y": [0.4, 0.6]}, index=["a", "b"]
    )
    agg = compute.aggregate(norm, {"x": 1.0, "y": 1.0})
    assert agg["a"] == pytest.approx((0.2 + 0.4) / 2)
    assert agg["b"] == pytest.approx((0.8 + 0.6) / 2)


def test_k_of_n_all_is_strict_and():
    passes = pd.DataFrame(
        {"x": [True, True, False], "y": [True, False, False]},
        index=["a", "b", "c"],
    )
    match = compute.k_of_n_match(passes, "all")
    assert list(match) == [True, False, False]


def test_k_of_n_one_is_union():
    passes = pd.DataFrame(
        {"x": [True, True, False], "y": [True, False, False]},
        index=["a", "b", "c"],
    )
    match = compute.k_of_n_match(passes, 1)
    assert list(match) == [True, True, False]


def test_rank_and_fallback_triggers_on_empty_match():
    agg = pd.Series([0.9, 0.5, 0.7, 0.1, 0.3], index=["a", "b", "c", "d", "e"])
    matched = pd.Series([False] * 5, index=agg.index)
    ranked, is_fallback = compute.rank_and_fallback(agg, matched, fallback_n=3)
    assert is_fallback is True
    assert ranked == ["a", "c", "b"]  # top-3 by aggregate desc


def test_rank_and_fallback_returns_matches_when_present():
    agg = pd.Series([0.9, 0.5, 0.7], index=["a", "b", "c"])
    matched = pd.Series([True, False, True], index=agg.index)
    ranked, is_fallback = compute.rank_and_fallback(agg, matched, fallback_n=10)
    assert is_fallback is False
    assert ranked == ["a", "c"]


from features.screener import engine


def test_registry_has_all_five_strategies():
    assert set(engine.REGISTRY) == {
        "ma_crossover", "momentum_12_1", "breakout", "rsi_reversion", "high_52w"
    }


def test_build_strategies_pulls_params_from_settings():
    s = screener_settings.get_settings()
    strategies = engine.build_strategies(s)
    by_name = {st.name: st for st in strategies}
    assert by_name["ma_crossover"].params == {"fast": 20, "slow": 50}


def test_run_individual_ranks_passing_by_raw_score():
    scores = pd.DataFrame({"ma_crossover": [0.3, 0.1, 0.9]}, index=["a", "b", "c"])
    passes = pd.DataFrame({"ma_crossover": [True, False, True]}, index=["a", "b", "c"])
    out = engine.run_individual("ma_crossover", scores, passes)
    assert [r["symbol"] for r in out] == ["c", "a"]  # b filtered (no pass)
    assert out[0]["score"] == 0.9


def test_run_combined_equal_weight_and_fallback():
    scores = pd.DataFrame(
        {"ma_crossover": [0.9, 0.2], "breakout": [0.1, 0.8]}, index=["a", "b"]
    )
    passes = pd.DataFrame(
        {"ma_crossover": [False, False], "breakout": [False, False]},
        index=["a", "b"],
    )
    out = engine.run_combined(
        ["ma_crossover", "breakout"], {}, "all", 2, scores, passes
    )
    assert out["is_fallback"] is True
    assert len(out["results"]) == 2  # exactly fallback_n rows


import datetime

from features.screener import data as screener_data


def test_filter_universe_keeps_only_nse500_equities():
    # Kite instruments() uses segment "NSE" (not "NSE-EQ") for cash equities.
    instruments = [
        {"tradingsymbol": "RELIANCE", "instrument_token": 1, "segment": "NSE"},
        {"tradingsymbol": "TCS", "instrument_token": 2, "segment": "NSE"},
        {"tradingsymbol": "NIFTY 50", "instrument_token": 3, "segment": "INDICES"},
        {"tradingsymbol": "PENNYX", "instrument_token": 4, "segment": "NSE"},
    ]
    out = screener_data.filter_universe(instruments, "NSE", {"RELIANCE", "TCS"})
    assert set(out["tradingsymbol"]) == {"RELIANCE", "TCS"}
    assert 3 not in list(out["instrument_token"])  # index dropped
    assert 4 not in list(out["instrument_token"])  # non-member dropped


def test_refresh_appends_only_new_dated_candles(db, monkeypatch, tmp_path):
    # Point settings at the temp cache DB.
    s = screener_settings.get_settings()
    s["data"]["cache_path"] = db
    monkeypatch.setattr(screener_data.settings, "get_settings", lambda: s)

    universe = pd.DataFrame(
        {"tradingsymbol": ["RELIANCE"], "instrument_token": [1]}
    )
    # Seed one candle at 2026-01-01.
    screener_cache.upsert_candles(
        db, "RELIANCE",
        [{"date": "2026-01-01", "open": 1, "high": 2, "low": 1, "close": 1.5, "volume": 5}],
    )

    calls = {}

    def fake_fetch(token, from_date, to_date):
        calls["from_date"] = from_date
        # Kite would only return candles from `from_date` onward.
        return [
            {"date": datetime.date(2026, 1, 2), "open": 1.5, "high": 2.5,
             "low": 1.4, "close": 2.0, "volume": 6}
        ]

    result = screener_data.refresh_ohlc(
        universe_df=universe, fetch=fake_fetch, today=datetime.date(2026, 1, 2)
    )
    # Incremental fetch starts strictly after the last stored date.
    assert calls["from_date"] == datetime.date(2026, 1, 2)
    df = screener_cache.read_candles(db, "RELIANCE")
    assert list(df["date"]) == ["2026-01-01", "2026-01-02"]  # appended, not backfilled
    assert result["updated"] == 1


def test_refresh_skips_and_logs_missing_symbol(db, monkeypatch):
    s = screener_settings.get_settings()
    s["data"]["cache_path"] = db
    monkeypatch.setattr(screener_data.settings, "get_settings", lambda: s)
    universe = pd.DataFrame({"tradingsymbol": ["DELISTED"], "instrument_token": [99]})

    def boom(token, from_date, to_date):
        raise Exception("instrument not found")

    result = screener_data.refresh_ohlc(
        universe_df=universe, fetch=boom, today=datetime.date(2026, 1, 2)
    )
    assert result["skipped"] == 1  # did not crash


from features.screener import service as screener_service


def _seed_signals(db):
    # Every cached symbol carries ALL registered strategies, exactly as
    # production does (build_signals_row computes every strategy per symbol).
    # AAA passes only ma_crossover, BBB passes only breakout.
    screener_cache.upsert_signal(
        db, "AAA", "2026-01-03",
        {"ma_crossover": 0.9, "momentum_12_1": 0.5, "breakout": 0.1,
         "rsi_reversion": 0.3, "high_52w": 0.4},
        {"ma_crossover": True, "momentum_12_1": False, "breakout": False,
         "rsi_reversion": False, "high_52w": False},
    )
    screener_cache.upsert_signal(
        db, "BBB", "2026-01-03",
        {"ma_crossover": 0.2, "momentum_12_1": 0.6, "breakout": 0.8,
         "rsi_reversion": 0.7, "high_52w": 0.5},
        {"ma_crossover": False, "momentum_12_1": False, "breakout": True,
         "rsi_reversion": False, "high_52w": False},
    )


def test_scan_reads_cache_without_recomputing(db, monkeypatch):
    s = screener_settings.get_settings()
    s["data"]["cache_path"] = db
    monkeypatch.setattr(screener_service.settings, "get_settings", lambda: s)
    _seed_signals(db)

    calls = {"n": 0}
    real = compute.build_signals_row

    def spy(*a, **k):
        calls["n"] += 1
        return real(*a, **k)

    monkeypatch.setattr(compute, "build_signals_row", spy)

    out = screener_service.run_scan(strategies=["ma_crossover", "breakout"], k=1)
    assert calls["n"] == 0  # screen reads cached signals; no per-stock recompute
    assert {r["symbol"] for r in out["results"]} == {"AAA", "BBB"}


def test_scan_payload_is_json_serializable(db, monkeypatch):
    s = screener_settings.get_settings()
    s["data"]["cache_path"] = db
    monkeypatch.setattr(screener_service.settings, "get_settings", lambda: s)
    _seed_signals(db)
    out = screener_service.run_scan()
    json.dumps(out)  # must not raise


def test_status_reports_seed_state(db, monkeypatch):
    s = screener_settings.get_settings()
    s["data"]["cache_path"] = db
    monkeypatch.setattr(screener_service.settings, "get_settings", lambda: s)
    screener_cache.set_meta(db, "seed_complete", "1")
    status = screener_service.get_status()
    assert status["seed_complete"] is True
    json.dumps(status)


def test_routes_module_exposes_all_endpoints():
    from features.screener import routes as screener_routes

    paths = {r.path for r in screener_routes.router.routes}
    assert paths == {"/strategies", "/individual", "/scan", "/refresh", "/status"}


# ── Post-review hardening ────────────────────────────────────────────────────
def test_run_scan_unknown_strategy_raises_value_error(db, monkeypatch):
    s = screener_settings.get_settings()
    s["data"]["cache_path"] = db
    monkeypatch.setattr(screener_service.settings, "get_settings", lambda: s)
    _seed_signals(db)
    # A misspelled / unregistered strategy is a client error, not a 500.
    with pytest.raises(ValueError):
        screener_service.run_scan(strategies=["ma_crossover", "momentum"])  # typo


def test_run_scan_drops_registered_but_uncached_strategy(db, monkeypatch):
    s = screener_settings.get_settings()
    s["data"]["cache_path"] = db
    monkeypatch.setattr(screener_service.settings, "get_settings", lambda: s)
    # Only ma_crossover cached — simulates a registered strategy not yet seeded.
    screener_cache.upsert_signal(db, "AAA", "2026-01-03",
                                 {"ma_crossover": 0.9}, {"ma_crossover": True})
    screener_cache.upsert_signal(db, "BBB", "2026-01-03",
                                 {"ma_crossover": 0.2}, {"ma_crossover": False})
    out = screener_service.run_scan(strategies=["ma_crossover", "breakout"])
    assert out["selected"] == ["ma_crossover"]  # breakout dropped, no KeyError/500
    json.dumps(out)


def test_cache_uses_wal_journal(db):
    import sqlite3

    conn = sqlite3.connect(db)
    mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    conn.close()
    assert mode.lower() == "wal"  # read-during-refresh must not block


def test_run_individual_nan_score_serializes_as_null():
    # A passing symbol whose cached score is NaN must become null, not a bare
    # NaN token that strict JSON.parse on the client would reject.
    scores = pd.DataFrame({"ma_crossover": [np.nan, 0.5]}, index=["AAA", "BBB"])
    passes = pd.DataFrame({"ma_crossover": [True, True]}, index=["AAA", "BBB"])
    out = engine.run_individual("ma_crossover", scores, passes)
    by_sym = {r["symbol"]: r["score"] for r in out}
    assert by_sym["AAA"] is None
    assert "NaN" not in json.dumps(out)


def test_locked_refresh_logs_and_releases_on_error(monkeypatch):
    def boom():
        raise RuntimeError("refresh blew up")

    monkeypatch.setattr(screener_service, "_refresh_core", boom)
    assert screener_service._refresh_lock.acquire(blocking=False)
    screener_service._locked_refresh()  # must swallow + release, not raise
    assert not screener_service._refresh_lock.locked()
