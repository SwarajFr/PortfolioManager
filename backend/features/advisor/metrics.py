"""Pure per-stock indicators and the parameterised reachability model.

No I/O and no settings lookups: every function takes one symbol's OHLC frame
(indexed by date, columns open/high/low/close/volume) plus explicit parameters,
exactly like `features/screener/compute.py` — whose `sma`/`rsi` are reused here
rather than reimplemented.

The reachability model is the core of the "what can I buy for X% in Y months"
question. Nothing about the horizon or the target is baked in: both arrive as
arguments, and every derived figure re-scales with them.
"""
from __future__ import annotations

import math

import pandas as pd

from features.screener.compute import rsi, sma

#: NSE trades ~21 sessions a month. Used to turn a caller's horizon in months
#: into the number of bars the volatility model scales over.
TRADING_DAYS_PER_MONTH = 21

#: Lower bounds on `expected_move_pct / target_gain_pct`. A ratio below the
#: smallest bound is "too_slow" — the stock's own typical range cannot cover the
#: target in the time given, so recommending it would be wishful thinking.
DEFAULT_REACHABILITY_TIERS = {
    "stretch": 1.0,
    "plausible": 1.2,
    "comfortable": 2.0,
    "too_wild": 5.0,
}

#: Tiers we are willing to put in front of the user. "too_slow" cannot reach the
#: target; "too_wild" can, but only because the stock swings far enough to blow
#: through the stop first — the wrong instrument for a modest, dated goal.
RECOMMENDABLE_TIERS = ("stretch", "plausible", "comfortable")


def _last(series: pd.Series) -> float | None:
    """Final value of a series as a plain float, or None if absent/NaN."""
    if series is None or len(series) == 0:
        return None
    value = series.iloc[-1]
    return None if pd.isna(value) else float(value)


