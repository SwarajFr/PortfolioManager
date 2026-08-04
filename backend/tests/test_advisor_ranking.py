"""Ranking: which candidates survive, in what order, and citing which facts.

Pure inputs, pure outputs — no market data service, no LLM. Assertions are on
reason *codes*, not prose, so rewording a sentence never breaks a test.
"""
from __future__ import annotations

import pytest

from features.advisor import narrate, ranking
from features.advisor.settings import DEFAULT

TUNING = DEFAULT["tuning"]
PROFILE = DEFAULT["profile"]


def signal(symbol, **over):
    base = {
        "symbol": symbol,
        "ltp": 100.0,
        "avg_price": 100.0,
        "quantity": 100,
        "value": 10000.0,
        "invested": 10000.0,
        "return_pct": 0.0,
        "weight_pct": 2.0,
        "volatility": 0.30,
        "ma50": 100.0,
        "ma200": 100.0,
        "rar": 0.0,
        "scores": {
            "loss_severity": 0,
            "risk_vs_median": 0,
            "risk_adj_inefficiency": 0,
            "trend_weakness": 0,
            "concentration": 0,
        },
        "exit_score": 0,
        "action": "HOLD",
    }
    scores = {**base["scores"], **over.pop("scores", {})}
    return {**base, **over, "scores": scores}


def payload(*signals, median_volatility=0.30, median_rar=0.5):
    return {
        "signals": list(signals),
        "summary": {"median_volatility": median_volatility, "median_rar": median_rar},
    }


def codes(candidate):
    return [r["code"] for r in candidate["reasons"]]


def snapshot(**over):
    base = {
        "price": 100.0,
        "atr": 2.0,
        "atr_pct": 2.0,
        "dist_to_ma50_pct": 5.0,
        "dist_to_ma200_pct": 10.0,
        "dist_to_52w_high_pct": 4.0,
        "return_3m_pct": 9.0,
        "return_12m_1_pct": 25.0,
        "rsi": 60.0,
    }
    return {**base, **over}


# ── sell ────────────────────────────────────────────────────────────────────


def test_only_trim_and_exit_are_recommended_for_sale():
    out = ranking.rank_sell(
        payload(
            signal("KEEP", action="HOLD", exit_score=10),
            signal("WATCH", action="WATCH", exit_score=35),
            signal("CUT", action="TRIM", exit_score=55),
            signal("DUMP", action="EXIT", exit_score=80),
        ),
        {}, 5.0, TUNING,
    )
    assert [c["symbol"] for c in out] == ["DUMP", "CUT"]


def test_sell_reasons_cite_the_kpis_that_fired():
    out = ranking.rank_sell(
        payload(
            signal(
                "IDEA",
                action="EXIT",
                exit_score=80,
                return_pct=-30.0,
                avg_price=12.0,
                ltp=8.4,
                volatility=0.62,
                ma50=9.8,
                ma200=11.2,
                rar=-1.5,
                weight_pct=9.0,
                scores={
                    "loss_severity": 25,
                    "risk_vs_median": 20,
                    "risk_adj_inefficiency": 20,
                    "trend_weakness": 20,
                    "concentration": 15,
                },
            )
        ),
        {}, 5.0, TUNING,
    )
    reasons = codes(out[0])
    assert "loss_severity" in reasons
    assert "risk_vs_median" in reasons
    assert "risk_adj_inefficiency" in reasons
    assert "trend_weakness_both" in reasons  # below both averages, 50 under 200
    assert "concentration" in reasons


def test_sell_reasons_carry_real_numbers():
    out = ranking.rank_sell(
        payload(signal("X", action="EXIT", exit_score=75, return_pct=-30.6,
                       scores={"loss_severity": 25})),
        {}, 5.0, TUNING,
    )
    loss = next(r for r in out[0]["reasons"] if r["code"] == "loss_severity")
    assert loss["value"] == -30.6


