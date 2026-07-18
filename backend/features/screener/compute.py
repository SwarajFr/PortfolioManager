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


def build_signals_row(df: pd.DataFrame, strategies: list) -> dict:
    """Per-stock {score, pass} for every strategy. Used to fill the cache's
    signals layer. `strategies` are engine.Strategy instances (duck-typed)."""
    row: dict[str, dict] = {}
    for st in strategies:
        score = st.compute(df).iloc[-1]
        passed = st.passes(df).iloc[-1]
        row[st.name] = {
            "score": None if pd.isna(score) else float(score),
            "pass": bool(passed) if pd.notna(passed) else False,
        }
    return row


def percentile_normalize(scores: pd.Series) -> pd.Series:
    """Cross-sectional rank in [0,1], monotonic in the raw score."""
    return scores.rank(pct=True)


def aggregate(norm: pd.DataFrame, weights: dict) -> pd.Series:
    """Weighted mean of normalized scores: Σ(wₛ·normₛ)/Σwₛ."""
    w = pd.Series(weights, dtype=float)
    return (norm[w.index] * w).sum(axis=1) / w.sum()


def k_of_n_match(passes: pd.DataFrame, k) -> pd.Series:
    """Row qualifies if it passes >= K of the given strategies.
    k == 'all' -> strict AND (all columns); int -> at least k."""
    counts = passes.astype(bool).sum(axis=1)
    if k == "all":
        return counts == passes.shape[1]
    return counts >= int(k)


def rank_and_fallback(
    agg: pd.Series, matched_mask: pd.Series, fallback_n: int
) -> tuple[list[str], bool]:
    """Matched sorted by aggregate desc; if empty, top fallback_n by aggregate."""
    matched = agg[matched_mask].sort_values(ascending=False)
    if len(matched) > 0:
        return list(matched.index), False
    return list(agg.sort_values(ascending=False).head(fallback_n).index), True
