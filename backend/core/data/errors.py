"""Typed failures raised by the data service.

Features catch these instead of provider-specific exceptions
(``kiteconnect.TokenException`` and friends). That indirection is what keeps
broker types from leaking past the data layer.
"""
from __future__ import annotations


class DataServiceError(Exception):
    """Base class for every failure originating in the data layer."""


class NotAuthenticatedError(DataServiceError):
    """The upstream provider needs credentials it does not currently have."""


class ProviderError(DataServiceError):
    """The upstream provider was reachable but the call failed."""


class SymbolNotFoundError(DataServiceError):
    """No instrument matches the requested symbol on the requested exchange."""

    def __init__(self, symbol: str, exchange: str = "NSE"):
        self.symbol = symbol
        self.exchange = exchange
        super().__init__(f"Unknown instrument {symbol!r} on {exchange}")


class CapabilityNotSupportedError(DataServiceError):
    """The active provider does not implement the requested capability.

    Raised rather than returning ``None`` so an unsupported call fails at the
    call site instead of turning into a downstream ``NoneType`` error.
    """

    def __init__(self, provider: str, capability: str):
        self.provider = provider
        self.capability = capability
        super().__init__(f"provider {provider!r} does not support {capability!r}")
