"""OpenAI-format tool schemas + dispatch, reusing the read-only MCP tools.

A deliberate subset of what MCP exposes. The in-app agent runs on a small local
model, and every extra tool is one more chance for it to pick the wrong one —
so the tools here map one-to-one onto questions a user actually asks, and the
raw-data tools (quotes, diversification metrics) are left to MCP clients driving
a stronger model.
"""
from __future__ import annotations

import json

from features.mcp.advisor_tools import (
    advice_history,
    buy_ideas,
    investor_profile,
    portfolio_actions,
)
from features.mcp.portfolio_tools import portfolio_holdings

_HANDLERS = {
    "portfolio_actions": portfolio_actions,
    "buy_ideas": buy_ideas,
    "portfolio_holdings": portfolio_holdings,
    "advice_history": advice_history,
    "investor_profile": investor_profile,
}

_HORIZON_PARAM = {
    "type": "number",
    "description": (
        "Holding period in months, taken from the user's question "
        "(e.g. 2 for 'two months', 3 for '1-3 months'). Omit if they didn't say."
    ),
}

_TARGET_PARAM = {
    "type": "number",
    "description": (
        "Target gain in percent, taken from the user's question "
        "(e.g. 5 for '5%', 10 for 'up to 10%'). Omit if they didn't say."
    ),
}

SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "portfolio_actions",
            "description": (
                "What to SELL and what to TOP UP in the user's own portfolio, ranked, with "
                "the reasons already written out. Use this for any question about what to do "
                "with holdings they already own. Returns `sell` (positions flagged TRIM or "
                "EXIT with a suggested quantity) and `topup` (healthy holdings with room "
                "under the weight cap and a suggested amount). Never compute your own "
                "numbers from this — quote the `reasons[].text` and the figures given."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "horizon_months": _HORIZON_PARAM,
                    "target_gain_pct": _TARGET_PARAM,
                    "limit": {"type": "integer", "description": "max entries per list"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "buy_ideas",
            "description": (
                "NEW stocks to buy for a given gain target over a given holding period, from "
                "the cached NSE500 screen. Use this whenever the user asks what to buy. Pass "
                "their own numbers: 'what can I buy for 5% in 2 months' -> horizon_months=2, "
                "target_gain_pct=5. Each idea comes with an entry price, target, stop, "
                "reward:risk and written reasons. Does not cover stocks they already hold — "
                "use portfolio_actions for those."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "horizon_months": _HORIZON_PARAM,
                    "target_gain_pct": _TARGET_PARAM,
                    "limit": {"type": "integer", "description": "how many ideas to return"},
                    "exclude_held": {
                        "type": "boolean",
                        "description": "leave out stocks already in the portfolio (default true)",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "portfolio_holdings",
            "description": (
                "The user's current holdings with per-position P&L and portfolio totals. Use "
                "for 'what do I own', 'how am I doing', or any plain valuation question. For "
                "buy/sell/top-up advice use portfolio_actions instead. No arguments."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "advice_history",
            "description": (
                "Recommendations this assistant made previously, with the price at the time "
                "and the move since. Use for 'what did you tell me before' or 'how did your "
                "last calls do'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "how many entries"},
                    "kind": {
                        "type": "string",
                        "description": 'filter: "sell", "topup" or "buy"',
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "investor_profile",
            "description": (
                "The user's saved risk tolerance, default horizon and target, available "
                "capital and avoid-list. Use when they ask what their settings are, or when "
                "you need to know their risk appetite. No arguments."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
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
