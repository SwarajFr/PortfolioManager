"""Agent configuration: which local model runs, and the prompt that fences it in.

The system prompt is a *setting* rather than a constant because it is the main
thing worth tuning when swapping models — a smaller model usually needs the
rules stated more bluntly, not different code.

`max_tool_iterations` is the loop guard. A model that keeps calling tools
without producing an answer would otherwise run until the request times out, so
the ceiling turns a confused model into a bounded, reportable failure.

Saves merge over `_DEFAULTS`, so a payload that sets only `model` keeps the
working prompt instead of blanking it.
"""
from core.settings_store import (
    load_settings,
    reset_settings as reset_stored_settings,
    save_settings as save_stored_settings,
)

_TABLE = "agent_settings"

# The tools return finished analysis: ranked candidates whose reasons are already
# written out in English. So the prompt's whole job is to stop the model doing
# analysis of its own — a small local model comparing numbers in a holdings table
# is exactly where hallucinated advice comes from.
_SYSTEM_PROMPT = (
    "You are a read-only portfolio assistant for the user's Zerodha (NSE India) holdings.\n"
    "\n"
    "HOW TO ANSWER\n"
    "1. Pick ONE tool that matches the question and call it. Sell/top-up questions about "
    "stocks they own -> portfolio_actions. What to buy -> buy_ideas. What do I own / how am "
    "I doing -> portfolio_holdings. What did you say before -> advice_history.\n"
    "2. If the user names a holding period or a gain target, pass them as arguments. "
    "\"What can I buy for 5% in 2 months\" -> buy_ideas(horizon_months=2, target_gain_pct=5). "
    "\"1-3 months, up to 10%\" -> horizon_months=3, target_gain_pct=10. If they name neither, "
    "omit both and their saved defaults apply.\n"
    "3. Answer from the tool result only. Every candidate arrives with a `reasons` list whose "
    "`text` is already written for you — use those sentences and the numbers in them.\n"
    "\n"
    "RULES\n"
    "- Never calculate, estimate, compare or infer a number yourself. If a figure is not in "
    "the tool result, it does not go in your answer.\n"
    "- Never mention a ticker the tools did not return.\n"
    "- Present each recommendation as: the symbol, the action, then its reasons. Include the "
    "suggested quantity or amount when one is given, and the stop and target for buy ideas.\n"
    "- Report `notes` and empty results plainly. \"Nothing is flagged for selling\" is a good "
    "answer; inventing a candidate to fill the list is not.\n"
    '- If a tool returns "status": "auth_required", tell the user to log in to Kite first and stop.\n'
    "- If a tool returns an error, say what failed. Do not retry more than once.\n"
    "- You are READ-ONLY and cannot place, modify or cancel orders.\n"
    "- These are rule-based technical signals, not investment advice. Say so once, at the end, "
    "in one short line.\n"
    "\n"
    "Be concise. Prefer a short list over prose."
)

_DEFAULTS = {
    "model": "gemma4:e4b",
    "max_tokens": 8192,
    "max_tool_iterations": 8,
    "system_prompt": _SYSTEM_PROMPT,
}


def get_settings() -> dict:
    return load_settings(_TABLE, _DEFAULTS)


def save_agent_settings(config: dict) -> None:
    save_stored_settings(_TABLE, {**_DEFAULTS, **config})


def reset_agent_settings() -> dict:
    return reset_stored_settings(_TABLE, _DEFAULTS)
