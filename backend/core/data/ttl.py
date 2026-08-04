"""A tiny in-process expiring cache.

Used for state that must stay live (holdings, quotes) but is asked for several
times while serving a single request, and for remembering which symbols were
recently fetched so an after-hours page refresh does not re-ask upstream for a
bar that does not exist yet. Deliberately not persisted — a restart should
forget all of it.
"""
from __future__ import annotations

import threading
import time
from typing import Any


class TTLCache:
    def __init__(self, ttl_seconds: float):
        self._ttl = float(ttl_seconds)
        self._entries: dict[Any, tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def get(self, key: Any) -> Any | None:
        if self._ttl <= 0:
            return None
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            expires_at, value = entry
            if expires_at < time.monotonic():
                del self._entries[key]
                return None
            return value

    def set(self, key: Any, value: Any) -> None:
        if self._ttl <= 0:
            return
        with self._lock:
            self._entries[key] = (time.monotonic() + self._ttl, value)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
