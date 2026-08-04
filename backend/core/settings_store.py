from __future__ import annotations

import copy
import json
import sqlite3
from collections.abc import Callable
from typing import Any

from core.identity import get_active_user

DB_PATH = "settings.db"

#: Tables that are NOT keyed by account. This set is a security boundary: every
#: table absent from it is scoped to the logged-in Zerodha account and can never
#: be read across accounts. Kept in one place so the property is auditable.
#:
#: - market_data_settings: infrastructure (provider, db path, rate limit).
#: - screener_settings: global for *correctness*, not convenience — strategy
#:   params feed the shared `signals` table, so per-account weights would make
#:   that table wrong for one of them.
#: - agent_settings: configures the LLM, not the portfolio.
#: - kite_session: holds the one live token; it is what we read to *learn* who
#:   the user is, so it cannot itself be user-scoped.
_UNSCOPED_TABLES = frozenset(
    {"market_data_settings", "screener_settings", "agent_settings", "kite_session"}
)

_GLOBAL_KEY = "__global__"
#: Rows written before account isolation existed. Owned by nobody until the
#: first account to authenticate claims them (see `claim_legacy_rows`).
_LEGACY_KEY = "__legacy__"


class NoActiveUserError(RuntimeError):
    """Refused to write user-scoped settings while no account is logged in."""


def _connect() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)


def _ensure_table(conn: sqlite3.Connection, table_name: str) -> None:
    conn.execute(
        f"CREATE TABLE IF NOT EXISTS {table_name} (user_id TEXT PRIMARY KEY, config TEXT)"
    )
    _migrate_schema(conn, table_name)


def _migrate_schema(conn: sqlite3.Connection, table_name: str) -> None:
    """Rewrite a pre-isolation table, which was keyed `(id INTEGER PRIMARY KEY)`
    with a single row `id=1`, into the account-keyed layout."""
    columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table_name})")}
    if "user_id" in columns:
        return

    row = conn.execute(f"SELECT config FROM {table_name} WHERE id=1").fetchone()
    conn.execute(f"DROP TABLE {table_name}")
    conn.execute(f"CREATE TABLE {table_name} (user_id TEXT PRIMARY KEY, config TEXT)")
    if row:
        # Unscoped tables were never user data, so they convert directly. User
        # tables wait for an owner rather than leak to whoever logs in mid-flight.
        key = _GLOBAL_KEY if table_name in _UNSCOPED_TABLES else _LEGACY_KEY
        conn.execute(
            f"INSERT INTO {table_name} (user_id, config) VALUES (?, ?)", (key, row[0])
        )


def _key_for(table_name: str) -> str | None:
    """The row key for this table, or None when a user is required but absent."""
    if table_name in _UNSCOPED_TABLES:
        return _GLOBAL_KEY
    return get_active_user()


def load_settings(table_name: str, defaults: dict[str, Any]) -> dict[str, Any]:
    key = _key_for(table_name)
    if key is None:
        # No account logged in: hand back defaults rather than fall through to
        # some other account's row.
        return copy.deepcopy(defaults)

    with _connect() as conn:
        _ensure_table(conn, table_name)
        row = conn.execute(
            f"SELECT config FROM {table_name} WHERE user_id=?", (key,)
        ).fetchone()

    return json.loads(row[0]) if row else copy.deepcopy(defaults)


def save_settings(
    table_name: str,
    config: dict[str, Any],
    normalizer: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
) -> None:
    key = _key_for(table_name)
    if key is None:
        raise NoActiveUserError(
            f"cannot write {table_name!r} with no account logged in"
        )

    payload = normalizer(copy.deepcopy(config)) if normalizer else copy.deepcopy(config)

    with _connect() as conn:
        _ensure_table(conn, table_name)
        conn.execute(
            f"INSERT INTO {table_name} (user_id, config) VALUES (?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET config = excluded.config",
            (key, json.dumps(payload)),
        )


def reset_settings(table_name: str, defaults: dict[str, Any]) -> dict[str, Any]:
    key = _key_for(table_name)
    if key is None:
        return copy.deepcopy(defaults)

    with _connect() as conn:
        _ensure_table(conn, table_name)
        conn.execute(f"DELETE FROM {table_name} WHERE user_id=?", (key,))

    return copy.deepcopy(defaults)


def claim_legacy_rows(user_id: str) -> None:
    """Hand pre-isolation rows to the first account that authenticates.

    Assumes the settings written before isolation existed belong to that
    account — true for a single-account install, which is the only way the old
    code could be used. Runs once: the legacy rows are gone afterwards.
    """
    with _connect() as conn:
        tables = [
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        ]
        for table in tables:
            if table in _UNSCOPED_TABLES:
                continue
            columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
            if "user_id" not in columns:
                continue
            # OR IGNORE: if this account already has a row, its own settings win
            # and the orphan is simply dropped below.
            conn.execute(
                f"UPDATE OR IGNORE {table} SET user_id=? WHERE user_id=?",
                (user_id, _LEGACY_KEY),
            )
            conn.execute(f"DELETE FROM {table} WHERE user_id=?", (_LEGACY_KEY,))
