"""MCP tool: live holdings, formatted and rounded."""
from __future__ import annotations

from features.portfolio.data import get_holdings

from .guards import needs_kite


def _empty_totals() -> dict:
    return {"value": 0.0, "invested": 0.0, "pnl": 0.0, "pnl_pct": 0.0, "num_holdings": 0}


@needs_kite
def portfolio_holdings() -> dict:
    """Current live holdings with per-position P&L, plus portfolio totals.

    Returns rows sorted by market value (largest first). Amounts are rounded;
    instrument tokens and raw broker fields are omitted for a compact payload.
    """
    df = get_holdings()
    if df is None or df.empty:
        return {"holdings": [], "totals": _empty_totals()}

    rows = []
    for _, r in df.iterrows():
        qty = float(r["quantity"])
        avg = float(r["average_price"])
        ltp = float(r["last_price"])
        value = ltp * qty
        invested = avg * qty
        pnl = value - invested
        rows.append({
            "symbol": str(r["tradingsymbol"]),
            "qty": qty,
            "avg_price": round(avg, 2),
            "ltp": round(ltp, 2),
            "value": round(value, 2),
            "pnl": round(pnl, 2),
            "pnl_pct": round((pnl / invested * 100) if invested else 0.0, 2),
        })

    rows.sort(key=lambda h: h["value"], reverse=True)
    total_value = sum(h["value"] for h in rows)
    total_invested = sum(h["avg_price"] * h["qty"] for h in rows)
    total_pnl = total_value - total_invested
    return {
        "holdings": rows,
        "totals": {
            "value": round(total_value, 2),
            "invested": round(total_invested, 2),
            "pnl": round(total_pnl, 2),
            "pnl_pct": round((total_pnl / total_invested * 100) if total_invested else 0.0, 2),
            "num_holdings": len(rows),
        },
    }


def register(mcp) -> None:
    mcp.tool(portfolio_holdings)
