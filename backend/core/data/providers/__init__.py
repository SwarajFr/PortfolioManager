"""Upstream data sources.

Importing a provider module is what registers it. Add a new source by writing
`myprovider.py` with an `@register` class and importing it here.
"""
from . import kite  # noqa: F401  -- import for @register side effect
from .base import Capability, MarketDataProvider
from .registry import REGISTRY, create_provider, register

__all__ = [
    "REGISTRY",
    "Capability",
    "MarketDataProvider",
    "create_provider",
    "register",
]
