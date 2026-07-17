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
    assert d["universe"]["segment"] == "NSE-EQ"
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
