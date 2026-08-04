"""Tests for the overview arithmetic.

`compute_overview` decides the rupee amount the UI tells a user to trade, and
it had no direct coverage — it was only ever exercised incidentally through the
wiring and MCP tests, which assert shape rather than values.

These pin the behaviour: the money, the band logic, and the two concentration
caps. They are deliberately written against hand-computed numbers rather than
against the function's own output, so a change in the rules fails here instead
of quietly re-baselining.
"""
from __future__ import annotations

import pandas as pd
import pytest

from features.portfolio.compute import compute_overview


def holdings(*rows) -> pd.DataFrame:
    """(symbol, qty, avg_price, last_price) tuples -> a holdings frame."""
    return pd.DataFrame(
        [
            {
                "tradingsymbol": symbol,
                "quantity": qty,
                "average_price": avg,
                "last_price": ltp,
            }
            for symbol, qty, avg, ltp in rows
        ]
    )


def config(groups=None, targets=None, top5=35, single=5) -> dict:
    return {
        "groups": groups or {},
        "targets": targets or {},
        "concentration": {"top5": top5, "single": single},
    }


# ── empty ────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("frame", [None, pd.DataFrame()])
def test_no_holdings_yields_a_zeroed_payload(frame):
    result = compute_overview(frame, config())
    assert result["health"] == {
        "total_value": 0,
        "total_pnl": 0,
        "return_pct": 0,
        "capital_at_risk": 0,
    }
    assert result["allocation"] == []
    assert result["concentration"] == []


# ── health ───────────────────────────────────────────────────────────────────
def test_health_totals_and_capital_at_risk():
    # WINNER: invested 1000, value 1200 (+200). LOSER: invested 1000, value 800 (-200).
    result = compute_overview(
        holdings(("WINNER", 10, 100, 120), ("LOSER", 10, 100, 80)), config()
    )
    health = result["health"]

    assert health["total_value"] == 2000
    assert health["total_pnl"] == 0
    assert health["return_pct"] == 0
    # Only the losing position's *market value* counts, not its loss.
    assert health["capital_at_risk"] == 800


def test_return_pct_is_pnl_over_invested():
    result = compute_overview(holdings(("A", 10, 100, 125)), config())
    assert result["health"]["return_pct"] == pytest.approx(25.0)


# ── allocation bands ─────────────────────────────────────────────────────────
def test_group_over_its_band_is_trimmed_to_the_nearest_edge():
    # G2 holds 800 of a 2000 book = 40%, against a 20-30% band.
    result = compute_overview(
        holdings(("A", 10, 100, 120), ("B", 10, 100, 80)),
        config(groups={"G1": ["A"], "G2": ["B"]}, targets={"G1": [50, 60], "G2": [20, 30]}),
    )
    by_group = {row["group"]: row for row in result["allocation"]}

    # Trim back to the *max* edge (30%), not to the midpoint: 800 - 600.
    assert by_group["G2"]["action"] == {"type": "TRIM", "amount": 200}
    assert by_group["G2"]["target"] == "20-30%"
    # G1 sits exactly on its upper edge, which is inside the band.
    assert by_group["G1"]["allocation_pct"] == 60.0
    assert by_group["G1"]["action"] == {"type": "HOLD", "amount": 0}


def test_group_under_its_band_is_topped_up_to_the_nearest_edge():
    result = compute_overview(
        holdings(("A", 10, 100, 100), ("B", 30, 100, 100)),
        config(groups={"SMALL": ["A"], "BIG": ["B"]}, targets={"SMALL": [40, 50], "BIG": [0, 100]}),
    )
    small = next(r for r in result["allocation"] if r["group"] == "SMALL")

    # 1000 of a 4000 book = 25%; the floor is 40% = 1600, so add 600.
    assert small["action"] == {"type": "ADD", "amount": 600}


def test_group_without_a_target_is_reported_but_never_actioned():
    result = compute_overview(
        holdings(("A", 10, 100, 100)), config(groups={"G": ["A"]}, targets={})
    )
    row = result["allocation"][0]

    assert row["target"] == "-"
    assert row["action"] == {"type": "HOLD", "amount": 0}


def test_unclassified_symbols_fall_into_an_unassigned_bucket():
    # Nothing maps ORPHAN, so it must still appear in the book rather than
    # silently vanish from the totals.
    result = compute_overview(
        holdings(("A", 10, 100, 100), ("ORPHAN", 10, 100, 100)),
        config(groups={"G": ["A"]}, targets={"G": [0, 100]}),
    )
    by_group = {row["group"]: row for row in result["allocation"]}

    assert "Unassigned" in by_group
    assert by_group["Unassigned"]["value"] == 1000
    assert by_group["Unassigned"]["target"] == "-"


def test_a_symbol_listed_in_two_groups_belongs_to_the_first():
    # Nothing stops a user putting the same symbol in two groups. The rule is
    # first-listed-wins; the value must be counted once, in one group only.
    result = compute_overview(
        holdings(("DUPE", 10, 100, 100)),
        config(groups={"FIRST": ["DUPE"], "SECOND": ["DUPE"]}),
    )
    groups = {row["group"] for row in result["allocation"]}

    assert groups == {"FIRST"}
    assert result["allocation"][0]["value"] == 1000
    assert result["health"]["total_value"] == 1000


def test_pnl_pct_is_per_group_not_per_book():
    result = compute_overview(
        holdings(("A", 10, 100, 150), ("B", 10, 100, 100)),
        config(groups={"UP": ["A"], "FLAT": ["B"]}),
    )
    by_group = {row["group"]: row for row in result["allocation"]}

    assert by_group["UP"]["pnl_pct"] == pytest.approx(50.0)
    assert by_group["FLAT"]["pnl_pct"] == pytest.approx(0.0)


# ── concentration caps ───────────────────────────────────────────────────────
def test_top5_and_largest_breaches_are_reported_with_trim_amounts():
    # Six equal 1000-value positions except HUGE at 5000: book = 10000.
    rows = [("HUGE", 50, 100, 100)] + [(f"S{i}", 10, 100, 100) for i in range(5)]
    result = compute_overview(holdings(*rows), config(top5=35, single=5))
    top5, largest = result["concentration"]

    # Top 5 by value = HUGE + four others = 9000 of 10000 = 90%, cap 35% = 3500.
    assert top5["metric"] == "Top 5 Holdings"
    assert top5["value_pct"] == pytest.approx(90.0)
    assert top5["action"] == {"type": "TRIM", "amount": 5500}

    # Largest is HUGE at 50%, cap 5% = 500.
    assert largest["metric"] == "Largest Holding - HUGE"
    assert largest["value_pct"] == pytest.approx(50.0)
    assert largest["action"] == {"type": "TRIM", "amount": 4500}


def test_concentration_within_limits_holds():
    rows = [(f"S{i}", 10, 100, 100) for i in range(10)]  # ten equal 10% positions
    result = compute_overview(holdings(*rows), config(top5=60, single=15))
    top5, largest = result["concentration"]

    assert top5["value_pct"] == pytest.approx(50.0)
    assert top5["action"] == {"type": "HOLD", "amount": 0}
    assert largest["action"] == {"type": "HOLD", "amount": 0}


def test_a_single_holding_is_both_the_top5_and_the_largest():
    result = compute_overview(holdings(("ONLY", 10, 100, 100)), config(top5=35, single=5))
    top5, largest = result["concentration"]

    assert top5["value_pct"] == pytest.approx(100.0)
    assert largest["metric"] == "Largest Holding - ONLY"
    assert largest["value_pct"] == pytest.approx(100.0)