def true_range(df: pd.DataFrame) -> pd.Series:
    """Wilder's true range: the widest of today's range and the two gap ranges."""
    prev_close = df["close"].shift(1)
    return pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - prev_close).abs(),
            (df["low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)


def atr(df: pd.DataFrame, period: int = 14) -> float | None:
    """Latest Wilder-smoothed ATR in rupees."""
    if len(df) < period + 1:
        return None
    smoothed = true_range(df).ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    return _last(smoothed)


def atr_pct(df: pd.DataFrame, period: int = 14) -> float | None:
    """ATR as a percentage of the last close — daily volatility in % terms."""
    value = atr(df, period)
    close = _last(df["close"])
    if value is None or not close:
        return None
    return value / close * 100


def realized_vol_pct(df: pd.DataFrame, window: int = 60) -> float | None:
    """Annualised realised volatility (%) from daily close-to-close returns."""
    if len(df) < window + 1:
        return None
    daily = df["close"].pct_change().tail(window).std()
    if pd.isna(daily):
        return None
    return float(daily) * math.sqrt(252) * 100


def max_drawdown_pct(df: pd.DataFrame, window: int = 252) -> float | None:
    """Deepest peak-to-trough fall (%) inside the window, as a positive number."""
    closes = df["close"].tail(window)
    if len(closes) < 2:
        return None
    drawdown = closes / closes.cummax() - 1
    return abs(float(drawdown.min())) * 100


def dist_to_high_pct(df: pd.DataFrame, window: int = 252) -> float | None:
    """How far below the window's high the stock is trading, in % (0 = at the high)."""
    closes = df["close"].tail(window)
    if closes.empty:
        return None
    high = float(closes.max())
    close = _last(closes)
    if not high or close is None:
        return None
    return (high - close) / high * 100


def dist_to_ma_pct(df: pd.DataFrame, window: int) -> float | None:
    """Distance from the simple moving average in %, signed (negative = below)."""
    if len(df) < window:
        return None
    ma = _last(sma(df["close"], window))
    close = _last(df["close"])
    if not ma or close is None:
        return None
    return (close - ma) / ma * 100


def trailing_return_pct(df: pd.DataFrame, months: float, skip_months: float = 0) -> float | None:
    """Return (%) over `months`, optionally skipping the most recent `skip_months`.

    `skip_months=1` gives the 12-1 momentum convention: the last month is
    dropped because short-term reversal contaminates it.
    """
    lookback = round(months * TRADING_DAYS_PER_MONTH)
    skip = round(skip_months * TRADING_DAYS_PER_MONTH)
    if lookback <= 0 or len(df) < lookback + skip + 1:
        return None
    closes = df["close"]
    end = closes.iloc[-1 - skip] if skip else closes.iloc[-1]
    start = closes.iloc[-1 - skip - lookback]
    if pd.isna(start) or pd.isna(end) or not start:
        return None
    return (float(end) - float(start)) / float(start) * 100


def classify_reachability(ratio: float | None, tiers: dict[str, float] | None = None) -> str:
    """Map an expected-move / target ratio onto a named tier."""
    if ratio is None:
        return "unknown"
    bounds = tiers or DEFAULT_REACHABILITY_TIERS
    for tier, lower in sorted(bounds.items(), key=lambda kv: kv[1], reverse=True):
        if ratio >= lower:
            return tier
    return "too_slow"


def reachability(
    daily_atr_pct: float | None,
    horizon_months: float,
    target_gain_pct: float,
    tiers: dict[str, float] | None = None,
) -> dict:
    """Can this stock plausibly cover `target_gain_pct` within `horizon_months`?

    Scales the stock's own daily range over the horizon as a random walk
    (`atr% × √days`) and compares that budget to the target. Both inputs are the
    caller's — pass 5%/2mo and 10%/3mo and you get genuinely different answers.
    """
    horizon_days = max(1, round(horizon_months * TRADING_DAYS_PER_MONTH))
    if daily_atr_pct is None or target_gain_pct <= 0:
        return {
            "horizon_trading_days": horizon_days,
            "expected_move_pct": None,
            "ratio": None,
            "tier": "unknown",
        }

    expected_move = daily_atr_pct * math.sqrt(horizon_days)
    ratio = expected_move / target_gain_pct
    return {
        "horizon_trading_days": horizon_days,
        "expected_move_pct": round(expected_move, 2),
        "ratio": round(ratio, 2),
        "tier": classify_reachability(ratio, tiers),
    }


def trade_levels(
    price: float,
    daily_atr: float | None,
    target_gain_pct: float,
    atr_stop_multiple: float,
) -> dict:
    """Target, stop and reward:risk for one candidate at the caller's target.

    The target is arithmetic (`price × (1 + target%)`); the stop is volatility-
    based (`atr_stop_multiple × ATR` below entry), so a calm stock gets a tight
    stop and a jumpy one gets room to breathe.
    """
    target_price = price * (1 + target_gain_pct / 100)
    if not daily_atr or daily_atr <= 0:
        return {
            "target_price": round(target_price, 2),
            "stop_price": None,
            "risk_pct": None,
            "reward_risk": None,
        }

    stop_price = price - atr_stop_multiple * daily_atr
    risk_pct = (price - stop_price) / price * 100
    return {
        "target_price": round(target_price, 2),
        "stop_price": round(stop_price, 2),
        "risk_pct": round(risk_pct, 2),
        "reward_risk": round(target_gain_pct / risk_pct, 2) if risk_pct > 0 else None,
    }


def snapshot(df: pd.DataFrame, rsi_period: int = 14) -> dict:
    """Every indicator the advisor reasons with, for one stock, in one pass.

    Missing values stay None rather than raising: a freshly listed stock with
    60 bars still yields an ATR and a 3-month return, and the ranking layer
    simply has fewer reasons to work with.
    """
    if df is None or df.empty:
        return {}
    return {
        "price": _last(df["close"]),
        "atr": atr(df),
        "atr_pct": atr_pct(df),
        "realized_vol_pct": realized_vol_pct(df),
        "max_drawdown_pct": max_drawdown_pct(df),
        "dist_to_52w_high_pct": dist_to_high_pct(df, 252),
        "dist_to_ma50_pct": dist_to_ma_pct(df, 50),
        "dist_to_ma200_pct": dist_to_ma_pct(df, 200),
        "rsi": _last(rsi(df["close"], rsi_period)),
        "return_3m_pct": trailing_return_pct(df, 3),
        "return_6m_pct": trailing_return_pct(df, 6),
        "return_12m_1_pct": trailing_return_pct(df, 12, skip_months=1),
        "bars": len(df),
    }
