"""Pure ranking: turns computed facts into ordered recommendations with reasons.

No I/O, no settings lookups, no prose — every input arrives as an argument and
every output carries reason *codes* plus the numbers behind them, which
`narrate.py` renders into sentences.

Splitting it this way is what makes the advisor's reasoning checkable: a test
can assert that a stock 30% underwater produces a `loss_severity` reason with
value -30, without caring how that sentence eventually reads.
"""
from __future__ import annotations

import math

from . import metrics

#: Exit-engine actions that mean "reduce this position".
SELL_ACTIONS = ("EXIT", "TRIM")

#: A reward:risk of 3 is about as good as a technical setup gets; used to put
#: reward:risk on the same 0-1 scale as the screener's aggregate conviction.
_REWARD_RISK_CEILING = 3.0

_REACH_VERDICT = {
    "comfortable": "comfortably covers",
    "plausible": "covers",
    "stretch": "only just covers",
    "too_wild": "far overshoots",
    "too_slow": "cannot cover",
}


def _round(value, digits=2):
    return None if value is None else round(float(value), digits)


def _clean(symbols) -> set[str]:
    return {str(s).strip().upper() for s in (symbols or []) if str(s).strip()}


# ── shared: technical strength ──────────────────────────────────────────────


def strength(snapshot: dict) -> tuple[int, dict]:
    """A 0-100 technical health score from five equally weighted yes/no checks.

    Deliberately coarse and countable rather than a tuned formula: "passes 4 of
    5 strength checks" is something the user can verify by eye, which a weighted
    polynomial is not.
    """
    checks = {
        "above_ma50": (snapshot.get("dist_to_ma50_pct") or 0) > 0,
        "above_ma200": (snapshot.get("dist_to_ma200_pct") or 0) > 0,
        "positive_3m": (snapshot.get("return_3m_pct") or 0) > 0,
        "positive_12m1": (snapshot.get("return_12m_1_pct") or 0) > 0,
        "near_52w_high": (snapshot.get("dist_to_52w_high_pct") if snapshot.get("dist_to_52w_high_pct") is not None else 100) <= 15,
    }
    return round(sum(checks.values()) / len(checks) * 100), checks


# ── sell ────────────────────────────────────────────────────────────────────


def _sell_reasons(signal: dict, summary: dict, single_cap: float, diversity: dict) -> list[dict]:
    scores = signal.get("scores", {})
    reasons: list[dict] = []

    if scores.get("loss_severity", 0) > 0:
        reasons.append({
            "code": "loss_severity",
            "value": signal["return_pct"],
            "ctx": {
                "drop": abs(signal["return_pct"]),
                "avg_price": _round(signal["avg_price"]),
                "ltp": _round(signal["ltp"]),
            },
        })

    if scores.get("risk_vs_median", 0) > 0:
        # The score already establishes this position is the riskier one. The
        # median only decides how precisely we can say so — it arrives rounded
        # to 4dp and can land on zero, which must not delete the reason.
        vol = signal.get("volatility") or 0
        median_vol = summary.get("median_volatility") or 0
        reasons.append({
            "code": "risk_vs_median" if median_vol else "risk_vs_median_simple",
            "value": _round(vol * 100, 1),
            "ctx": {
                "median": _round(median_vol * 100, 1),
                "ratio": _round(vol / median_vol, 1) if median_vol else None,
            },
        })

    if scores.get("risk_adj_inefficiency", 0) > 0:
        reasons.append({
            "code": "risk_adj_inefficiency",
            "value": _round(signal.get("rar")),
            "ctx": {"median": _round(summary.get("median_rar"))},
        })

    if scores.get("trend_weakness", 0) > 0:
        ma50, ma200 = signal.get("ma50"), signal.get("ma200")
        below_both = ma50 is not None and ma200 is not None and ma50 < ma200
        reasons.append({
            "code": "trend_weakness_both" if below_both else "trend_weakness_short",
            "value": _round(signal["ltp"]),
            "ctx": {"ma50": _round(ma50), "ma200": _round(ma200)},
        })

    if scores.get("concentration", 0) > 0:
        reasons.append({
            "code": "concentration",
            "value": signal["weight_pct"],
            "ctx": {"limit": single_cap},
        })

    pair = diversity.get("max_correlation_pair") or []
    if signal["symbol"] in pair and len(pair) == 2:
        partner = pair[0] if pair[1] == signal["symbol"] else pair[1]
        reasons.append({
            "code": "correlation_cluster",
            "value": _round((diversity.get("scalars") or {}).get("max_correlation")),
            "ctx": {"partner": partner},
        })

    if not reasons:
        reasons.append({
            "code": "position_size",
            "value": _round(signal["value"], 0),
            "ctx": {"weight_pct": signal["weight_pct"]},
        })
    return reasons


