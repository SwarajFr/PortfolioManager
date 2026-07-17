"""Pure computation layer for the NSE screener.

Per-stock strategy functions take one symbol's OHLC DataFrame plus explicit
params (params come from settings via the engine — never hardcoded here) and
return a pandas Series aligned to the input index. Cross-stock functions
(percentile_normalize, aggregate, k_of_n_match, rank_and_fallback,
build_signals_row) are added in the next task.
"""
from __future__ import annotations

import pandas as pd


def sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window).mean()


def rsi(close: pd.Series, period: int) -> pd.Series:
    """Wilder's RSI."""
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


# 1. MA crossover
def ma_crossover_score(df: pd.DataFrame, fast: int, slow: int) -> pd.Series:
    f = sma(df["close"], fast)
    s = sma(df["close"], slow)
    return (f - s) / s


def ma_crossover_pass(df: pd.DataFrame, fast: int, slow: int) -> pd.Series:
    return sma(df["close"], fast) > sma(df["close"], slow)


# 2. Momentum 12-1
def momentum_score(df: pd.DataFrame, lookback: int, skip: int) -> pd.Series:
    c = df["close"]
    return c.shift(skip) / c.shift(lookback) - 1


def momentum_pass(df: pd.DataFrame, lookback: int, skip: int) -> pd.Series:
    return momentum_score(df, lookback, skip) > 0


# 3. Breakout (prior-window high)
# NOTE: the `.shift(1)` is REQUIRED — it makes the rolling max cover the PRIOR
# window (excluding today's own bar), which is the definition of a breakout.
# Do NOT remove it to make a test pass; if the breakout test fails, the test
# DATA is wrong (slope too shallow), not this logic.
def breakout_score(df: pd.DataFrame, n_high: int) -> pd.Series:
    prior_high = df["high"].rolling(n_high).max().shift(1)
    return df["close"] / prior_high


def breakout_pass(df: pd.DataFrame, n_high: int) -> pd.Series:
    prior_high = df["high"].rolling(n_high).max().shift(1)
    return df["close"] > prior_high


# 4. RSI reversion (contrarian: weakness scores as strength)
def rsi_reversion_score(df: pd.DataFrame, rsi_period: int) -> pd.Series:
    return 100 - rsi(df["close"], rsi_period)


def rsi_reversion_pass(df: pd.DataFrame, rsi_period: int, oversold: int) -> pd.Series:
    return rsi(df["close"], rsi_period) < oversold


# 5. 52-week high proximity
def high_52w_score(df: pd.DataFrame, window: int) -> pd.Series:
    return df["close"] / df["high"].rolling(window).max()


def high_52w_pass(df: pd.DataFrame, window: int, proximity: float) -> pd.Series:
    return df["close"] >= proximity * df["high"].rolling(window).max()
