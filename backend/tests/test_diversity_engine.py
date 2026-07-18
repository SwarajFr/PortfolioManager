"""Tests for the descriptive DiversityEngine.

Synthetic returns with a known correlation/weight structure let us assert the
math directly. PCA-ENB is basis-dependent under eigenvalue degeneracy, so the
independent-asset ENB is checked as a range/ordering, never as a point value
(it lands ~3.7, not 5, for 5 independent assets — that is expected).
"""
from __future__ import annotations

import json
import math

import numpy as np
import pandas as pd
import pytest

from features.fragility.engine import DiversityEngine

COLS = ["A", "B", "C", "D", "E"]
T = 4000


def _independent_returns(seed: int = 0) -> pd.DataFrame:
    """5 independent, equal-vol assets."""
    rng = np.random.default_rng(seed)
    data = rng.standard_normal((T, 5)) * 0.01
    return pd.DataFrame(data, columns=COLS)


def _correlated_returns(rho: float = 0.95, seed: int = 1) -> pd.DataFrame:
    """5 equal-vol assets sharing a single common factor -> pairwise corr = rho."""
    rng = np.random.default_rng(seed)
    f = rng.standard_normal((T, 1))
    eps = rng.standard_normal((T, 5))
    data = (math.sqrt(rho) * f + math.sqrt(1.0 - rho) * eps) * 0.01
    return pd.DataFrame(data, columns=COLS)


def _equal_weights() -> pd.Series:
    return pd.Series([0.2] * 5, index=COLS)


def test_independent_equal_weight_diversification_ratio():
    result = DiversityEngine().run(_independent_returns(), _equal_weights())
    # DR = sqrt(N) for N independent equal-vol equal-weight assets.
    assert result.diversification_ratio == pytest.approx(math.sqrt(5), abs=0.15)


def test_independent_equal_weight_effective_positions():
    result = DiversityEngine().run(_independent_returns(), _equal_weights())
    # exp(H) with equal weights is exactly N, independent of the returns.
    assert result.effective_positions == pytest.approx(5.0, abs=1e-9)


def test_independent_enb_in_range():
    result = DiversityEngine().run(_independent_returns(), _equal_weights())
    # ENB is bounded above by N; allow a float epsilon at the boundary.
    assert 1.0 <= result.enb <= 5.0 + 1e-6


def test_highly_correlated_diversification_ratio_near_one():
    result = DiversityEngine().run(_correlated_returns(0.95), _equal_weights())
    assert result.diversification_ratio == pytest.approx(1.0, abs=0.2)
    assert result.diversification_ratio >= 1.0


def test_highly_correlated_enb_near_one():
    result = DiversityEngine().run(_correlated_returns(0.95), _equal_weights())
    assert 1.0 <= result.enb < 1.5


def test_enb_ordering_independent_beats_correlated():
    enb_indep = DiversityEngine().run(_independent_returns(), _equal_weights()).enb
    enb_corr = DiversityEngine().run(_correlated_returns(0.95), _equal_weights()).enb
    assert enb_indep > enb_corr


def test_concentrated_weights_low_effective_positions():
    weights = pd.Series([0.85, 0.08, 0.04, 0.02, 0.01], index=COLS)
    result = DiversityEngine().run(_independent_returns(), weights)
    assert result.effective_positions < 2.0


def test_weighted_symbol_without_returns_errors():
    weights = pd.Series([0.5, 0.3, 0.2], index=["A", "B", "Z"])
    with pytest.raises(ValueError):
        DiversityEngine().run(_independent_returns(), weights)


def test_concentration_gap_is_positions_over_enb():
    result = DiversityEngine().run(_independent_returns(), _equal_weights())
    assert result.concentration_gap == pytest.approx(
        result.effective_positions / result.enb, rel=1e-9
    )


def test_principal_bets_align_with_contributions():
    result = DiversityEngine().run(_independent_returns(), _equal_weights())
    # One bet per principal component, in the same order as the contributions.
    assert len(result.principal_bets) == len(result.principal_risk_contributions) == 5
    for bet in result.principal_bets:
        assert len(bet) >= 2  # every bet names at least its two dominant holdings
        for member in bet:
            assert member["symbol"] in COLS
            assert -1.0 <= member["loading"] <= 1.0
            assert 0.0 <= member["weight"] <= 1.0
        # Squared loadings are shares of the bet's direction: never exceed 1.
        assert sum(m["weight"] for m in bet) <= 1.0 + 1e-6


def test_dominant_bet_names_the_common_factor():
    # A single 0.95-correlation factor: the top bet is ~equal parts of all names.
    result = DiversityEngine().run(_correlated_returns(0.95), _equal_weights())
    top_bet = result.principal_bets[0]
    assert {m["symbol"] for m in top_bet} == set(COLS)
    for member in top_bet:
        assert member["weight"] == pytest.approx(0.2, abs=0.08)


def test_to_dict_is_json_serializable():
    result = DiversityEngine().run(_independent_returns(), _equal_weights())
    payload = result.to_dict()
    # Must not raise — no numpy scalars/arrays leaking through.
    dumped = json.dumps(payload)
    assert isinstance(dumped, str)
    # Shape the FastAPI route + React component depend on.
    assert set(payload) >= {
        "scalars",
        "principal_risk_contributions",
        "correlation",
    }
    assert set(payload["scalars"]) >= {
        "diversification_ratio",
        "enb",
        "effective_positions",
        "concentration_gap",
        "portfolio_vol",
    }
    assert payload["correlation"]["symbols"] == COLS
    assert len(payload["correlation"]["matrix"]) == 5
    # Math-only: no sector / asset-class data (Kite doesn't provide it).
    assert "sector_weights" not in payload
    assert "asset_class_weights" not in payload
    assert "sector_hhi" not in payload["scalars"]
    assert "asset_class_hhi" not in payload["scalars"]
