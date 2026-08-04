"""Orchestration for the advisor: gather facts, rank them, narrate, journal.

This is the only layer here that does I/O. It reuses the existing feature
services rather than re-deriving anything — the exit engine already scores
holdings, the fragility engine already measures correlation, and the screener
already ranks the NSE500 — so the advisor's job is to combine them into an
answer to a question a person actually asks.
"""
from __future__ import annotations

import datetime
import logging

from core.data import InstrumentRef, get_market_data
from features.exit.service import get_exit_signals
from features.fragility.service import get_diversity_analysis
from features.portfolio.settings import get_settings as get_portfolio_settings
from features.screener import cache as screener_cache
from features.screener.service import run_scan

from . import journal, metrics, narrate, ranking, settings

logger = logging.getLogger(__name__)

#: Deeper than the exit engine's 365 days: the 12-1 momentum reason skips a
#: month and still needs a year behind it, and MA200 needs 200 bars. The
#: fragility engine already warms the cache to 900 days, so this rarely fetches.
LOOKBACK_DAYS = 500

DISCLAIMER = (
    "Rule-based technical signals computed from your holdings and cached price history. "
    "Not investment advice — verify before acting."
)


def _today() -> str:
    return datetime.date.today().isoformat()


def _config() -> tuple[dict, dict]:
    conf = settings.get_settings()
    return conf["profile"], conf["tuning"]


def _single_cap() -> float:
    """The single-holding weight cap the user already set on the Overview page."""
    return float(get_portfolio_settings()["concentration"]["single"])


def _params(horizon_months, target_gain_pct, profile) -> tuple[float, float]:
    """Caller's horizon and target win; the profile only fills in the blanks."""
    horizon = float(horizon_months if horizon_months is not None else profile["default_horizon_months"])
    target = float(target_gain_pct if target_gain_pct is not None else profile["default_target_gain_pct"])
    return max(horizon, 0.25), max(target, 0.5)


def _holding_refs() -> list[InstrumentRef]:
    """Holdings rows carry an instrument token, so history needs no lookup."""
    holdings = get_market_data().get_holdings()
    if holdings is None or holdings.empty:
        return []
    return [
        InstrumentRef(symbol=str(row.tradingsymbol), token=int(row.instrument_token))
        for row in holdings.itertuples()
    ]


def _held_symbols() -> set[str]:
    """Upper-cased holdings, or empty when there is no live session — a buy
    screen is still useful without one, it just cannot flag overlap."""
    try:
        return {ref.symbol.upper() for ref in _holding_refs()}
    except Exception as exc:  # noqa: BLE001 - no session -> rank buys without overlap flagging
        logger.warning("holdings unavailable while ranking buys: %s", exc)
        return set()


def _snapshots(symbols_or_refs, *, refresh: bool) -> dict[str, dict]:
    history = get_market_data().get_history_batch(
        symbols_or_refs, lookback_days=LOOKBACK_DAYS, refresh=refresh
    )
    return {symbol: metrics.snapshot(frame) for symbol, frame in history.items()}


def _safe_diversity() -> dict:
    """Correlation structure is a nice-to-have reason, not a prerequisite."""
    try:
        return get_diversity_analysis()
    except Exception as exc:  # noqa: BLE001 - correlation is a bonus reason, not a prerequisite
        logger.warning("diversification metrics unavailable: %s", exc)
        return {}


def _record(entries: list[dict]) -> None:
    """Journalling must never cost the user their answer."""
    try:
        journal.record(entries)
    except Exception as exc:  # noqa: BLE001 - journalling must never cost the user their answer
        logger.warning("could not write advisor journal: %s", exc)


def _headline(candidate: dict) -> str:
    reasons = candidate.get("reasons") or []
    return reasons[0].get("text", "") if reasons else ""


# ── question 1: what should I sell or top up? ───────────────────────────────


