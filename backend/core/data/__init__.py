"""Market data service — the single entry point for all market data.

Features import `get_market_data()` and ask for what they need; they never see
Kite, SQLite, or any other source:

    from core.data import get_market_data

    md = get_market_data()
    md.get_history("INFY")          # cache-first daily OHLC
    md.get_quote(["INFY", "TCS"])   # live LTP
    md.get_holdings()               # live broker holdings
    md.get_instruments("NSE")       # instrument master, refreshed daily
    md.get_fundamentals("INFY")     # CapabilityNotSupportedError until a
                                    # provider implements it

Layering: features → MarketDataService → {repositories (SQLite), providers
(Kite today)}. Adding a source means writing one provider class; changing
storage means touching one repository.
"""
from .config import DataConfig, load_config
from .container import build_service, get_market_data, set_market_data
from .errors import (
    CapabilityNotSupportedError,
    DataServiceError,
    NotAuthenticatedError,
    ProviderError,
    SymbolNotFoundError,
)
from .models import (
    CANDLE_COLUMNS,
    Candle,
    Fundamentals,
    InstrumentRef,
    Quote,
    RefreshReport,
    empty_history,
)
from .providers import Capability, MarketDataProvider
from .service import MarketDataService

__all__ = [
    "CANDLE_COLUMNS",
    "Candle",
    "Capability",
    "CapabilityNotSupportedError",
    "DataConfig",
    "DataServiceError",
    "Fundamentals",
    "InstrumentRef",
    "MarketDataProvider",
    "MarketDataService",
    "NotAuthenticatedError",
    "ProviderError",
    "Quote",
    "RefreshReport",
    "SymbolNotFoundError",
    "build_service",
    "empty_history",
    "get_market_data",
    "load_config",
    "set_market_data",
]