def _suggested_trim(signal: dict, total_value: float, single_cap: float, trim_fraction: float) -> dict:
    """How much to sell: everything on an EXIT, back to the cap on an oversized
    TRIM, otherwise a fixed slice."""
    qty = int(signal["quantity"])
    ltp = float(signal["ltp"]) or 1.0

    if signal["action"] == "EXIT":
        sell_qty, basis = qty, "full exit"
    elif signal["weight_pct"] > single_cap and total_value:
        excess = signal["value"] - (single_cap / 100) * total_value
        sell_qty = min(qty, max(1, math.ceil(excess / ltp)))
        basis = f"back to the {single_cap}% cap"
    else:
        sell_qty = min(qty, max(1, round(qty * trim_fraction)))
        basis = f"{round(trim_fraction * 100)}% of the position"

    return {
        "suggested_qty": sell_qty,
        "suggested_value": _round(sell_qty * ltp, 0),
        "suggested_basis": basis,
    }


def rank_sell(
    exit_payload: dict,
    diversity: dict,
    single_cap: float,
    tuning: dict,
    limit: int | None = None,
) -> list[dict]:
    """Positions the exit engine wants reduced, worst first."""
    signals = exit_payload.get("signals", [])
    summary = exit_payload.get("summary", {})
    total_value = sum(float(s.get("value") or 0) for s in signals)
    trim_fraction = float(tuning["trim_fraction"])

    out = []
    for signal in signals:
        if signal.get("action") not in SELL_ACTIONS:
            continue
        out.append({
            "symbol": signal["symbol"],
            "action": signal["action"],
            "conviction": signal["exit_score"],
            "quantity": signal["quantity"],
            "ltp": _round(signal["ltp"]),
            "avg_price": _round(signal["avg_price"]),
            "value": _round(signal["value"], 0),
            "weight_pct": signal["weight_pct"],
            "return_pct": signal["return_pct"],
            **_suggested_trim(signal, total_value, single_cap, trim_fraction),
            "reasons": _sell_reasons(signal, summary, single_cap, diversity),
        })

    out.sort(key=lambda c: c["conviction"], reverse=True)
    return out[:limit] if limit else out


# ── top up ──────────────────────────────────────────────────────────────────


def _topup_reasons(
    signal: dict,
    snapshot: dict,
    checks: dict,
    headroom_pct: float,
    single_cap: float,
    suggested_amount: float | None,
    reach: dict,
    horizon_months: float,
    target_gain_pct: float,
) -> list[dict]:
    reasons: list[dict] = [{"code": "exit_clear", "value": signal["exit_score"]}]

    if signal["return_pct"] > 0:
        reasons.append({
            "code": "in_profit",
            "value": signal["return_pct"],
            "ctx": {"avg_price": _round(signal["avg_price"])},
        })

    if checks["above_ma50"] and checks["above_ma200"]:
        reasons.append({
            "code": "trend_strength",
            "value": None,
            "ctx": {
                "ma50_gap": _round(snapshot.get("dist_to_ma50_pct"), 1),
                "ma200_gap": _round(snapshot.get("dist_to_ma200_pct"), 1),
            },
        })

    if checks["near_52w_high"]:
        reasons.append({"code": "near_high", "value": _round(snapshot.get("dist_to_52w_high_pct"), 1)})

    if checks["positive_3m"]:
        reasons.append({"code": "momentum_3m", "value": _round(snapshot.get("return_3m_pct"), 1)})

    if reach.get("expected_move_pct") is not None:
        reasons.append({
            "code": "reachable",
            "value": reach["expected_move_pct"],
            "ctx": {
                "months": horizon_months,
                "target": target_gain_pct,
                "verdict": _REACH_VERDICT.get(reach["tier"], "may cover"),
            },
        })

    reasons.append({
        "code": "headroom",
        "value": signal["weight_pct"],
        "ctx": {"headroom": _round(headroom_pct, 1), "limit": single_cap},
    })

    if suggested_amount:
        reasons.append({"code": "sizing", "value": _round(suggested_amount, 0)})

    return reasons


