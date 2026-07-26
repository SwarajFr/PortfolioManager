"""MCP tool: live last-traded price for NSE symbols via the warm Kite session."""
from __future__ import annotations

from core.kite import get_kite

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
    keys = [f"NSE:{s}" for s in cleaned]
    data = get_kite().ltp(keys)

    quotes, not_found = [], []
    for sym in cleaned:
        entry = data.get(f"NSE:{sym}")
        if entry and entry.get("last_price") is not None:
            quotes.append({"symbol": sym, "ltp": round(float(entry["last_price"]), 2)})
        else:
            not_found.append(sym)
    return {"quotes": quotes, "not_found": not_found}


def register(mcp) -> None:
    mcp.tool(quote)
