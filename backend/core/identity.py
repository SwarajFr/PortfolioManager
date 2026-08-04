"""The Zerodha account whose data this process is currently serving.

Deliberately dependency-free. ``core.kite`` imports ``core.settings_store``, so
``settings_store`` cannot import ``core.kite`` back without a cycle — both
depend on this module instead. ``core.kite`` is the only writer; everything that
persists user-scoped state reads from here.

Not persisted: a restart must re-establish identity from the stored session
rather than assume the last one.
"""
from __future__ import annotations

import threading

_lock = threading.Lock()
_active_user_id: str | None = None


def set_active_user(user_id: str | None) -> None:
    global _active_user_id
    with _lock:
        _active_user_id = user_id


def get_active_user() -> str | None:
    with _lock:
        return _active_user_id