def portfolio_actions(
    horizon_months: float | None = None,
    target_gain_pct: float | None = None,
    limit: int | None = None,
) -> dict:
    """Ranked sell and top-up candidates from the current portfolio, with reasons."""
    profile, tuning = _config()
    horizon, target = _params(horizon_months, target_gain_pct, profile)
    cap = _single_cap()

    # Checked before the exit engine runs: `compute_exit_signals` indexes the
    # holdings frame directly and raises KeyError on an account with no stock.
    refs = _holding_refs()
    exit_payload = get_exit_signals() if refs else {}
    signals = exit_payload.get("signals", [])
    summary = exit_payload.get("summary", {})

    if not signals:
        return {
            "as_of": _today(),
            "horizon_months": horizon,
            "target_gain_pct": target,
            "portfolio": {"num_holdings": 0, "total_value": 0.0},
            "sell": [],
            "topup": [],
            "notes": ["No holdings found. Log in to Kite and make sure the account has stock."],
            "disclaimer": DISCLAIMER,
        }

    diversity = _safe_diversity()
    snapshots = _snapshots(refs, refresh=True)

    sell = narrate.apply(ranking.rank_sell(exit_payload, diversity, cap, tuning, limit))
    topup = narrate.apply(
        ranking.rank_topup(exit_payload, snapshots, cap, tuning, profile, horizon, target, limit)
    )

    _record(
        [
            {"kind": "sell", "symbol": c["symbol"], "price": c["ltp"],
             "conviction": c["conviction"], "action": c["action"], "headline": _headline(c)}
            for c in sell
        ]
        + [
            {"kind": "topup", "symbol": c["symbol"], "price": c["ltp"],
             "conviction": c["conviction"], "horizon_months": horizon,
             "target_gain_pct": target, "headline": _headline(c)}
            for c in topup
        ]
    )

    notes = []
    if not sell:
        notes.append("Nothing is flagged for selling — every holding scores below the TRIM threshold.")
    if not topup:
        notes.append(
            f"No holding qualifies for a top-up: each is either flagged by the exit engine, "
            f"below the technical strength bar, or already at the {cap}% weight cap."
        )

    scalars = diversity.get("scalars") or {}
    return {
        "as_of": _today(),
        "horizon_months": horizon,
        "target_gain_pct": target,
        "portfolio": {
            "num_holdings": summary.get("total_holdings", len(signals)),
            "total_value": round(sum(float(s.get("value") or 0) for s in signals), 2),
            "avg_exit_score": summary.get("avg_exit_score"),
            "action_counts": summary.get("action_counts"),
            "single_holding_cap_pct": cap,
        },
        "diversification": {
            "effective_number_of_bets": scalars.get("enb"),
            "avg_correlation": scalars.get("avg_correlation"),
            "max_correlation": scalars.get("max_correlation"),
            "max_correlation_pair": diversity.get("max_correlation_pair"),
        },
        "sell": sell,
        "topup": topup,
        "notes": notes,
        "disclaimer": DISCLAIMER,
    }


# ── question 2: what should I buy for X% in Y months? ───────────────────────


def _passing_strategies(selected: list[str]) -> dict[str, list[str]]:
    """Which of the selected screens each symbol currently passes."""
    out: dict[str, list[str]] = {}
    for row in screener_cache.read_signals():
        passed = [name for name in selected if (row["passes"] or {}).get(name)]
        if passed:
            out[row["symbol"]] = passed
    return out


def _summarize_exclusions(excluded: list[dict]) -> dict:
    """Counts plus a few worked examples. Dumping 400 rejected symbols into an
    LLM's context buys nothing; knowing 40 were too sluggish does."""
    counts: dict[str, int] = {}
    for item in excluded:
        counts[item["code"]] = counts.get(item["code"], 0) + 1

    examples = [
        {"symbol": item["symbol"], "reason": narrate.render(item)}
        for item in excluded
        if item["code"] in ("too_slow", "too_wild", "poor_reward_risk")
    ][:5]
    return {"counts": counts, "examples": examples}


