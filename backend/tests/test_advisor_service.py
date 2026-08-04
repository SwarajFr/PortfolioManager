"""End-to-end advisor: real market data service, real exit/fragility/screener
layers, stub broker.

Nothing here patches a feature's internals — the stub provider is configured and
the whole chain runs, which is the only way to catch the wiring bugs that matter
(wrong lookback, cold cache, a filter that silently drops everything).
"""
from __future__ import annotations

import datetime

import pytest

import core.identity as identity
import core.settings_store as store
from features.advisor import journal, service
from features.screener import cache as screener_cache

from conftest import TODAY

USER = "AB1234"

#: Long enough for MA200 and for 12-1 momentum (252 + 21 bars).
BARS = 420

STRATEGIES = ["ma_crossover", "momentum_12_1", "breakout", "rsi_reversion", "high_52w"]


def _start(bars: int = BARS) -> datetime.date:
    return TODAY - datetime.timedelta(days=bars - 1)


def _rising(base: float, step: float = 0.05, bars: int = BARS) -> list[float]:
    """A smooth uptrend: above both averages, at its 52-week high, low volatility."""
    return [base + step * i for i in range(bars)]


def _falling(base: float, bars: int = BARS) -> list[float]:
    """A jagged decline: below both averages and far more volatile than the rest
    of the book, which is what the exit engine's risk KPIs key off."""
    return [base - 0.15 * i + (6.0 if i % 2 else -6.0) for i in range(bars)]


@pytest.fixture()
def account(monkeypatch, tmp_path):
    monkeypatch.setattr(store, "DB_PATH", str(tmp_path / "settings.db"))
    identity.set_active_user(USER)
    yield USER
    identity.set_active_user(None)


@pytest.fixture()
def portfolio(account, market_data, stub_provider):
    """25 holdings so individual weights land under the 5% concentration cap:
    one clear winner, one clear loser, and filler."""
    holdings = []

    # Sized to sit under the 5% cap: a winner already at the cap is correctly
    # refused a top-up, which would make this fixture test the wrong thing.
    stub_provider.set_series("WINNER", _start(), _rising(100.0, 0.12))
    holdings.append({"tradingsymbol": "WINNER", "instrument_token": 1, "quantity": 60,
                     "average_price": 100.0, "last_price": 150.0})

    stub_provider.set_series("LOSER", _start(), _falling(120.0))
    holdings.append({"tradingsymbol": "LOSER", "instrument_token": 2, "quantity": 100,
                     "average_price": 100.0, "last_price": 60.0})

    for i in range(23):
        symbol = f"FILL{i}"
        stub_provider.set_series(symbol, _start(), _rising(100.0, 0.01))
        holdings.append({"tradingsymbol": symbol, "instrument_token": 10 + i,
                         "quantity": 100, "average_price": 100.0, "last_price": 105.0})

    stub_provider.holdings = holdings
    return stub_provider


@pytest.fixture()
def universe(account, market_data, stub_provider):
    """Three screener candidates. The stub's bars are always ±1 wide, so the
    price level alone sets ATR% — 25 is wild, 100 is workable, 500 is sluggish."""
    prices = {"WILD": 25.0, "GOOD": 100.0, "SLOW": 500.0}
    for i, (symbol, base) in enumerate(prices.items()):
        stub_provider.set_series(symbol, _start(), _rising(base, base * 0.0005))
        stub_provider.set_instruments("NSE", {symbol: 100 + i for symbol in prices})
        screener_cache.upsert_signal(
            symbol,
            TODAY.isoformat(),
            {name: 1.0 - i * 0.1 for name in STRATEGIES},
            {name: True for name in STRATEGIES},
        )
    # Prime the candle cache the way the login refresh would, so buy_ideas can
    # read it without touching the provider.
    market_data.get_history_batch(list(prices), lookback_days=service.LOOKBACK_DAYS)
    return prices


# ── question 1: sell / top up ───────────────────────────────────────────────


