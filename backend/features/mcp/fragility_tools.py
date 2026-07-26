"""MCP tool: the five-metric diversification suite as a compact summary."""
from __future__ import annotations

from features.fragility.service import get_diversity_analysis

from .guards import needs_kite


@needs_kite
def portfolio_metrics() -> dict:
    """Descriptive diversification metrics for the current portfolio.

    Compact summary of the five-metric suite (diversification ratio, effective
    number of bets, weight entropy, correlation structure, concentration gap).
    Raw covariance/correlation matrices are intentionally omitted.
    """
    full = get_diversity_analysis()
    s = full.get("scalars", {})

    if int(s.get("num_positions", 0)) == 0:
        return {
            "num_positions": 0,
            "note": "Insufficient holdings or price history to compute diversification metrics.",
            "tickers_excluded": full.get("tickers_excluded", []),
        }

    bets = full.get("principal_bets") or []
    return {
        "num_positions": s["num_positions"],
        "diversification_ratio": s["diversification_ratio"],
        "enb": s["enb"],
        "effective_positions": s["effective_positions"],
        "normalized_entropy": s["normalized_entropy"],
        "weight_entropy": s["weight_entropy"],
        "concentration_gap": s["concentration_gap"],
        "portfolio_vol_annualized": s["portfolio_vol"],
        "avg_correlation": s["avg_correlation"],
        "max_correlation": s["max_correlation"],
        "max_correlation_pair": full.get("max_correlation_pair"),
        "top_principal_bet": bets[0] if bets else [],
        "tickers_excluded": full.get("tickers_excluded", []),
    }


def register(mcp) -> None:
    mcp.tool(portfolio_metrics)
