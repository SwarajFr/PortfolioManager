from __future__ import annotations

import numpy as np
import pandas as pd

from core.data import InstrumentRef, get_market_data

from .engine import DiversityEngine
from .settings import get_settings

#: Correlation structure needs a long window; this is the deepest history any
#: feature asks for, so it also sets how far back the shared cache is filled.
MAX_LOOKBACK_DAYS = 900


def _empty_payload(excluded: list[str]) -> dict:
    """Well-formed empty response so the frontend shows an empty state, not a 500."""
    return {
        "scalars": {
            "num_positions": 0,
            "diversification_ratio": 0.0,
            "enb": 0.0,
            "effective_positions": 0.0,
            "normalized_entropy": 0.0,
            "weight_entropy": 0.0,
            "concentration_gap": 0.0,
            "portfolio_vol": 0.0,
            "portfolio_vol_daily": 0.0,
            "portfolio_variance": 0.0,
            "avg_correlation": 0.0,
            "max_correlation": 0.0,
        },
        "max_correlation_pair": None,
        "principal_risk_contributions": [],
        "principal_bets": [],
        "correlation": {"symbols": [], "matrix": []},
        "tickers_excluded": list(excluded),
    }


def _refs(holdings: pd.DataFrame) -> list[InstrumentRef]:
    """Holdings already carry an instrument token, so history needs no lookup."""
    return [
        InstrumentRef(symbol=str(row.tradingsymbol), token=int(row.instrument_token))
        for row in holdings.itertuples()
    ]


def _weights(holdings: pd.DataFrame, prices: pd.DataFrame) -> dict[str, float]:
    """Position value as a fraction of the portfolio, for priced tickers only."""
    value_map: dict[str, float] = {}
    for _, row in holdings.iterrows():
        symbol = str(row["tradingsymbol"])
        if symbol in prices.columns:
            value_map[symbol] = float(row.get("last_price", 0)) * float(
                row.get("quantity", 0)
            )

    total_value = sum(value_map.values())
    if total_value == 0:
        return {}
    return {symbol: value / total_value for symbol, value in value_map.items()}


def get_diversity_analysis() -> dict:
    """Fetch holdings + prices, derive returns, and run the descriptive engine.

    The engine takes returns + a weights Series, so the prices→log-returns
    conversion and the min-history filter (tickers with < long_window days of
    data are dropped) live here, in the data-orchestration layer.
    """
    settings = get_settings()
    long_window = int(settings.get("long_window", 90))

    market_data = get_market_data()
    holdings = market_data.get_holdings()
    if holdings.empty:
        return _empty_payload([])

    prices = market_data.get_close_frame(
        _refs(holdings), lookback_days=MAX_LOOKBACK_DAYS
    )
    weights = _weights(holdings, prices)
    if prices.empty or not weights:
        return _empty_payload([])

    returns = np.log1p(prices.pct_change())

    # Keep only weighted tickers with enough history; report the rest as excluded.
    surviving = [
        c
        for c in returns.columns
        if c in weights and int(returns[c].notna().sum()) >= long_window
    ]
    excluded = [c for c in returns.columns if c not in surviving]
    returns = returns[surviving].dropna(how="any")

    if returns.shape[1] < 2 or len(returns) < long_window:
        return _empty_payload(excluded)

    w = pd.Series({t: weights[t] for t in returns.columns})

    result = DiversityEngine().run(returns, w)
    result.tickers_excluded = excluded
    return result.to_dict()
