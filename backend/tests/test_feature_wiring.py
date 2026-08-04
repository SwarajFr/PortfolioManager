"""Every feature reads market data through the shared service.

These tests drive Portfolio, Exit and Fragility end-to-end with only the stub
provider configured — no feature-level patching. If a feature reached around the
data service to Kite, it would fail here.
"""
from __future__ import annotations

import datetime

import pytest

from features.exit import service as exit_service
from features.fragility import service as fragility_service
from features.portfolio import service as portfolio_service

HOLDINGS = [
    {
        "tradingsymbol": "AAA",
        "instrument_token": 1,
        "quantity": 10,
        "average_price": 100.0,
        "last_price": 150.0,
    },
    {
        "tradingsymbol": "BBB",
        "instrument_token": 2,
        "quantity": 5,
        "average_price": 200.0,
        "last_price": 180.0,
    },
]


@pytest.fixture()
def portfolio(market_data, stub_provider):
    """Two holdings with three years of prices behind them."""
    stub_provider.holdings = list(HOLDINGS)
    stub_provider.set_instruments("NSE", {"AAA": 1, "BBB": 2})
    start = datetime.date(2023, 6, 1)
    stub_provider.set_series("AAA", start, [100.0 + (i % 17) for i in range(1000)])
    stub_provider.set_series("BBB", start, [200.0 - (i % 23) for i in range(1000)])
    return stub_provider


# ── Portfolio ────────────────────────────────────────────────────────────────
def test_portfolio_overview_reads_holdings_from_the_service(portfolio):
    out = portfolio_service.get_overview()

    assert out["health"]["total_value"] == pytest.approx(2400.0)  # 1500 + 900
    assert out["health"]["total_pnl"] == pytest.approx(400.0)
    # Largest holding is named in the concentration block.
    assert any("AAA" in row["metric"] for row in out["concentration"])
    assert portfolio.holdings_calls == 1


# ── Exit ─────────────────────────────────────────────────────────────────────
def test_exit_signals_score_every_holding(portfolio):
    out = exit_service.get_exit_signals()

    assert {s["symbol"] for s in out["signals"]} == {"AAA", "BBB"}
    assert out["summary"]["total_holdings"] == 2
    # A non-zero median volatility proves history actually reached the scorer;
    # the token-keyed history dict is rebuilt from the symbol-keyed service.
    assert out["summary"]["median_volatility"] > 0
    for signal in out["signals"]:
        assert signal["action"] in {"HOLD", "WATCH", "TRIM", "EXIT"}


def test_exit_signals_request_one_year_of_history(portfolio):
    exit_service.get_exit_signals()
    _, start, end = portfolio.candle_calls[0]
    assert (end - start).days == exit_service.LOOKBACK_DAYS


def test_exit_signals_reuse_the_cache_on_a_second_request(portfolio):
    exit_service.get_exit_signals()
    calls_after_first = len(portfolio.candle_calls)

    exit_service.get_exit_signals()

    # Previously every request re-downloaded a year of candles per holding.
    assert len(portfolio.candle_calls) == calls_after_first


# ── Fragility ────────────────────────────────────────────────────────────────
def test_fragility_analysis_runs_on_service_prices(portfolio):
    out = fragility_service.get_diversity_analysis()

    assert out["scalars"]["num_positions"] == 2
    assert out["scalars"]["portfolio_vol"] > 0
    assert set(out["correlation"]["symbols"]) == {"AAA", "BBB"}


def test_fragility_requests_its_deeper_window(portfolio):
    fragility_service.get_diversity_analysis()
    _, start, end = portfolio.candle_calls[0]
    assert (end - start).days == fragility_service.MAX_LOOKBACK_DAYS


def test_fragility_weights_use_holding_value(portfolio):
    import pandas as pd

    holdings = pd.DataFrame(HOLDINGS)
    prices = pd.DataFrame({"AAA": [1.0], "BBB": [1.0]})

    weights = fragility_service._weights(holdings, prices)

    assert weights["AAA"] == pytest.approx(1500 / 2400)
    assert weights["BBB"] == pytest.approx(900 / 2400)
    assert sum(weights.values()) == pytest.approx(1.0)


def test_fragility_drops_unpriced_tickers_from_weights(portfolio):
    import pandas as pd

    holdings = pd.DataFrame(HOLDINGS)
    prices = pd.DataFrame({"AAA": [1.0]})  # BBB never priced

    assert set(fragility_service._weights(holdings, prices)) == {"AAA"}


def test_fragility_empty_holdings_returns_empty_payload(market_data, stub_provider):
    stub_provider.holdings = []
    out = fragility_service.get_diversity_analysis()
    assert out["scalars"]["num_positions"] == 0
    assert out["correlation"]["symbols"] == []


# ── the shared cache is genuinely shared ─────────────────────────────────────
def test_exit_reuses_history_the_screener_already_cached(portfolio):
    """One store, one symbol, one download — regardless of who asked first."""
    from core.data import InstrumentRef, get_market_data

    get_market_data().refresh_history(
        [InstrumentRef(symbol="AAA", token=1)],
        lookback_days=fragility_service.MAX_LOOKBACK_DAYS,
        seed=True,
        today=datetime.date(2026, 1, 20),
    )
    portfolio.candle_calls.clear()

    exit_service.get_exit_signals()

    fetched = {symbol for symbol, _, _ in portfolio.candle_calls}
    assert "AAA" not in fetched  # already cached by the refresh
    assert "BBB" in fetched