def test_loss_reason_reads_as_a_drop_not_a_double_negative():
    out = ranking.rank_sell(
        payload(signal("X", action="EXIT", exit_score=75, return_pct=-40.0,
                       scores={"loss_severity": 25})),
        {}, 5.0, TUNING,
    )
    loss = next(r for r in out[0]["reasons"] if r["code"] == "loss_severity")
    assert loss["value"] == -40.0  # signed for machines
    assert "Down 40.0%" in narrate.render(loss)  # readable for people


def test_risk_reason_survives_a_median_that_rounds_to_zero():
    """The exit summary reports the median to 4dp. A portfolio of very calm
    holdings rounds it to 0.0, which must not delete the reason that the exit
    engine already scored."""
    out = ranking.rank_sell(
        payload(
            signal("X", action="EXIT", exit_score=75, volatility=0.62,
                   scores={"risk_vs_median": 20}),
            median_volatility=0.0,
        ),
        {}, 5.0, TUNING,
    )
    risk = next(r for r in out[0]["reasons"] if r["code"].startswith("risk_vs_median"))
    assert risk["value"] == 62.0
    assert "62.0%" in narrate.render(risk)
    assert "{" not in narrate.render(risk)


def test_a_flagged_position_always_gets_at_least_one_reason():
    """Thresholds can put a stock over the TRIM line on subscores that have
    since fallen back to zero; an empty rationale is never acceptable."""
    out = ranking.rank_sell(
        payload(signal("ODD", action="TRIM", exit_score=55)), {}, 5.0, TUNING
    )
    assert codes(out[0]) == ["position_size"]


def test_correlation_partner_becomes_a_reason():
    diversity = {
        "max_correlation_pair": ["HDFCBANK", "ICICIBANK"],
        "scalars": {"max_correlation": 0.91},
    }
    out = ranking.rank_sell(
        payload(signal("HDFCBANK", action="TRIM", exit_score=55)), diversity, 5.0, TUNING
    )
    reason = next(r for r in out[0]["reasons"] if r["code"] == "correlation_cluster")
    assert reason["ctx"]["partner"] == "ICICIBANK"
    assert narrate.render(reason).count("ICICIBANK") == 1


def test_exit_sells_the_whole_position():
    out = ranking.rank_sell(
        payload(signal("X", action="EXIT", exit_score=80, quantity=100)), {}, 5.0, TUNING
    )
    assert out[0]["suggested_qty"] == 100
    assert out[0]["suggested_basis"] == "full exit"


def test_oversized_trim_cuts_back_to_the_cap():
    # One 20,000 position inside a 100,000 portfolio is 20%; a 5% cap means
    # selling 15,000 worth, i.e. 150 of 200 shares at 100.
    out = ranking.rank_sell(
        payload(
            signal("BIG", action="TRIM", exit_score=55, quantity=200,
                   value=20000.0, weight_pct=20.0),
            signal("REST", action="HOLD", value=80000.0, weight_pct=80.0),
        ),
        {}, 5.0, TUNING,
    )
    assert out[0]["suggested_qty"] == 150
    assert "cap" in out[0]["suggested_basis"]


def test_trim_within_the_cap_sheds_a_fixed_fraction():
    out = ranking.rank_sell(
        payload(signal("X", action="TRIM", exit_score=55, quantity=90, weight_pct=3.0)),
        {}, 5.0, TUNING,
    )
    assert out[0]["suggested_qty"] == 30  # trim_fraction 0.33


# ── top up ──────────────────────────────────────────────────────────────────


def topup(signals, snapshots, **kw):
    return ranking.rank_topup(
        payload(*signals), snapshots, kw.pop("cap", 5.0), TUNING,
        {**PROFILE, **kw.pop("profile", {})},
        kw.pop("horizon", 3), kw.pop("target", 10),
    )


def test_healthy_underweight_holding_is_a_topup():
    out = topup([signal("BEL", exit_score=12, weight_pct=2.0, return_pct=18.0)],
                {"BEL": snapshot()})
    assert [c["symbol"] for c in out] == ["BEL"]
    assert out[0]["headroom_pct"] == 3.0
    assert "exit_clear" in codes(out[0])
    assert "headroom" in codes(out[0])