def test_portfolio_actions_flags_the_loser_for_sale(portfolio):
    out = service.portfolio_actions()

    assert [c["symbol"] for c in out["sell"]] == ["LOSER"]
    sell = out["sell"][0]
    assert sell["action"] in ("EXIT", "TRIM")
    assert sell["suggested_qty"] > 0
    assert sell["return_pct"] == pytest.approx(-40.0)


def test_sell_reasons_are_written_out_with_numbers(portfolio):
    sell = service.portfolio_actions()["sell"][0]
    codes = {r["code"] for r in sell["reasons"]}

    assert "loss_severity" in codes
    assert {"trend_weakness_both", "trend_weakness_short"} & codes
    for reason in sell["reasons"]:
        assert reason["text"] and "{" not in reason["text"]


def test_portfolio_actions_suggests_topping_up_the_winner(portfolio):
    out = service.portfolio_actions()

    topups = {c["symbol"] for c in out["topup"]}
    assert "WINNER" in topups
    assert "LOSER" not in topups  # never averages down

    winner = next(c for c in out["topup"] if c["symbol"] == "WINNER")
    assert winner["headroom_pct"] > 0
    assert winner["suggested_amount"] > 0
    assert winner["strength"] >= 60


def test_topup_horizon_and_target_come_from_the_caller(portfolio):
    default = service.portfolio_actions()
    custom = service.portfolio_actions(horizon_months=2, target_gain_pct=5)

    assert default["horizon_months"] == 3 and default["target_gain_pct"] == 10
    assert custom["horizon_months"] == 2 and custom["target_gain_pct"] == 5

    winner = next(c for c in custom["topup"] if c["symbol"] == "WINNER")
    assert winner["reachability"]["horizon_trading_days"] == 42


def test_portfolio_actions_on_an_empty_account(account, market_data, stub_provider):
    stub_provider.holdings = []
    out = service.portfolio_actions()

    assert out["sell"] == [] and out["topup"] == []
    assert out["notes"] and "No holdings" in out["notes"][0]


def test_portfolio_actions_records_what_it_recommended(portfolio):
    service.portfolio_actions()

    kinds = {e["kind"] for e in journal.read()}
    assert "sell" in kinds
    symbols = {e["symbol"] for e in journal.read(kind="sell")}
    assert "LOSER" in symbols


# ── question 2: what to buy ─────────────────────────────────────────────────


def test_buy_ideas_keeps_only_reachable_candidates(portfolio, universe):
    out = service.buy_ideas(horizon_months=3, target_gain_pct=10)

    assert [c["symbol"] for c in out["ideas"]] == ["GOOD"]
    counts = out["excluded"]["counts"]
    assert counts.get("too_slow") == 1  # SLOW
    assert counts.get("too_wild") == 1  # WILD


def test_buy_ideas_change_with_the_horizon_and_target(portfolio, universe):
    """The requirement that shaped the feature: different question, different list."""
    modest = service.buy_ideas(horizon_months=3, target_gain_pct=10)
    ambitious = service.buy_ideas(horizon_months=3, target_gain_pct=20)

    # Same universe, same horizon, opposite answers. Asking for 10% picks the
    # steady name and rejects the volatile one as overkill; asking for 20% in the
    # same three months inverts it — the steady name can no longer get there, and
    # only the volatile one can.
    assert [c["symbol"] for c in modest["ideas"]] == ["GOOD"]
    assert modest["excluded"]["counts"].get("too_wild") == 1

    assert [c["symbol"] for c in ambitious["ideas"]] == ["WILD"]
    assert ambitious["excluded"]["counts"].get("too_slow") == 2


def test_shortening_the_horizon_can_leave_nothing_suitable(portfolio, universe):
    """An empty list is a real answer. Nothing here can cover 10% in a month
    without risking more than it stands to gain, and saying so beats padding."""
    out = service.buy_ideas(horizon_months=1, target_gain_pct=10)

    assert out["ideas"] == []
    counts = out["excluded"]["counts"]
    assert counts.get("too_slow") == 2  # GOOD and SLOW cannot get there in time
    assert counts.get("poor_reward_risk") == 1  # WILD can, but not safely
    assert out["notes"]


