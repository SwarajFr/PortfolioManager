"""Tests for the NSE multi-strategy screener."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from features.screener import settings as screener_settings


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