def test_a_flagged_holding_is_never_a_topup():
    """The whole point of 'add to winners': anything the exit engine dislikes is
    filtered out before ranking, so this can never suggest averaging down."""
    out = topup([signal("IDEA", exit_score=75, weight_pct=1.0, return_pct=-40.0)],
                {"IDEA": snapshot()})
    assert out == []


def test_a_holding_at_the_cap_is_not_a_topup():
    out = topup([signal("BIG", exit_score=5, weight_pct=5.0)], {"BIG": snapshot()})
    assert out == []


def test_a_technically_weak_holding_is_not_a_topup():
    weak = snapshot(dist_to_ma50_pct=-5, dist_to_ma200_pct=-8,
                    return_3m_pct=-4, return_12m_1_pct=-10, dist_to_52w_high_pct=40)
    out = topup([signal("SOFT", exit_score=10, weight_pct=1.0)], {"SOFT": weak})
    assert out == []


def test_avoid_list_removes_a_holding_from_topups():
    out = topup([signal("BEL", exit_score=10, weight_pct=1.0)], {"BEL": snapshot()},
                profile={"avoid_symbols": ["bel"]})
    assert out == []


def test_topup_sizing_respects_available_capital():
    signals = [signal("BEL", exit_score=10, weight_pct=1.0, value=1000.0),
               signal("OTHER", value=99000.0, weight_pct=99.0)]
    unlimited = topup(signals, {"BEL": snapshot()})
    assert unlimited[0]["suggested_amount"] == 4000  # 4% headroom of 100,000

    limited = topup(signals, {"BEL": snapshot()}, profile={"capital_available": 1500})
    assert limited[0]["suggested_amount"] == 1500


def test_topup_carries_the_callers_horizon_and_target():
    out = topup([signal("BEL", exit_score=10, weight_pct=1.0)], {"BEL": snapshot()},
                horizon=2, target=5)
    assert out[0]["reachability"]["horizon_trading_days"] == 42
    reach = next(r for r in out[0]["reasons"] if r["code"] == "reachable")
    assert reach["ctx"]["target"] == 5


# ── buy ─────────────────────────────────────────────────────────────────────


def scan(*symbols_and_aggregates):
    return {"results": [{"symbol": s, "aggregate": a, "passes": 3}
                        for s, a in symbols_and_aggregates]}


def buy(scan_payload, snapshots, **kw):
    return ranking.rank_buy(
        scan_payload, snapshots, kw.pop("passes", {}), kw.pop("held", set()),
        TUNING, {**PROFILE, **kw.pop("profile", {})},
        kw.pop("horizon", 3), kw.pop("target", 10),
        exclude_held=kw.pop("exclude_held", True), limit=kw.pop("limit", 10),
    )


def test_sluggish_stock_is_excluded_with_a_stated_reason():
    """0.5% daily range cannot cover 10% in three months, and saying so is more
    useful than silently dropping it."""
    ideas, excluded = buy(scan(("SLOW", 0.9)), {"SLOW": snapshot(atr_pct=0.5, atr=0.5)})
    assert ideas == []
    assert excluded[0]["code"] == "too_slow"


def test_wild_stock_is_excluded_unless_the_profile_is_aggressive():
    # Over six months this stock swings ~5x the target, but its stop is still
    # closer than its target — so reward:risk passes and "too wild" is the only
    # thing standing between it and the list.
    snaps = {"WILD": snapshot(atr_pct=4.6, atr=4.6)}
    ideas, excluded = buy(scan(("WILD", 0.9)), snaps, horizon=6, target=10)
    assert ideas == []
    assert excluded[0]["code"] == "too_wild"

    ideas, _ = buy(scan(("WILD", 0.9)), snaps, horizon=6, target=10,
                   profile={"risk_tolerance": "aggressive"})
    assert [c["symbol"] for c in ideas] == ["WILD"]
    assert "too_wild" in codes(ideas[0])


