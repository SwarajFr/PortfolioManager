"""The recommendation journal: dedupe, cap, and account isolation.

The isolation assertions here are security assertions, not style ones — the
journal records what a specific person was told to buy and sell.
"""
from __future__ import annotations

import pytest

import core.identity as identity
import core.settings_store as store
from core.settings_store import NoActiveUserError
from features.advisor import journal

USER_A = "AB1234"
USER_B = "XY9876"


@pytest.fixture(autouse=True)
def _isolated_settings_db(monkeypatch, tmp_path):
    monkeypatch.setattr(store, "DB_PATH", str(tmp_path / "settings.db"))
    identity.set_active_user(USER_A)
    yield
    identity.set_active_user(None)


def entry(symbol, kind="buy", **over):
    return {"kind": kind, "symbol": symbol, "price": 100.0, **over}


def test_records_and_reads_back_newest_first():
    journal.record([entry("INFY")], as_of="2026-08-01")
    journal.record([entry("TCS")], as_of="2026-08-02")

    assert [e["symbol"] for e in journal.read()] == ["TCS", "INFY"]


def test_same_symbol_same_day_is_recorded_once():
    """Asking the same question twice in a morning is one piece of advice, not
    two — otherwise the journal fills with duplicates and the outcome stats lie."""
    assert journal.record([entry("INFY")], as_of="2026-08-01") == 1
    assert journal.record([entry("INFY")], as_of="2026-08-01") == 0
    assert len(journal.read()) == 1


def test_same_symbol_on_a_later_day_is_a_new_entry():
    journal.record([entry("INFY")], as_of="2026-08-01")
    journal.record([entry("INFY")], as_of="2026-08-02")
    assert len(journal.read()) == 2


def test_same_symbol_different_kind_is_a_new_entry():
    journal.record([entry("INFY", kind="buy")], as_of="2026-08-01")
    journal.record([entry("INFY", kind="topup")], as_of="2026-08-01")
    assert len(journal.read()) == 2


def test_filters_by_kind():
    journal.record([entry("INFY", kind="buy"), entry("TCS", kind="sell")], as_of="2026-08-01")
    assert [e["symbol"] for e in journal.read(kind="sell")] == ["TCS"]


def test_limit_returns_the_most_recent():
    for day in range(1, 6):
        journal.record([entry(f"S{day}")], as_of=f"2026-08-0{day}")
    assert [e["symbol"] for e in journal.read(limit=2)] == ["S5", "S4"]


def test_oldest_entries_fall_off_the_cap(monkeypatch):
    monkeypatch.setattr(journal, "MAX_ENTRIES", 3)
    for day in range(1, 6):
        journal.record([entry(f"S{day}")], as_of=f"2026-08-0{day}")

    kept = [e["symbol"] for e in journal.read()]
    assert kept == ["S5", "S4", "S3"]


def test_recording_nothing_is_a_no_op():
    assert journal.record([]) == 0
    assert journal.read() == []


def test_write_without_an_account_fails_closed():
    """A journal entry that cannot be attributed to an account must not be
    written at all — silently landing it under a reserved key would leak it to
    whoever logs in next."""
    identity.set_active_user(None)
    with pytest.raises(NoActiveUserError):
        journal.record([entry("INFY")])


def test_read_without_an_account_returns_nothing():
    journal.record([entry("INFY")], as_of="2026-08-01")
    identity.set_active_user(None)
    assert journal.read() == []


def test_one_accounts_journal_is_invisible_to_another():
    journal.record([entry("INFY")], as_of="2026-08-01")

    identity.set_active_user(USER_B)
    assert journal.read() == []

    journal.record([entry("TCS")], as_of="2026-08-01")
    assert [e["symbol"] for e in journal.read()] == ["TCS"]

    identity.set_active_user(USER_A)
    assert [e["symbol"] for e in journal.read()] == ["INFY"]


def test_journal_table_is_not_in_the_unscoped_set():
    """Explicit guard: adding it there would make one person's recommendations
    readable from every account."""
    assert "advisor_journal" not in store._UNSCOPED_TABLES
    assert "advisor_settings" not in store._UNSCOPED_TABLES


def test_clear_empties_only_the_current_account():
    journal.record([entry("INFY")], as_of="2026-08-01")
    identity.set_active_user(USER_B)
    journal.record([entry("TCS")], as_of="2026-08-01")

    journal.clear()
    assert journal.read() == []

    identity.set_active_user(USER_A)
    assert [e["symbol"] for e in journal.read()] == ["INFY"]