def rank_topup(
    exit_payload: dict,
    snapshots: dict[str, dict],
    single_cap: float,
    tuning: dict,
    profile: dict,
    horizon_months: float,
    target_gain_pct: float,
    limit: int | None = None,
) -> list[dict]:
    """Holdings worth adding to: nothing wrong with them, trending, and still
    under the weight cap. Explicitly *not* averaging down — a position the exit
    engine has flagged is filtered out before it gets here."""
    signals = exit_payload.get("signals", [])
    total_value = sum(float(s.get("value") or 0) for s in signals)
    avoid = _clean(profile.get("avoid_symbols"))
    max_exit = float(tuning["topup_max_exit_score"])
    min_strength = float(tuning["topup_min_strength"])
    capital = float(profile.get("capital_available") or 0)

    out = []
    for signal in signals:
        symbol = signal["symbol"]
        if symbol.upper() in avoid or signal["exit_score"] > max_exit:
            continue

        headroom_pct = single_cap - signal["weight_pct"]
        if headroom_pct <= 0:
            continue

        snapshot = snapshots.get(symbol) or {}
        if not snapshot.get("price"):
            continue

        score, checks = strength(snapshot)
        if score < min_strength:
            continue

        reach = metrics.reachability(
            snapshot.get("atr_pct"), horizon_months, target_gain_pct, tuning["reachability_tiers"]
        )

        amount = headroom_pct / 100 * total_value if total_value else 0
        if capital > 0:
            amount = min(amount, capital)

        out.append({
            "symbol": symbol,
            "conviction": round(0.5 * (100 - signal["exit_score"]) + 0.5 * score),
            "strength": score,
            "exit_score": signal["exit_score"],
            "weight_pct": signal["weight_pct"],
            "headroom_pct": _round(headroom_pct, 1),
            "ltp": _round(signal["ltp"]),
            "return_pct": signal["return_pct"],
            "suggested_amount": _round(amount, 0),
            "reachability": reach,
            "reasons": _topup_reasons(
                signal, snapshot, checks, headroom_pct, single_cap,
                amount, reach, horizon_months, target_gain_pct,
            ),
        })

    out.sort(key=lambda c: c["conviction"], reverse=True)
    return out[:limit] if limit else out


# ── buy ─────────────────────────────────────────────────────────────────────


def _buy_reasons(
    snapshot: dict,
    reach: dict,
    levels: dict,
    passed: list[str],
    horizon_months: float,
    target_gain_pct: float,
    stop_multiple: float,
    already_held: bool,
) -> list[dict]:
    reasons: list[dict] = [{
        "code": "reachable",
        "value": reach["expected_move_pct"],
        "ctx": {
            "months": horizon_months,
            "target": target_gain_pct,
            "verdict": _REACH_VERDICT.get(reach["tier"], "may cover"),
        },
    }]

    if passed:
        reasons.append({
            "code": "screens_passed",
            "value": len(passed),
            "ctx": {"names": ", ".join(passed)},
        })

    if (snapshot.get("return_12m_1_pct") or 0) > 0:
        reasons.append({"code": "momentum_12_1", "value": _round(snapshot["return_12m_1_pct"], 1)})
    elif (snapshot.get("return_3m_pct") or 0) > 0:
        reasons.append({"code": "momentum_3m", "value": _round(snapshot["return_3m_pct"], 1)})

    high_gap = snapshot.get("dist_to_52w_high_pct")
    if high_gap is not None and high_gap <= 15:
        reasons.append({"code": "near_high", "value": _round(high_gap, 1)})

    ma50_gap = snapshot.get("dist_to_ma50_pct")
    if ma50_gap is not None and ma50_gap > 0:
        reasons.append({"code": "above_trend", "value": _round(ma50_gap, 1)})

    rsi = snapshot.get("rsi")
    if rsi is not None and rsi < 40:
        reasons.append({"code": "oversold", "value": _round(rsi, 1)})

    if levels.get("reward_risk"):
        reasons.append({
            "code": "risk",
            "value": levels["risk_pct"],
            "ctx": {
                "stop": levels["stop_price"],
                "stop_mult": stop_multiple,
                "target": target_gain_pct,
                "reward_risk": levels["reward_risk"],
            },
        })

    if reach["tier"] == "too_wild":
        reasons.append({
            "code": "too_wild",
            "value": reach["expected_move_pct"],
            "ctx": {"target": target_gain_pct},
        })

    if already_held:
        reasons.append({"code": "already_held", "value": None})

    return reasons