def test_held_stocks_are_excluded_by_default_and_flagged_when_not():
    ideas, excluded = buy(scan(("INFY", 0.9)), {"INFY": snapshot()}, held={"INFY"})
    assert ideas == []
    assert excluded[0]["code"] == "held"

    ideas, _ = buy(scan(("INFY", 0.9)), {"INFY": snapshot()}, held={"INFY"}, exclude_held=False)
    assert ideas[0]["already_held"] is True
    assert "already_held" in codes(ideas[0])


def test_avoid_list_is_honoured():
    ideas, excluded = buy(scan(("ITC", 0.9)), {"ITC": snapshot()},
                          profile={"avoid_symbols": ["ITC"]})
    assert ideas == []
    assert excluded[0]["code"] == "avoided"


def test_a_trade_risking_more_than_it_targets_is_excluded():
    """Reachability alone does not catch these: a 6%-a-day stock easily covers
    10% in three months, but a sensible stop sits 12% away — so it is likelier to
    stop out than to pay. Recommending it would defeat the point of the target."""
    ideas, excluded = buy(scan(("CHOPPY", 0.95)), {"CHOPPY": snapshot(atr_pct=6.0, atr=6.0)},
                          target=10)
    assert ideas == []
    assert excluded[0]["code"] == "poor_reward_risk"
    assert "{" not in narrate.render(excluded[0])


def test_the_reward_risk_floor_is_configurable():
    snaps = {"CHOPPY": snapshot(atr_pct=6.0, atr=6.0)}
    relaxed = {**TUNING, "min_reward_risk": 0.0}
    ideas, _ = ranking.rank_buy(
        scan(("CHOPPY", 0.95)), snaps, {}, set(), relaxed, PROFILE, 3, 10,
    )
    assert [c["symbol"] for c in ideas] == ["CHOPPY"]


def test_missing_history_is_excluded_not_guessed():
    ideas, excluded = buy(scan(("NEW", 0.9)), {})
    assert ideas == []
    assert excluded[0]["code"] == "no_history"


def test_ideas_are_ranked_and_limited():
    snaps = {s: snapshot() for s in ("A", "B", "C")}
    ideas, _ = buy(scan(("A", 0.4), ("B", 0.95), ("C", 0.7)), snaps, limit=2)
    assert [c["symbol"] for c in ideas] == ["B", "C"]


def test_risk_tolerance_changes_the_ordering():
    """A conservative profile weights reward:risk over raw screener conviction,
    so the safer setup outranks the higher-scoring one."""
    # Both can reach 10% in three months; HOTSHOT just needs a wider stop to do
    # it, which is what makes its reward:risk worse.
    snaps = {
        "HOTSHOT": snapshot(atr_pct=3.0, atr=3.0),
        "STEADY": snapshot(atr_pct=1.8, atr=1.8),
    }
    scan_payload = scan(("HOTSHOT", 0.95), ("STEADY", 0.60))

    aggressive, _ = buy(scan_payload, snaps, profile={"risk_tolerance": "aggressive"})
    conservative, _ = buy(scan_payload, snaps, profile={"risk_tolerance": "conservative"})

    assert aggressive[0]["symbol"] == "HOTSHOT"
    assert conservative[0]["symbol"] == "STEADY"


def test_buy_idea_carries_levels_and_named_screens():
    ideas, _ = buy(scan(("CG", 0.8)), {"CG": snapshot()},
                   passes={"CG": ["breakout", "high_52w"]})
    idea = ideas[0]
    assert idea["target_price"] == 110.0
    assert idea["stop_price"] == 96.0
    assert idea["reward_risk"] == pytest.approx(2.5)
    screens = next(r for r in idea["reasons"] if r["code"] == "screens_passed")
    assert screens["value"] == 2
    assert "breakout" in narrate.render(screens)


def test_every_reason_renders_to_a_sentence():
    ideas, _ = buy(scan(("CG", 0.8)), {"CG": snapshot(rsi=32.0)},
                   passes={"CG": ["rsi_reversion"]})
    narrate.apply(ideas)
    for reason in ideas[0]["reasons"]:
        assert reason["text"]
        assert "{" not in reason["text"]  # no unfilled template slots
