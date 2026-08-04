"""MCP tools that answer whole questions rather than returning raw tables.

Each tool returns a ranked list where every entry already carries its reasons,
computed in Python. The calling model's job is to narrate them, not to derive
them — which is what lets a small local model give a trustworthy answer.
"""
from __future__ import annotations

from features.advisor.service import (
    advice_history as _advice_history,
    buy_ideas as _buy_ideas,
    investor_profile as _investor_profile,
    portfolio_actions as _portfolio_actions,
)

from .guards import needs_kite


@needs_kite
def portfolio_actions(
    horizon_months: float | None = None,
    target_gain_pct: float | None = None,
    limit: int | None = None,
) -> dict:
    """What to sell and what to top up in the user's portfolio, with reasons.

    Answers "which stocks should I sell or add to?" in a single call. Returns
    two ranked lists:

    - `sell` — positions the rule-based exit engine scores at TRIM or EXIT,
      worst first, each with a suggested quantity and the KPIs that triggered it
      (loss severity, volatility vs. the portfolio median, risk-adjusted return,
      trend break, over-concentration).
    - `topup` — holdings that are clean on every exit check, technically strong,
      and still under the user's single-holding weight cap, with a suggested
      rupee amount. These are adds to strength, never averaging down.

    Every entry has `reasons[]`, each with a ready-written `text`. Quote those
    figures; do not compute your own. `horizon_months` and `target_gain_pct`
    tune the top-up side — pass whatever the user asked for (e.g. 2 and 5 for
    "5% in two months"); omit them to use the user's saved defaults.
    """
    return _portfolio_actions(horizon_months, target_gain_pct, limit)


@needs_kite
def buy_ideas(
    horizon_months: float | None = None,
    target_gain_pct: float | None = None,
    limit: int = 10,
    exclude_held: bool = True,
) -> dict:
    """New stocks to buy for a given gain target over a given holding period.

    Answers "what should I buy for X% in Y months?". Screens the cached NSE500
    with the technical strategies that suit the horizon (breakouts and mean
    reversion for short holds, momentum for long ones), then keeps only names
    whose own typical price swing can realistically cover the target in the time
    available. Each idea carries an entry, a target, an ATR-based stop, a
    reward:risk ratio and `reasons[]` with ready-written `text`.

    Pass the user's own numbers: `horizon_months=2, target_gain_pct=5` for "5%
    in two months". Nothing is hardcoded — different inputs give genuinely
    different lists. Omit both to use the user's saved defaults.

    `excluded` summarises what was filtered out and why, including names that
    move too slowly to reach the target. Reads only the screener cache, so it
    never blocks on the broker.
    """
    return _buy_ideas(horizon_months, target_gain_pct, limit, exclude_held)


@needs_kite
def advice_history(limit: int = 20, kind: str | None = None) -> dict:
    """Past recommendations from this advisor, with what the price did since.

    Answers "what did you tell me last month, and how did it go?". Each entry
    records the date, the symbol, the price at the time and a one-line rationale,
    plus the current price and the move since. Filter with `kind`: "sell",
    "topup" or "buy".
    """
    return _advice_history(limit, kind)


@needs_kite
def investor_profile() -> dict:
    """The user's saved risk profile, default horizon, target gain and exclusions.

    Read this before giving recommendations so the answer respects their risk
    tolerance, the stocks they never want suggested, and the capital they
    actually have available. The defaults it returns are fallbacks only — a
    horizon or target named in the user's question always wins.
    """
    return _investor_profile()


def register(mcp) -> None:
    mcp.tool(portfolio_actions)
    mcp.tool(buy_ideas)
    mcp.tool(advice_history)
    mcp.tool(investor_profile)
