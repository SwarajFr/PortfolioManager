"""The contract every upstream data source implements.

A provider is the only place allowed to know a vendor's SDK, URL shapes, range
limits and error types. Everything above it works in terms of `InstrumentRef`,
`Candle`, `Quote` and the errors in `core.data.errors`.

Unimplemented methods raise `CapabilityNotSupportedError` by default, so a
partial provider (history only, fundamentals only) is a normal, safe thing to
write: declare what you support in `capabilities` and override just those.
"""
from __future__ import annotations

import datetime
from abc import ABC
from collections.abc import Sequence
from enum import StrEnum
from typing import ClassVar

from ..errors import CapabilityNotSupportedError
from ..models import Candle, Fundamentals, InstrumentRef, Quote


class Capability(StrEnum):
    HISTORY = "history"
    QUOTES = "quotes"
    INSTRUMENTS = "instruments"
    HOLDINGS = "holdings"
    FUNDAMENTALS = "fundamentals"


class MarketDataProvider(ABC):
    name: ClassVar[str] = ""
    capabilities: ClassVar[frozenset[Capability]] = frozenset()

    # ── capability handling ──────────────────────────────────────────────────
    def supports(self, capability: Capability) -> bool:
        return capability in self.capabilities

    def require(self, capability: Capability) -> None:
        if not self.supports(capability):
            raise CapabilityNotSupportedError(self.name, str(capability))

    def is_available(self) -> bool:
        """Whether a call would currently succeed (credentials present, etc.).

        The service uses this to decide between serving stale cache and
        attempting a fetch, so it must not raise.
        """
        return True

    # ── data access ──────────────────────────────────────────────────────────
    def fetch_candles(
        self,
        ref: InstrumentRef,
        start: datetime.date,
        end: datetime.date,
        interval: str = "day",
    ) -> list[Candle]:
        self.require(Capability.HISTORY)
        raise NotImplementedError

    def fetch_quotes(self, refs: Sequence[InstrumentRef]) -> dict[str, Quote]:
        self.require(Capability.QUOTES)
        raise NotImplementedError

    def fetch_instruments(self, exchange: str) -> list[InstrumentRef]:
        self.require(Capability.INSTRUMENTS)
        raise NotImplementedError

    def fetch_holdings(self) -> list[dict]:
        self.require(Capability.HOLDINGS)
        raise NotImplementedError

    def fetch_fundamentals(self, ref: InstrumentRef) -> Fundamentals:
        self.require(Capability.FUNDAMENTALS)
        raise NotImplementedError
