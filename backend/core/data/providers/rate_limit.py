"""Process-wide request pacing.

Previously the only throttle lived inside the screener refresh loop, so a
background refresh and a foreground analytics request each spent the full
budget independently and together blew past it. One limiter owned by the
provider means every caller draws from the same allowance.
"""
from __future__ import annotations

import threading
import time


class RateLimiter:
    """Enforces a minimum interval between calls across all threads."""

    def __init__(self, requests_per_second: float):
        self._min_interval = 1.0 / requests_per_second if requests_per_second > 0 else 0.0
        self._lock = threading.Lock()
        self._last_call = 0.0

    def acquire(self) -> None:
        if self._min_interval <= 0:
            return
        # The sleep happens under the lock on purpose: releasing early would let
        # every waiting thread wake at once and burst past the limit.
        with self._lock:
            wait = self._min_interval - (time.monotonic() - self._last_call)
            if wait > 0:
                time.sleep(wait)
            self._last_call = time.monotonic()
