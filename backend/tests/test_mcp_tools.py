from kiteconnect.exceptions import TokenException

import features.mcp.guards as guards


def _fake_login_url(monkeypatch):
    monkeypatch.setattr(guards.kite, "login_url", lambda: "http://login-url")


def test_needs_kite_passes_through_when_authenticated(monkeypatch):
    _fake_login_url(monkeypatch)
    monkeypatch.setattr(guards, "is_authenticated", lambda: True)

    @guards.needs_kite
    def tool():
        return {"ok": True}

    assert tool() == {"ok": True}


def test_needs_kite_blocks_when_unauthenticated(monkeypatch):
    _fake_login_url(monkeypatch)
    monkeypatch.setattr(guards, "is_authenticated", lambda: False)

    @guards.needs_kite
    def tool():
        raise AssertionError("must not run")

    out = tool()
    assert out["status"] == "auth_required"
    assert out["login_url"] == "http://login-url"


def test_needs_kite_catches_token_exception(monkeypatch):
    _fake_login_url(monkeypatch)
    monkeypatch.setattr(guards, "is_authenticated", lambda: True)

    @guards.needs_kite
    def tool():
        raise TokenException("Token is invalid or has expired.")

    out = tool()
    assert out["status"] == "auth_required"
    assert "login_url" in out


# ── T4: portfolio_holdings ───────────────────────────────────────────────────
import pandas as pd  # noqa: E402

import features.mcp.portfolio_tools as portfolio_tools  # noqa: E402


def test_portfolio_holdings_formats_rows_and_totals(monkeypatch):
    monkeypatch.setattr(guards, "is_authenticated", lambda: True)
    df = pd.DataFrame([
        {"tradingsymbol": "INFY", "quantity": 10, "average_price": 100.0, "last_price": 150.0},
        {"tradingsymbol": "TCS", "quantity": 5, "average_price": 200.0, "last_price": 180.0},
    ])
    monkeypatch.setattr(portfolio_tools, "get_holdings", lambda: df)

    out = portfolio_tools.portfolio_holdings()

    # Sorted by value desc: INFY (1500) before TCS (900)
    assert [h["symbol"] for h in out["holdings"]] == ["INFY", "TCS"]
    infy = out["holdings"][0]
    assert infy["value"] == 1500.0
    assert infy["pnl"] == 500.0
    assert infy["pnl_pct"] == 50.0
    assert out["totals"]["value"] == 2400.0
    assert out["totals"]["invested"] == 2000.0
    assert out["totals"]["pnl"] == 400.0
    assert out["totals"]["num_holdings"] == 2
    # No raw instrument tokens leak
    assert "instrument_token" not in infy


def test_portfolio_holdings_empty(monkeypatch):
    monkeypatch.setattr(guards, "is_authenticated", lambda: True)
    monkeypatch.setattr(portfolio_tools, "get_holdings", lambda: pd.DataFrame())

    out = portfolio_tools.portfolio_holdings()
    assert out["holdings"] == []
    assert out["totals"]["num_holdings"] == 0


# ── T5: portfolio_metrics ────────────────────────────────────────────────────
import features.mcp.fragility_tools as fragility_tools  # noqa: E402


_FULL_ANALYSIS = {
    "scalars": {
        "num_positions": 8,
        "diversification_ratio": 1.42,
        "enb": 3.1,
        "effective_positions": 5.4,
        "normalized_entropy": 0.81,
        "weight_entropy": 1.68,
        "concentration_gap": 1.74,
        "portfolio_vol": 0.184,
        "portfolio_vol_daily": 0.0116,
        "portfolio_variance": 0.000134,
        "avg_correlation": 0.36,
        "max_correlation": 0.72,
    },
    "max_correlation_pair": ["INFY", "TCS"],
    "principal_risk_contributions": [0.4, 0.2],
    "principal_bets": [[{"symbol": "INFY", "loading": 0.7, "weight": 0.49}]],
    "correlation": {"symbols": ["INFY", "TCS"], "matrix": [[1.0, 0.72], [0.72, 1.0]]},
    "tickers_excluded": ["NEWSTOCK"],
}


def test_portfolio_metrics_is_compact(monkeypatch):
    monkeypatch.setattr(guards, "is_authenticated", lambda: True)
    monkeypatch.setattr(fragility_tools, "get_diversity_analysis", lambda: _FULL_ANALYSIS)

    out = fragility_tools.portfolio_metrics()

    assert out["num_positions"] == 8
    assert out["diversification_ratio"] == 1.42
    assert out["enb"] == 3.1
    assert out["max_correlation_pair"] == ["INFY", "TCS"]
    assert out["top_principal_bet"] == [{"symbol": "INFY", "loading": 0.7, "weight": 0.49}]
    assert out["tickers_excluded"] == ["NEWSTOCK"]
    # The raw matrix must NOT be in the payload
    assert "correlation" not in out
    assert "matrix" not in out


def test_portfolio_metrics_empty(monkeypatch):
    monkeypatch.setattr(guards, "is_authenticated", lambda: True)
    empty = {"scalars": {"num_positions": 0}, "tickers_excluded": []}
    monkeypatch.setattr(fragility_tools, "get_diversity_analysis", lambda: empty)

    out = fragility_tools.portfolio_metrics()
    assert out["num_positions"] == 0
    assert "note" in out


# ── T6: screen_strategy ──────────────────────────────────────────────────────
import features.mcp.screener_tools as screener_tools  # noqa: E402


def test_screen_strategy_top_n_and_total(monkeypatch):
    results = [{"symbol": f"S{i}", "score": float(50 - i)} for i in range(30)]
    monkeypatch.setattr(
        screener_tools, "get_individual",
        lambda name: {"strategy": name, "results": results, "last_updated": "2026-07-25T18:00:00"},
    )

    out = screener_tools.screen_strategy("momentum_12_1", limit=5)
    assert out["total_matches"] == 30
    assert len(out["top"]) == 5
    assert out["top"][0]["symbol"] == "S0"
    assert out["strategy"] == "momentum_12_1"
    assert out["universe"] == "NSE500"
    assert out["last_updated"] == "2026-07-25T18:00:00"


def test_screen_strategy_unknown_name():
    out = screener_tools.screen_strategy("not_a_strategy")
    assert "error" in out
    assert "ma_crossover" in out["valid_strategies"]


def test_screen_strategy_unsupported_universe():
    out = screener_tools.screen_strategy("breakout", universe="SP500")
    assert "error" in out
    assert out["supported_universes"] == ["NSE500"]


def test_screen_strategy_empty_cache(monkeypatch):
    monkeypatch.setattr(
        screener_tools, "get_individual",
        lambda name: {"strategy": name, "results": [], "last_updated": None},
    )
    out = screener_tools.screen_strategy("breakout")
    assert out["total_matches"] == 0
    assert "note" in out
