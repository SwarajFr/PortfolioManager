"""Data-layer configuration, persisted through the shared settings store.

Defaults deliberately match the values the screener used before the data layer
was extracted (``screener_cache.db``, 500-day seed, 3 rps) so an existing cache
file keeps working with no migration.
"""
from __future__ import annotations

from dataclasses import dataclass, fields

from core.settings_store import load_settings, save_settings

_TABLE = "market_data_settings"


@dataclass(frozen=True, slots=True)
class DataConfig:
    #: Registered provider name; see core.data.providers.registry.
    provider: str = "kite"
    #: SQLite file holding candles, instruments and refresh metadata.
    db_path: str = "screener_cache.db"
    #: Window used when a caller does not pass an explicit start date.
    default_lookback_days: int = 500
    #: Upstream request budget, enforced process-wide by the provider.
    rate_limit_rps: float = 3.0
    #: How long a "we already tried to fill this symbol" note survives, so an
    #: after-hours page refresh does not re-ask upstream for a bar that does
    #: not exist yet.
    history_fill_ttl_seconds: float = 900.0
    #: Live broker/market state — memoised only long enough to collapse the
    #: repeated calls made while serving a single request.
    holdings_ttl_seconds: float = 15.0
    quote_ttl_seconds: float = 5.0
    #: Instrument master is stable within a trading day.
    instruments_ttl_seconds: float = 86_400.0


def load_config() -> DataConfig:
    stored = load_settings(_TABLE, {})
    known = {f.name for f in fields(DataConfig)}
    return DataConfig(**{k: v for k, v in stored.items() if k in known})


def save_config(config: dict) -> None:
    known = {f.name for f in fields(DataConfig)}
    save_settings(_TABLE, {k: v for k, v in config.items() if k in known})