def test_buy_idea_carries_entry_target_stop_and_reasons(portfolio, universe):
    idea = service.buy_ideas(horizon_months=3, target_gain_pct=10)["ideas"][0]

    assert idea["target_price"] == pytest.approx(idea["ltp"] * 1.1, rel=1e-3)
    assert idea["stop_price"] < idea["ltp"]
    assert idea["reward_risk"] > 0
    assert idea["reachability"]["tier"] in ("stretch", "plausible", "comfortable")
    for reason in idea["reasons"]:
        assert reason["text"] and "{" not in reason["text"]


def test_buy_ideas_reads_the_cache_without_calling_the_broker(portfolio, universe, stub_provider):
    """A chat message must not turn 60 shortlisted symbols into 60 broker
    round-trips — the screener refresh already filled this cache."""
    before = len(stub_provider.candle_calls)
    service.buy_ideas(horizon_months=3, target_gain_pct=10)
    assert len(stub_provider.candle_calls) == before


def test_buy_ideas_excludes_what_is_already_held(account, market_data, stub_provider, universe):
    stub_provider.holdings = [
        {"tradingsymbol": "GOOD", "instrument_token": 101, "quantity": 10,
         "average_price": 90.0, "last_price": 100.0}
    ]

    excluded = service.buy_ideas(horizon_months=3, target_gain_pct=10)
    assert excluded["ideas"] == []
    assert excluded["excluded"]["counts"].get("held") == 1

    included = service.buy_ideas(horizon_months=3, target_gain_pct=10, exclude_held=False)
    assert [c["symbol"] for c in included["ideas"]] == ["GOOD"]
    assert included["ideas"][0]["already_held"] is True


def test_buy_ideas_says_so_when_the_screener_cache_is_empty(portfolio):
    out = service.buy_ideas()
    assert out["ideas"] == []
    assert "screener cache is empty" in out["notes"][0]


def test_buy_ideas_respects_the_avoid_list(portfolio, universe):
    from features.advisor.settings import save_advisor_settings

    save_advisor_settings({"profile": {"avoid_symbols": ["GOOD"]}})
    out = service.buy_ideas(horizon_months=3, target_gain_pct=10)

    assert out["ideas"] == []
    assert out["excluded"]["counts"].get("avoided") == 1


def test_buy_ideas_uses_profile_defaults_when_unasked(portfolio, universe):
    from features.advisor.settings import save_advisor_settings

    save_advisor_settings({"profile": {"default_horizon_months": 6, "default_target_gain_pct": 20}})
    out = service.buy_ideas()

    assert out["horizon_months"] == 6
    assert out["target_gain_pct"] == 20
    assert out["horizon_band"] == "medium"


def test_horizon_selects_the_strategy_mix(portfolio, universe):
    assert service.buy_ideas(horizon_months=1)["horizon_band"] == "short"
    assert service.buy_ideas(horizon_months=4)["horizon_band"] == "medium"
    assert service.buy_ideas(horizon_months=12)["horizon_band"] == "long"


# ── memory ──────────────────────────────────────────────────────────────────


def test_advice_history_replays_past_calls_against_the_current_price(portfolio, universe, stub_provider):
    stub_provider.quotes["GOOD"] = 120.0
    service.buy_ideas(horizon_months=3, target_gain_pct=10)

    history = service.advice_history()
    entry = next(e for e in history["entries"] if e["symbol"] == "GOOD")

    assert entry["kind"] == "buy"
    assert entry["price_now"] == 120.0
    assert entry["move_since_pct"] == pytest.approx(
        (120.0 - entry["price"]) / entry["price"] * 100, abs=0.01  # stored to 2dp
    )


def test_advice_history_is_empty_before_anything_is_recommended(account, market_data):
    out = service.advice_history()
    assert out["entries"] == []
    assert "No recommendations" in out["note"]


def test_investor_profile_reports_defaults_and_the_weight_cap(account, market_data):
    out = service.investor_profile()

    assert out["profile"]["risk_tolerance"] == "balanced"
    assert out["defaults_in_use"]["horizon_months"] == 3
    assert out["defaults_in_use"]["single_holding_cap_pct"] == 5
