"""The recommendation journal: what the advisor said, when, and at what price.

Stored as a capped list inside a user-scoped `advisor_journal` settings row.
Going through `core.settings_store` rather than a fresh SQLite table is
deliberate — account isolation, schema migration and fail-closed writes are
properties of that module, and re-implementing `user_id` scoping by hand is
exactly how a portfolio leaks into the wrong account.

Entries are written by the service, never by the LLM: a small local model cannot
be relied on to call a "record this" tool, and an advisor that only remembers
what it felt like remembering is not accountable.
"""
from __future__ import annotations

import datetime
import threading

from core.settings_store import load_settings, save_settings

_TABLE = "advisor_journal"
_DEFAULT: dict = {"entries": []}

#: Enough to answer "what did you tell me over the last few months" without the
#: row growing without bound. Oldest entries fall off the front.
MAX_ENTRIES = 200

#: The store is read-modify-write, and the screener's background refresh thread
#: means this process is genuinely multi-threaded.
_lock = threading.Lock()


def _today() -> str:
    return datetime.date.today().isoformat()


def _key(entry: dict) -> tuple:
    """One entry per symbol per kind per day — repeated questions on the same
    day are the same call, not new advice."""
    return (entry.get("date"), entry.get("kind"), entry.get("symbol"))


def read(limit: int | None = None, kind: str | None = None) -> list[dict]:
    """Journal entries, newest first."""
    entries = load_settings(_TABLE, _DEFAULT).get("entries", [])
    if kind:
        entries = [e for e in entries if e.get("kind") == kind]
    entries = list(reversed(entries))
    return entries[:limit] if limit else entries


def record(entries: list[dict], as_of: str | None = None) -> int:
    """Append new entries, skipping same-day duplicates. Returns how many stuck.

    Raises `NoActiveUserError` (from the settings store) when no account is
    logged in — a journal that cannot be attributed to an account must not be
    written at all.
    """
    if not entries:
        return 0

    stamp = as_of or _today()
    with _lock:
        stored = load_settings(_TABLE, _DEFAULT).get("entries", [])
        seen = {_key(e) for e in stored}

        added = []
        for entry in entries:
            candidate = {"date": stamp, **entry}
            if _key(candidate) in seen:
                continue
            seen.add(_key(candidate))
            added.append(candidate)

        if not added:
            return 0

        save_settings(_TABLE, {"entries": (stored + added)[-MAX_ENTRIES:]})
        return len(added)


def clear() -> None:
    """Wipe the journal for the logged-in account."""
    with _lock:
        save_settings(_TABLE, {"entries": []})
