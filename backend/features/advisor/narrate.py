"""Reason code → English sentence.

The ranking layer decides *what* is true and attaches numbers; this module
decides how to say it. Keeping them apart means the ranking tests assert on
codes and values rather than on prose, and the wording can change without
touching a single threshold.

It also pins down where an answer's reasoning comes from: the LLM narrates these
sentences, it does not compose them. Every figure in a recommendation was
computed in Python before the model ever saw it.
"""
from __future__ import annotations

TEMPLATES: dict[str, str] = {
    # ── sell ────────────────────────────────────────────────────────────────
    # `value` stays signed for machine consumers; the sentence uses the
    # magnitude so it never reads "Down -40%".
    "loss_severity": "Down {drop}% against your average price of ₹{avg_price} (now ₹{ltp}).",
    "risk_vs_median": (
        "Annualised volatility {value}% versus a {median}% median across your holdings "
        "— {ratio}x the portfolio norm."
    ),
    "risk_vs_median_simple": (
        "Annualised volatility {value}% — materially above the rest of your holdings."
    ),
    "risk_adj_inefficiency": (
        "Return per unit of risk is {value}, below your portfolio median of {median} "
        "— it is not paying for the risk it carries."
    ),
    "trend_weakness_both": "Trading below both its 50-day (₹{ma50}) and 200-day (₹{ma200}) averages.",
    "trend_weakness_short": "Trading below its 50-day average of ₹{ma50}.",
    "concentration": "At {value}% of the portfolio it is above the {limit}% single-holding cap.",
    "correlation_cluster": (
        "Moves almost in step with {partner} (correlation {value}) — together they are one bet, not two."
    ),
    "position_size": "Position is worth ₹{value} ({weight_pct}% of the portfolio).",
    # ── top up ──────────────────────────────────────────────────────────────
    "exit_clear": "Exit score {value}/100 — none of the five risk checks are flagging it.",
    "in_profit": "Up {value}% on your average price of ₹{avg_price}.",
    "trend_strength": "Above both its 50-day and 200-day averages ({ma50_gap}% and {ma200_gap}% clear).",
    "near_high": "Within {value}% of its 52-week high.",
    "momentum_3m": "Up {value}% over the last three months.",
    "momentum_12_1": "Up {value}% over twelve months excluding the most recent one.",
    "headroom": (
        "At {value}% of the portfolio it still has {headroom}% of room under your {limit}% cap."
    ),
    "sizing": "Adding about ₹{value} would take it to roughly the cap.",
    # ── buy ─────────────────────────────────────────────────────────────────
    "reachable": (
        "Typically moves about {value}% over {months} months, which {verdict} a {target}% target."
    ),
    "screens_passed": "Passes {value} of the short-listed technical screens ({names}).",
    "risk": (
        "A {stop_mult}x ATR stop at ₹{stop} risks {value}% for a {target}% target — {reward_risk}:1."
    ),
    "oversold": "RSI at {value} — near-term selling looks exhausted.",
    "above_trend": "Trading {value}% above its 50-day average.",
    "already_held": "You already own this one — this would be adding to it.",
    "too_wild": (
        "Swings roughly {value}% over the period — far more than the {target}% target needs, "
        "so the stop is likely to be hit first."
    ),
    # ── exclusions ──────────────────────────────────────────────────────────
    "too_slow": "Typically moves only about {value}% over {months} months — cannot cover {target}%.",
    "poor_reward_risk": (
        "A sensible stop sits {value}% below the entry, so it risks more than the {target}% "
        "it aims to gain."
    ),
    "no_history": "Not enough price history cached to assess it.",
    "avoided": "On your avoid list.",
    "held": "Already in your portfolio.",
}


def render(reason: dict) -> str:
    """Fill a reason's template. An unknown code or a missing field degrades to a
    readable fallback rather than raising — a broken sentence must never cost the
    user their whole answer."""
    template = TEMPLATES.get(reason.get("code", ""))
    if template is None:
        return f"{reason.get('code', 'note')}: {reason.get('value')}"
    fields = {"value": reason.get("value"), **(reason.get("ctx") or {})}
    try:
        return template.format(**fields)
    except (KeyError, IndexError):
        return f"{reason.get('code')}: {reason.get('value')}"


def apply(candidates: list[dict]) -> list[dict]:
    """Add a rendered `text` to every reason on every candidate, in place."""
    for candidate in candidates:
        for reason in candidate.get("reasons", []):
            reason["text"] = render(reason)
    return candidates
