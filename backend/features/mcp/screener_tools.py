"""MCP tool: run one screener strategy, cache-only, top-N + total_matches."""
from __future__ import annotations

from features.screener.engine import REGISTRY
from features.screener.service import get_individual

_SUPPORTED_UNIVERSES = ["NSE500"]


def screen_strategy(name: str, universe: str = "NSE500", limit: int = 20) -> dict:
    """Run a single technical screening strategy over the cached NSE500 universe.

    Reads only the screener cache (no live market calls). Returns the top-`limit`
    passing symbols ranked by raw score, plus the full `total_matches` count.
    Valid `name` values: ma_crossover, momentum_12_1, breakout, rsi_reversion,
    high_52w. Only the NSE500 universe is supported.
    """
    if name not in REGISTRY:
        return {"error": f"Unknown strategy: {name!r}", "valid_strategies": list(REGISTRY)}
    if universe not in _SUPPORTED_UNIVERSES:
        return {"error": f"Unsupported universe: {universe!r}", "supported_universes": _SUPPORTED_UNIVERSES}

    data = get_individual(name)
    results = data.get("results", [])
    out = {
        "strategy": name,
        "universe": universe,
        "total_matches": len(results),
        "top": results[: max(0, int(limit))],
        "last_updated": data.get("last_updated"),
    }
    if not results:
        out["note"] = "No matches in cache. The screener cache may be unseeded — log in to trigger a refresh."
    return out


def register(mcp) -> None:
    mcp.tool(screen_strategy)
