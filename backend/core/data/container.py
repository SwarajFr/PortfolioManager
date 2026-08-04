"""Composition root: the one place that wires a provider, the repositories and
the config into a `MarketDataService`.

Built lazily on first use so importing a feature module never touches SQLite or
the settings store, and swappable via `set_market_data` so tests can run the
real service against a stub provider and a temp database.
"""
from __future__ import annotations

import threading

from .config import DataConfig, load_config
from .providers import create_provider
from .repositories import CandleRepository, InstrumentRepository, MetaRepository
from .service import MarketDataService

_service: MarketDataService | None = None
_lock = threading.Lock()


def build_service(config: DataConfig | None = None) -> MarketDataService:
    """Assemble a service from configuration. Does not touch the singleton."""
    config = config or load_config()
    return MarketDataService(
        provider=create_provider(config.provider, rate_limit_rps=config.rate_limit_rps),
        candles=CandleRepository(config.db_path),
        instruments=InstrumentRepository(config.db_path),
        meta=MetaRepository(config.db_path),
        config=config,
    )


def get_market_data() -> MarketDataService:
    """The shared service. Every feature goes through this."""
    global _service
    if _service is None:
        with _lock:
            if _service is None:
                _service = build_service()
    return _service


def set_market_data(service: MarketDataService | None) -> None:
    """Install a service (or `None` to rebuild on next use). Test seam."""
    global _service
    with _lock:
        _service = service
