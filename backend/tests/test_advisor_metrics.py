"""Per-stock indicators and the reachability model.

The reachability tests are the regression guard for the one requirement that
shaped this feature: the horizon and the gain target are the caller's, and every
derived figure must move when they do.
"""
from __future__ import annotations

import datetime

import pandas as pd
import pytest

from features.advisor import metrics


def frame(closes: list[float], spread: float = 1.0) -> pd.DataFrame:
    """Synthetic OHLC: a fixed high-low spread makes ATR analytically predictable."""
    start = datetime.date(2025, 1, 1)
    index = pd.to_datetime([start + datetime.timedelta(days=i) for i in range(len(closes))])
    return pd.DataFrame(
        {
            "open": closes,
            "high": [c + spread for c in closes],
            "low": [c - spread for c in closes],
            "close": closes,
            "volume": [1000.0] * len(closes),
        },
        index=index,
    )


# ── indicators ──────────────────────────────────────────────────────────────


def test_atr_pct_matches_the_known_spread():
    # Flat price 100 with a ±1 band: true range is 2 every bar, so ATR is 2 (2%).
    df = frame([100.0] * 60)
    assert metrics.atr(df) == pytest.approx(2.0, abs=0.01)
    assert metrics.atr_pct(df) == pytest.approx(2.0, abs=0.01)


def test_atr_is_none_without_enough_bars():
    assert metrics.atr(frame([100.0] * 5)) is None


def test_dist_to_high_and_ma():
    df = frame([100.0] * 250 + [90.0] * 10)
    assert metrics.dist_to_high_pct(df, 252) == pytest.approx(10.0, abs=0.1)
    # Below the 50-day average after the drop.
    assert metrics.dist_to_ma_pct(df, 50) < 0


def test_trailing_return_skips_the_recent_month():
    # Rises to 200 over a year, then collapses in the last month. 12-1 momentum
    # must ignore the collapse; the plain 3-month return must not.
    closes = [100.0 + i * 0.3 for i in range(300)] + [50.0] * 21
    df = frame(closes)
    assert metrics.trailing_return_pct(df, 12, skip_months=1) > 0
    assert metrics.trailing_return_pct(df, 3) < 0


def test_max_drawdown_is_positive():
    df = frame([100.0] * 30 + [60.0] * 30)
    assert metrics.max_drawdown_pct(df, 252) == pytest.approx(40.0, abs=0.1)


def test_snapshot_survives_short_history():
    """A recently listed stock yields Nones, not an exception — the ranking layer
    simply has fewer reasons to work with."""
    snap = metrics.snapshot(frame([100.0] * 30))
    assert snap["price"] == 100.0
    assert snap["atr_pct"] is not None
    assert snap["return_12m_1_pct"] is None
    assert snap["dist_to_ma200_pct"] is None


def test_snapshot_of_empty_frame_is_empty():
    assert metrics.snapshot(pd.DataFrame()) == {}


# ── reachability: nothing is hardcoded ──────────────────────────────────────


def test_same_stock_different_target_gives_different_verdict():
    """2% daily ATR over three months is a ~16% budget: comfortable for 5%,
    merely plausible for 10%."""
    easy = metrics.reachability(2.0, horizon_months=3, target_gain_pct=5)
    hard = metrics.reachability(2.0, horizon_months=3, target_gain_pct=10)

    assert easy["expected_move_pct"] == hard["expected_move_pct"]
    assert easy["tier"] == "comfortable"
    assert hard["tier"] == "plausible"


def test_same_stock_different_horizon_gives_different_verdict():
    """Ten percent is out of reach for this stock in one month and within reach
    in three — the horizon has to change the answer."""
    short = metrics.reachability(2.0, horizon_months=1, target_gain_pct=10)
    long = metrics.reachability(2.0, horizon_months=3, target_gain_pct=10)

    assert short["tier"] == "too_slow"
    assert long["tier"] in metrics.RECOMMENDABLE_TIERS
    assert long["expected_move_pct"] > short["expected_move_pct"]


def test_expected_move_scales_with_the_square_root_of_time():
    one = metrics.reachability(2.0, 1, 10)["expected_move_pct"]
    four = metrics.reachability(2.0, 4, 10)["expected_move_pct"]
    assert four == pytest.approx(one * 2, rel=0.01)


def test_horizon_is_converted_to_trading_days():
    assert metrics.reachability(2.0, 3, 10)["horizon_trading_days"] == 63
    assert metrics.reachability(2.0, 1, 10)["horizon_trading_days"] == 21
    # Fractional months are allowed ("a couple of weeks") and never round to zero.
    assert metrics.reachability(2.0, 0.25, 10)["horizon_trading_days"] == 5


def test_very_volatile_stock_is_flagged_too_wild():
    """A stock that typically swings 60% is not a way to earn 5%."""
    assert metrics.reachability(8.0, 3, 5)["tier"] == "too_wild"


def test_unknown_atr_yields_unknown_tier():
    out = metrics.reachability(None, 3, 10)
    assert out["tier"] == "unknown"
    assert out["expected_move_pct"] is None


def test_tier_boundaries_are_configurable():
    """The thresholds live in settings, so an override must actually take effect."""
    strict = {"stretch": 5.0, "plausible": 8.0, "comfortable": 12.0, "too_wild": 50.0}
    assert metrics.reachability(2.0, 3, 10, strict)["tier"] == "too_slow"
    assert metrics.reachability(2.0, 3, 10)["tier"] == "plausible"


# ── trade levels ────────────────────────────────────────────────────────────


def test_trade_levels_target_and_stop_follow_the_caller():
    levels = metrics.trade_levels(price=100.0, daily_atr=2.0, target_gain_pct=10, atr_stop_multiple=2.0)
    assert levels["target_price"] == 110.0
    assert levels["stop_price"] == 96.0
    assert levels["risk_pct"] == pytest.approx(4.0)
    assert levels["reward_risk"] == pytest.approx(2.5)


def test_reward_risk_improves_with_a_bigger_target():
    tight = metrics.trade_levels(100.0, 2.0, 5, 2.0)["reward_risk"]
    wide = metrics.trade_levels(100.0, 2.0, 10, 2.0)["reward_risk"]
    assert wide > tight


def test_trade_levels_without_atr_still_gives_a_target():
    levels = metrics.trade_levels(100.0, None, 10, 2.0)
    assert levels["target_price"] == 110.0
    assert levels["stop_price"] is None
    assert levels["reward_risk"] is None


# ── strength ────────────────────────────────────────────────────────────────


def test_strength_counts_five_checks():
    from features.advisor.ranking import strength

    strong, checks = strength({
        "dist_to_ma50_pct": 5.0,
        "dist_to_ma200_pct": 12.0,
        "return_3m_pct": 8.0,
        "return_12m_1_pct": 30.0,
        "dist_to_52w_high_pct": 3.0,
    })
    assert strong == 100
    assert all(checks.values())

    weak, _ = strength({
        "dist_to_ma50_pct": -5.0,
        "dist_to_ma200_pct": -12.0,
        "return_3m_pct": -8.0,
        "return_12m_1_pct": -30.0,
        "dist_to_52w_high_pct": 45.0,
    })
    assert weak == 0


def test_strength_of_an_empty_snapshot_is_zero():
    from features.advisor.ranking import strength

    assert strength({})[0] == 0
