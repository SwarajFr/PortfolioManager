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


def test_needs_kite_catches_data_layer_auth_error(monkeypatch):
    """The data service translates Kite auth failures into its own error type;
    the guard must recognise that translation too, not 500."""
    from core.data import NotAuthenticatedError

    _fake_login_url(monkeypatch)
    monkeypatch.setattr(guards, "is_authenticated", lambda: True)

    @guards.needs_kite
    def tool():
        raise NotAuthenticatedError("session expired mid-call")

    out = tool()
    assert out["status"] == "auth_required"
    assert "login_url" in out


# ── T4: portfolio_holdings ───────────────────────────────────────────────────
import features.mcp.portfolio_tools as portfolio_tools  # noqa: E402


def test_portfolio_holdings_formats_rows_and_totals(monkeypatch, market_data, stub_provider):
    monkeypatch.setattr(guards, "is_authenticated", lambda: True)
    stub_provider.holdings = [
        {"tradingsymbol": "INFY", "quantity": 10, "average_price": 100.0, "last_price": 150.0},
        {"tradingsymbol": "TCS", "quantity": 5, "average_price": 200.0, "last_price": 180.0},
    ]

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


def test_portfolio_holdings_empty(monkeypatch, market_data, stub_provider):
    monkeypatch.setattr(guards, "is_authenticated", lambda: True)
    stub_provider.holdings = []

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


# ── T6: advisor tools ────────────────────────────────────────────────────────
import features.mcp.advisor_tools as advisor_tools  # noqa: E402


def test_advisor_tools_pass_caller_params_through(monkeypatch):
    """The whole point of the rebuild: a horizon and target named in the user's
    question must reach the service untouched, not be replaced by a default."""
    monkeypatch.setattr(guards, "is_authenticated", lambda: True)
    seen = {}
    monkeypatch.setattr(
        advisor_tools, "_buy_ideas",
        lambda h, t, limit, exclude: seen.update(horizon=h, target=t, limit=limit) or {"ideas": []},
    )

    advisor_tools.buy_ideas(horizon_months=2, target_gain_pct=5, limit=3)
    assert seen == {"horizon": 2, "target": 5, "limit": 3}


def test_advisor_tools_omit_params_when_unspecified(monkeypatch):
    monkeypatch.setattr(guards, "is_authenticated", lambda: True)
    seen = {}
    monkeypatch.setattr(
        advisor_tools, "_portfolio_actions",
        lambda h, t, limit: seen.update(horizon=h, target=t) or {"sell": [], "topup": []},
    )

    advisor_tools.portfolio_actions()
    # None, not a hardcoded number — the service resolves it from the profile.
    assert seen == {"horizon": None, "target": None}


def test_advisor_tools_require_auth(monkeypatch):
    _fake_login_url(monkeypatch)
    monkeypatch.setattr(guards, "is_authenticated", lambda: False)

    for call in (
        advisor_tools.portfolio_actions,
        advisor_tools.buy_ideas,
        advisor_tools.advice_history,
        advisor_tools.investor_profile,
    ):
        assert call()["status"] == "auth_required"


def test_advisor_tools_all_registered():
    registered = []
    advisor_tools.register(type("Mcp", (), {"tool": lambda self, fn: registered.append(fn.__name__)})())
    assert registered == ["portfolio_actions", "buy_ideas", "advice_history", "investor_profile"]


# ── T7: quote ────────────────────────────────────────────────────────────────
import features.mcp.market_tools as market_tools  # noqa: E402


def test_quote_maps_symbols_and_rounds(monkeypatch, market_data, stub_provider):
    monkeypatch.setattr(guards, "is_authenticated", lambda: True)
    stub_provider.quotes = {"INFY": 1543.256, "TCS": 3890.0}

    out = market_tools.quote(["infy", "TCS"])

    assert stub_provider.quote_calls == [["INFY", "TCS"]]
    assert {"symbol": "INFY", "ltp": 1543.26} in out["quotes"]
    assert out["not_found"] == []


def test_quote_collects_not_found(monkeypatch, market_data, stub_provider):
    monkeypatch.setattr(guards, "is_authenticated", lambda: True)
    stub_provider.quotes = {"INFY": 1500.0}

    out = market_tools.quote(["INFY", "BOGUS"])
    assert [q["symbol"] for q in out["quotes"]] == ["INFY"]
    assert out["not_found"] == ["BOGUS"]


def test_quote_caps_symbol_count(monkeypatch, market_data, stub_provider):
    monkeypatch.setattr(guards, "is_authenticated", lambda: True)
    symbols = [f"S{i}" for i in range(60)]
    stub_provider.quotes = dict.fromkeys(symbols, 1.0)

    out = market_tools.quote(symbols)
    assert len(out["quotes"]) == 50  # capped, payload stays compact


def test_quote_empty_input(monkeypatch):
    monkeypatch.setattr(guards, "is_authenticated", lambda: True)
    out = market_tools.quote([])
    assert out == {"quotes": [], "not_found": []}


# ── T8: auth tools ───────────────────────────────────────────────────────────
import features.mcp.auth_tools as auth_tools  # noqa: E402


class _ProfileKite:
    def __init__(self, profile=None, raise_token=False):
        self._profile = profile or {}
        self._raise = raise_token

    def profile(self):
        if self._raise:
            raise TokenException("expired")
        return self._profile

    def login_url(self):
        return "http://login-url"


def test_session_status_unauthenticated(monkeypatch):
    monkeypatch.setattr(auth_tools, "is_authenticated", lambda: False)
    monkeypatch.setattr(auth_tools.kite, "login_url", lambda: "http://login-url")

    out = auth_tools.kite_session_status()
    assert out["authenticated"] is False
    assert out["token_valid"] is False
    assert out["login_url"] == "http://login-url"


def test_session_status_valid_probe(monkeypatch):
    monkeypatch.setattr(auth_tools, "is_authenticated", lambda: True)
    kobj = _ProfileKite(profile={"user_id": "AB1234"})
    monkeypatch.setattr(auth_tools, "get_kite", lambda: kobj)
    monkeypatch.setattr(auth_tools.kite, "login_url", lambda: "http://login-url")

    out = auth_tools.kite_session_status()
    assert out["authenticated"] is True
    assert out["token_valid"] is True
    assert out["user_id"] == "AB1234"


def test_session_status_expired_probe(monkeypatch):
    monkeypatch.setattr(auth_tools, "is_authenticated", lambda: True)
    monkeypatch.setattr(auth_tools, "get_kite", lambda: _ProfileKite(raise_token=True))
    monkeypatch.setattr(auth_tools.kite, "login_url", lambda: "http://login-url")

    out = auth_tools.kite_session_status()
    assert out["authenticated"] is True
    assert out["token_valid"] is False


def test_complete_login_success(monkeypatch):
    monkeypatch.setattr(auth_tools, "complete_login", lambda rt: {"user_id": "AB1234", "access_token": "tok"})
    out = auth_tools.kite_complete_login("req-token")
    assert out["status"] == "authenticated"
    assert out["user_id"] == "AB1234"


def test_complete_login_error(monkeypatch):
    def boom(rt):
        raise TokenException("bad request token")

    monkeypatch.setattr(auth_tools, "complete_login", boom)
    monkeypatch.setattr(auth_tools.kite, "login_url", lambda: "http://login-url")
    out = auth_tools.kite_complete_login("bad")
    assert out["status"] == "error"
    assert "login_url" in out
