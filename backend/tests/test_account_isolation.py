"""Account isolation: no data from one Zerodha account may reach another.

These are security assertions. Each test names the leak it closes (L1-L4 in
.claude/specs/2026-08-03-account-isolation-design.md), so a failure here is a
data-exposure regression, not a style nit.
"""
from __future__ import annotations

from dataclasses import replace

import pytest
from conftest import build_test_service

import core.identity as identity
import core.kite as kite_mod
import core.settings_store as store
from core.data import set_market_data
from features.auth import service as auth_service

USER_A = "AB1234"
USER_B = "XY9876"


@pytest.fixture(autouse=True)
def _isolated_settings_db(monkeypatch, tmp_path):
    """Every test gets its own settings.db and a clean identity."""
    monkeypatch.setattr(store, "DB_PATH", str(tmp_path / "settings.db"))
    identity.set_active_user(None)
    yield
    identity.set_active_user(None)


# ── L2: settings are scoped per account ──────────────────────────────────────


def test_settings_written_under_one_account_are_invisible_to_another():
    identity.set_active_user(USER_A)
    store.save_settings("exit_settings", {"threshold": 80})

    identity.set_active_user(USER_B)

    assert store.load_settings("exit_settings", {"threshold": 50}) == {"threshold": 50}


def test_switching_back_restores_the_original_accounts_settings():
    identity.set_active_user(USER_A)
    store.save_settings("exit_settings", {"threshold": 80})
    identity.set_active_user(USER_B)
    store.save_settings("exit_settings", {"threshold": 20})

    identity.set_active_user(USER_A)

    assert store.load_settings("exit_settings", {})["threshold"] == 80


def test_global_tables_are_shared_across_accounts():
    """Market-data and screener config are infrastructure, not user data."""
    identity.set_active_user(USER_A)
    store.save_settings("market_data_settings", {"rate_limit_rps": 7})

    identity.set_active_user(USER_B)

    assert store.load_settings("market_data_settings", {})["rate_limit_rps"] == 7


def test_user_scoped_read_without_an_active_user_returns_defaults():
    """No active user must never fall through to some other account's row."""
    identity.set_active_user(USER_A)
    store.save_settings("exit_settings", {"threshold": 80})

    identity.set_active_user(None)

    assert store.load_settings("exit_settings", {"threshold": 50}) == {"threshold": 50}


def test_global_tables_readable_before_login():
    identity.set_active_user(None)
    store.save_settings("market_data_settings", {"rate_limit_rps": 3})

    assert store.load_settings("market_data_settings", {})["rate_limit_rps"] == 3


# ── L3 / L4: the persisted session carries an identity ───────────────────────


def test_session_persists_the_user_id(monkeypatch):
    monkeypatch.setattr(kite_mod.kite, "set_access_token", lambda t: None)

    kite_mod.set_access_token("tok-123", USER_A)

    saved = store.load_settings("kite_session", {})
    assert saved["access_token"] == "tok-123"
    assert saved["user_id"] == USER_A


def test_login_sets_the_active_user(monkeypatch):
    monkeypatch.setattr(kite_mod.kite, "set_access_token", lambda t: None)

    kite_mod.set_access_token("tok-123", USER_A)

    assert identity.get_active_user() == USER_A


def test_restored_session_restores_the_active_user(monkeypatch):
    monkeypatch.setattr(kite_mod.kite, "set_access_token", lambda t: None)
    store.save_settings(
        "kite_session",
        {"access_token": "tok-abc", "user_id": USER_A, "ist_date": kite_mod._today_ist()},
    )

    kite_mod._access_token = None
    kite_mod._load_persisted_token()

    assert kite_mod.is_authenticated() is True
    assert identity.get_active_user() == USER_A


def test_legacy_session_without_user_id_is_rejected(monkeypatch):
    """A row written before this change has no owner. Resuming it would leave
    the app authenticated as an unidentified account (L3)."""
    monkeypatch.setattr(kite_mod.kite, "set_access_token", lambda t: None)
    store.save_settings(
        "kite_session", {"access_token": "tok-legacy", "ist_date": kite_mod._today_ist()}
    )

    kite_mod._access_token = None
    kite_mod._load_persisted_token()

    assert kite_mod._access_token is None
    assert kite_mod.is_authenticated() is False
    assert identity.get_active_user() is None


# ── L1: cached broker state does not survive an account change ───────────────


def _login_as(monkeypatch, user_id, token="tok"):
    monkeypatch.setattr(
        auth_service.kite,
        "generate_session",
        lambda rt, api_secret: {"access_token": token, "user_id": user_id},
    )
    monkeypatch.setattr(auth_service.kite, "set_access_token", lambda t: None)
    monkeypatch.setattr(auth_service, "screener_on_login", lambda: None)
    return auth_service.complete_login("req-token")


@pytest.fixture()
def caching_service(stub_provider, data_config):
    """The real service with holdings caching actually switched on — the default
    config disables TTLs, which would mask the leak these tests probe."""
    service = build_test_service(stub_provider, replace(data_config, holdings_ttl_seconds=300))
    set_market_data(service)
    yield service
    set_market_data(None)


def test_holdings_cached_for_one_account_are_not_served_to_the_next(
    monkeypatch, stub_provider, caching_service
):
    """The holdings TTL cache was keyed on the literal string 'holdings', so a
    switch inside the TTL window served the previous account's portfolio (L1)."""
    stub_provider.holdings = [{"tradingsymbol": "INFY", "quantity": 10}]
    _login_as(monkeypatch, USER_A)

    assert caching_service.get_holdings().iloc[0]["tradingsymbol"] == "INFY"
    caching_service.get_holdings()
    assert stub_provider.holdings_calls == 1, "second read should hit the cache"

    stub_provider.holdings = [{"tradingsymbol": "TCS", "quantity": 5}]
    _login_as(monkeypatch, USER_B)

    assert caching_service.get_holdings().iloc[0]["tradingsymbol"] == "TCS"
    assert stub_provider.holdings_calls == 2


def test_relogin_as_the_same_account_keeps_the_cache(
    monkeypatch, stub_provider, caching_service
):
    """Purging is for identity *changes*; a token refresh should not throw away
    a warm cache."""
    stub_provider.holdings = [{"tradingsymbol": "INFY", "quantity": 10}]
    _login_as(monkeypatch, USER_A)
    caching_service.get_holdings()

    _login_as(monkeypatch, USER_A, token="tok-refreshed")
    caching_service.get_holdings()

    assert stub_provider.holdings_calls == 1


# ── defence in depth ─────────────────────────────────────────────────────────


def test_complete_login_does_not_return_the_access_token(monkeypatch, caching_service):
    result = _login_as(monkeypatch, USER_A)

    assert "access_token" not in result
    assert result["user_id"] == USER_A