def rank_buy(
    scan: dict,
    snapshots: dict[str, dict],
    passes_by_symbol: dict[str, list[str]],
    held_symbols: set[str],
    tuning: dict,
    profile: dict,
    horizon_months: float,
    target_gain_pct: float,
    exclude_held: bool = True,
    limit: int = 10,
) -> tuple[list[dict], list[dict]]:
    """Rank screener candidates on whether they can realistically reach the
    caller's target in the caller's timeframe. Returns (ideas, excluded)."""
    tiers = tuning["reachability_tiers"]
    stop_multiple = float(tuning["atr_stop_multiple"])
    min_reward_risk = float(tuning.get("min_reward_risk", 1.0))
    risk_weights = tuning["risk_weights"]
    tolerance = profile.get("risk_tolerance", "balanced")
    blend = risk_weights.get(tolerance, risk_weights["balanced"])
    avoid = _clean(profile.get("avoid_symbols"))
    # Only an explicitly aggressive profile sees names whose typical swing dwarfs
    # the target — for everyone else the stop gets hit long before the target.
    allow_wild = tolerance == "aggressive"

    ideas: list[dict] = []
    excluded: list[dict] = []

    for row in scan.get("results", []):
        symbol = row["symbol"]

        if symbol.upper() in avoid:
            excluded.append({"symbol": symbol, "code": "avoided"})
            continue
        already_held = symbol.upper() in held_symbols
        if already_held and exclude_held:
            excluded.append({"symbol": symbol, "code": "held"})
            continue

        snapshot = snapshots.get(symbol) or {}
        if not snapshot.get("price") or snapshot.get("atr_pct") is None:
            excluded.append({"symbol": symbol, "code": "no_history"})
            continue

        reach = metrics.reachability(snapshot["atr_pct"], horizon_months, target_gain_pct, tiers)
        if reach["tier"] not in metrics.RECOMMENDABLE_TIERS and not (
            reach["tier"] == "too_wild" and allow_wild
        ):
            excluded.append({
                "symbol": symbol,
                "code": reach["tier"] if reach["tier"] in ("too_slow", "too_wild") else "no_history",
                "value": reach["expected_move_pct"],
                "ctx": {"months": horizon_months, "target": target_gain_pct},
            })
            continue

        levels = metrics.trade_levels(
            snapshot["price"], snapshot.get("atr"), target_gain_pct, stop_multiple
        )
        reward_risk = levels.get("reward_risk") or 0
        if reward_risk < min_reward_risk:
            excluded.append({
                "symbol": symbol,
                "code": "poor_reward_risk",
                "value": levels.get("risk_pct"),
                "ctx": {"target": target_gain_pct},
            })
            continue

        conviction = float(row.get("aggregate") or 0)
        rr_norm = min(reward_risk / _REWARD_RISK_CEILING, 1.0)
        score = 100 * (blend["conviction"] * conviction + blend["reward_risk"] * rr_norm)

        ideas.append({
            "symbol": symbol,
            "score": round(score),
            "conviction": round(conviction * 100),
            "ltp": _round(snapshot["price"]),
            **levels,
            "reachability": reach,
            "passes": passes_by_symbol.get(symbol, []),
            "already_held": already_held,
            "reasons": _buy_reasons(
                snapshot, reach, levels, passes_by_symbol.get(symbol, []),
                horizon_months, target_gain_pct, stop_multiple, already_held,
            ),
        })

    ideas.sort(key=lambda c: c["score"], reverse=True)
    return ideas[:limit], excluded