def buy_ideas(
    horizon_months: float | None = None,
    target_gain_pct: float | None = None,
    limit: int = 10,
    exclude_held: bool = True,
) -> dict:
    """New buy candidates that can realistically reach the target in the time given."""
    profile, tuning = _config()
    horizon, target = _params(horizon_months, target_gain_pct, profile)
    band, weights = settings.strategy_weights_for_horizon(horizon, tuning)
    shortlist_size = int(tuning["shortlist_size"])

    scan = run_scan(
        strategies=list(weights),
        weights=weights,
        k=int(tuning["min_strategies_passed"]),
        fallback_n=shortlist_size,
    )
    results = scan.get("results", [])[:shortlist_size]

    if not results:
        return {
            "as_of": _today(),
            "horizon_months": horizon,
            "target_gain_pct": target,
            "ideas": [],
            "notes": [
                "The screener cache is empty. Log in to Kite (which triggers a refresh) or "
                "POST /api/screener/refresh, then ask again."
            ],
            "disclaimer": DISCLAIMER,
        }

    selected = scan.get("selected", list(weights))
    # refresh=False keeps this a pure cache read: 60 symbols must not turn into
    # 60 broker round-trips on a chat message.
    snapshots = _snapshots([row["symbol"] for row in results], refresh=False)

    ideas, excluded = ranking.rank_buy(
        {"results": results},
        snapshots,
        _passing_strategies(selected),
        # Always resolved: when exclude_held is off, overlap becomes a flag on
        # the idea rather than a reason to drop it.
        _held_symbols(),
        tuning,
        profile,
        horizon,
        target,
        exclude_held=exclude_held,
        limit=limit,
    )
    narrate.apply(ideas)

    _record([
        {"kind": "buy", "symbol": c["symbol"], "price": c["ltp"],
         "target_price": c["target_price"], "stop_price": c["stop_price"],
         "conviction": c["score"], "horizon_months": horizon,
         "target_gain_pct": target, "headline": _headline(c)}
        for c in ideas
    ])

    notes = []
    if scan.get("is_fallback"):
        notes.append(
            f"No stock passed {tuning['min_strategies_passed']} of the {band}-horizon screens, "
            "so these are the best-ranked names rather than confirmed setups."
        )
    if not ideas:
        notes.append(
            f"Nothing in the NSE500 cache can plausibly cover {target}% in {horizon} months "
            "at your risk setting."
        )

    return {
        "as_of": _today(),
        "horizon_months": horizon,
        "target_gain_pct": target,
        "horizon_band": band,
        "strategies_used": selected,
        "universe": "NSE500",
        "signals_as_of": scan.get("last_updated"),
        "considered": len(results),
        "ideas": ideas,
        "excluded": _summarize_exclusions(excluded),
        "notes": notes,
        "disclaimer": DISCLAIMER,
    }


# ── memory: what did you tell me before? ────────────────────────────────────


def advice_history(limit: int = 20, kind: str | None = None) -> dict:
    """Past recommendations with what the price has done since.

    This is the accountability half of the design: the advisor's own record,
    marked against the market rather than against its memory of itself.
    """
    entries = journal.read(limit=limit, kind=kind)
    if not entries:
        return {"entries": [], "note": "No recommendations recorded yet.", "disclaimer": DISCLAIMER}

    symbols = sorted({e["symbol"] for e in entries if e.get("symbol")})
    live: dict[str, float] = {}
    try:
        live = {s: q.last_price for s, q in get_market_data().get_quote(symbols).items()}
    except Exception as exc:  # noqa: BLE001 - journal replay still works without live prices
        logger.warning("live prices unavailable for journal replay: %s", exc)

    out = []
    for entry in entries:
        now = live.get(entry.get("symbol"))
        then = entry.get("price")
        move = round((now - then) / then * 100, 2) if now and then else None
        out.append({**entry, "price_now": round(now, 2) if now else None, "move_since_pct": move})

    return {"entries": out, "count": len(out), "disclaimer": DISCLAIMER}


def investor_profile() -> dict:
    """The stored profile, so a client with no system prompt of its own (Claude
    Desktop over MCP) can still tailor its answers."""
    profile, tuning = _config()
    return {
        "profile": profile,
        "defaults_in_use": {
            "horizon_months": profile["default_horizon_months"],
            "target_gain_pct": profile["default_target_gain_pct"],
            "single_holding_cap_pct": _single_cap(),
        },
        "note": (
            "These are fallbacks. If the user names a horizon or a target in their question, "
            "pass those instead."
        ),
        "tuning": tuning,
    }
