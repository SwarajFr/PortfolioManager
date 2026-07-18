from __future__ import annotations

import numpy as np
import pandas as pd

from .data import get_holdings, get_prices
from .engine import DiversityEngine
from .settings import get_settings


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


def get_diversity_analysis() -> dict:
    """Fetch holdings + prices, derive returns, and run the descriptive engine.

    The engine takes returns + a weights Series, so the prices→log-returns
    conversion and the min-history filter (tickers with < long_window days of
    data are dropped) live here, in the data-orchestration layer.
    """
    settings = get_settings()
    long_window = int(settings.get("long_window", 90))

    holdings = get_holdings()
    prices, weights = get_prices(holdings)
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
