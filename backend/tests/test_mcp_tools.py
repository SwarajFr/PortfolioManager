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
