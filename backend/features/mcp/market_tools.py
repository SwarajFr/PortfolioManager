"""MCP tool: live last-traded price for NSE symbols via the shared data service."""
from __future__ import annotations

from core.data import get_market_data

from .guards import needs_kite

_MAX_SYMBOLS = 50


@needs_kite
def quote(symbols: list[str]) -> dict:
    """Live last-traded price (LTP) for a list of NSE symbols.

    Symbols are plain tradingsymbols (e.g. "INFY", "TCS"); the NSE exchange
    prefix is added internally. Capped at 50 symbols per call. Symbols with no
    quote are returned in `not_found`.
    """
    if not symbols:
        return {"quotes": [], "not_found": []}

    cleaned = [str(s).strip().upper() for s in symbols if str(s).strip()][:_MAX_SYMBOLS]
    found = get_market_data().get_quote(cleaned)

    return {
        "quotes": [
            {"symbol": s, "ltp": round(found[s].last_price, 2)}
            for s in cleaned
            if s in found
        ],
        "not_found": [s for s in cleaned if s not in found],
    }


def register(mcp) -> None:
    mcp.tool(quote)
