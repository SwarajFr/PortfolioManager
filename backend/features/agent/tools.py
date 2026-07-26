"""OpenAI-format tool schemas + dispatch, reusing the read-only MCP tools."""
from __future__ import annotations

import json

from features.mcp.fragility_tools import portfolio_metrics
from features.mcp.market_tools import quote
from features.mcp.portfolio_tools import portfolio_holdings
from features.mcp.screener_tools import screen_strategy

_HANDLERS = {
    "portfolio_holdings": portfolio_holdings,
    "portfolio_metrics": portfolio_metrics,
    "screen_strategy": screen_strategy,
    "quote": quote,
}

SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "portfolio_holdings",
            "description": "Current live holdings with per-position P&L and portfolio totals. No arguments.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "portfolio_metrics",
            "description": (
                "Diversification metrics for the portfolio: diversification ratio, effective number "
                "of bets (ENB), weight entropy, average/max correlation, concentration gap. No arguments."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "screen_strategy",
            "description": (
                "Run one NSE500 technical screener strategy and return the top matches with a total count. "
                "Valid names: ma_crossover, momentum_12_1, breakout, rsi_reversion, high_52w."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "strategy name"},
                    "universe": {"type": "string", "description": "only NSE500 is supported"},
                    "limit": {"type": "integer", "description": "max results to return"},
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "quote",
            "description": 'Live last-traded price for a list of NSE symbols, e.g. ["INFY", "TCS"].',
            "parameters": {
                "type": "object",
                "properties": {
                    "symbols": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "NSE tradingsymbols",
                    }
                },
                "required": ["symbols"],
            },
        },
    },
]


def dispatch(name: str, arguments_json: str) -> dict:
    """Route a tool call to its handler. Never raises — a failure is returned as {'error': ...}."""
    handler = _HANDLERS.get(name)
    if handler is None:
        return {"error": f"unknown tool: {name}"}
    try:
        args = json.loads(arguments_json or "{}")
    except json.JSONDecodeError as e:
        return {"error": f"invalid tool arguments: {e}"}
    try:
        return handler(**args)
    except Exception as e:  # a broken tool must not kill the agent loop
        return {"error": f"{type(e).__name__}: {e}"}
