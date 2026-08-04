"""Self-registering provider lookup.

Mirrors the screener's `@register` strategy registry so the codebase has one
extension idiom: a new provider is one decorated class, imported once in
`providers/__init__.py`, with no edits anywhere else.
"""
from __future__ import annotations

from .base import MarketDataProvider

REGISTRY: dict[str, type[MarketDataProvider]] = {}


def register(cls: type[MarketDataProvider]) -> type[MarketDataProvider]:
    if not cls.name:
        raise ValueError(f"{cls.__name__} must define a non-empty `name`")
    REGISTRY[cls.name] = cls
    return cls


def create_provider(name: str, **kwargs) -> MarketDataProvider:
    try:
        cls = REGISTRY[name]
    except KeyError:
        raise ValueError(
            f"Unknown data provider {name!r}. Registered: {sorted(REGISTRY)}"
        ) from None
    return cls(**kwargs)
