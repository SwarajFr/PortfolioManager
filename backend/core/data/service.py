"""The single point that decides where a piece of market data comes from.

Features call this and nothing below it. Every "should I read the cache, hit the
provider, or write back what I just fetched?" question is answered here, once,
instead of being re-answered slightly differently inside each feature.

Two classes of data, two policies:

* **Historical candles** are cache-first. A settled daily bar never changes, so
  the store is authoritative and the provider is only asked for the parts of the
  requested window that are missing.
* **Holdings and quotes** are live broker/market state. They are never cached
  beyond a few seconds — just long enough to collapse the repeat calls made
  while serving one request.
"""
from __future__ import annotations

import datetime
import logging
from collections.abc import Callable, Iterable, Sequence

import pandas as pd

from .config import DataConfig
from .errors import DataServiceError, NotAuthenticatedError, SymbolNotFoundError
from .models import Fundamentals, InstrumentRef, Quote, RefreshReport
from .providers.base import Capability, MarketDataProvider
from .repositories import CandleRepository, InstrumentRepository, MetaRepository
from .ttl import TTLCache

logger = logging.getLogger(__name__)

_ONE_DAY = datetime.timedelta(days=1)

META_LAST_UPDATED = "last_updated"
META_SEED_COMPLETE = "seed_complete"


def _instruments_stamp_key(exchange: str) -> str:
    return f"instruments_updated_{exchange}"


class MarketDataService:
    def __init__(
        self,
        *,
        provider: MarketDataProvider,
        candles: CandleRepository,
        instruments: InstrumentRepository,
        meta: MetaRepository,
        config: DataConfig,
        today: Callable[[], datetime.date] | None = None,
    ):
        self._provider = provider
        self._candles = candles
        self._instruments = instruments
        self._meta = meta
        self._config = config
        self._today = today or datetime.date.today

        self._holdings_cache = TTLCache(config.holdings_ttl_seconds)
        self._quote_cache = TTLCache(config.quote_ttl_seconds)
        self._fill_attempts = TTLCache(config.history_fill_ttl_seconds)

    @property
    def provider(self) -> MarketDataProvider:
        return self._provider

    @property
    def config(self) -> DataConfig:
        return self._config

    # ── history ──────────────────────────────────────────────────────────────
    def get_history(
        self,
        symbol: str | InstrumentRef,
        *,
        start: datetime.date | None = None,
        end: datetime.date | None = None,
        lookback_days: int | None = None,
        interval: str = "day",
        refresh: bool = True,
    ) -> pd.DataFrame:
        """Daily OHLC for one symbol, cache-first.

        Returns a frame indexed by date with columns open/high/low/close/volume.
        Missing pieces of the window are fetched and written back; if the
        provider is unreachable, whatever is cached is returned rather than
        failing the whole request.

        Pass an `InstrumentRef` instead of a bare symbol when the caller already
        knows the token (holdings rows carry one) — that skips the instrument
        master lookup entirely.
        """
        name, ref = _coerce_ref(symbol)
        start, end = self._window(start, end, lookback_days)
        if refresh:
            self._fill_window(name, start, end, interval, ref)
        return self._candles.read(name, start, end)

    def get_history_batch(
        self,
        symbols: Iterable[str | InstrumentRef],
        *,
        start: datetime.date | None = None,
        end: datetime.date | None = None,
        lookback_days: int | None = None,
        interval: str = "day",
        refresh: bool = True,
    ) -> dict[str, pd.DataFrame]:
        """History for many symbols. Symbols that yield no data are omitted.

        A single unresolvable or failing symbol must not sink a portfolio-wide
        analysis, so failures are logged and skipped — the same tolerance the
        per-feature fetchers had before.
        """
        start, end = self._window(start, end, lookback_days)
        out: dict[str, pd.DataFrame] = {}
        for raw in symbols:
            name, _ = _coerce_ref(raw)
            if not name or name in out:
                continue
            try:
                frame = self.get_history(
                    raw, start=start, end=end, interval=interval, refresh=refresh
                )
            except DataServiceError as exc:
                logger.warning("history unavailable for %s: %s", name, exc)
                continue
            if not frame.empty:
                out[name] = frame
        return out

    def get_close_frame(
        self,
        symbols: Iterable[str | InstrumentRef],
        *,
        start: datetime.date | None = None,
        end: datetime.date | None = None,
        lookback_days: int | None = None,
        refresh: bool = True,
    ) -> pd.DataFrame:
        """Wide close-price frame: one column per symbol, union of dates."""
        history = self.get_history_batch(
            symbols,
            start=start,
            end=end,
            lookback_days=lookback_days,
            refresh=refresh,
        )
        if not history:
            return pd.DataFrame()
        return pd.DataFrame(
            {symbol: frame["close"] for symbol, frame in history.items()}
        ).sort_index()

    def refresh_history(
        self,
        refs: Iterable[InstrumentRef],
        *,
        lookback_days: int | None = None,
        seed: bool = False,
        interval: str = "day",
        on_updated: Callable[[str], None] | None = None,
        today: datetime.date | None = None,
    ) -> RefreshReport:
        """Bulk incremental fill, used by the scheduled/login-triggered refresh.

        `seed=True` pulls the full lookback for every symbol; otherwise each
        symbol resumes from the day after its newest stored bar. A symbol that
        cannot be fetched (delisted, removed from the index) is skipped and
        logged — never fatal, because one dead constituent must not abort a
        500-symbol refresh.
        """
        today = today or self._today()
        lookback = int(
            lookback_days
            if lookback_days is not None
            else self._config.default_lookback_days
        )
        report = RefreshReport()

        for ref in refs:
            symbol = _clean(ref.symbol)
            start = self._resume_from(symbol, seed, lookback, today)
            if start > today:
                continue
            try:
                candles = self._provider.fetch_candles(ref, start, today, interval)
            except Exception as exc:  # noqa: BLE001 - one bad symbol must not abort
                logger.warning("history refresh skipped %s: %s", symbol, exc)
                report.record_skip(symbol, str(exc))
                continue

            if self._candles.upsert(symbol, candles) > 0:
                report.record_update(symbol)
                if on_updated is not None:
                    on_updated(symbol)

        self._meta.set(
            META_LAST_UPDATED, datetime.datetime.now().isoformat(timespec="seconds")
        )
        if seed:
            self._meta.set(META_SEED_COMPLETE, "1")
        self._fill_attempts.clear()
        return report

    # ── live market/broker state ─────────────────────────────────────────────
    def get_quote(self, symbols: str | Sequence[str]) -> dict[str, Quote]:
        """Last traded price per symbol. Symbols with no quote are absent."""
        wanted = _unique([_clean(s) for s in _as_sequence(symbols)])
        if not wanted:
            return {}

        found: dict[str, Quote] = {}
        missing: list[str] = []
        for symbol in wanted:
            cached = self._quote_cache.get(symbol)
            if cached is None:
                missing.append(symbol)
            else:
                found[symbol] = cached

        if missing:
            refs = [self._ref_or_placeholder(s) for s in missing]
            for symbol, quote in self._provider.fetch_quotes(refs).items():
                self._quote_cache.set(symbol, quote)
                found[symbol] = quote
        return found

    def get_holdings(self) -> pd.DataFrame:
        """Current broker holdings as a DataFrame (always live)."""
        cached = self._holdings_cache.get("holdings")
        if cached is None:
            cached = pd.DataFrame(self._provider.fetch_holdings())
            self._holdings_cache.set("holdings", cached)
        return cached.copy()

    def clear_user_caches(self) -> None:
        """Drop everything that belongs to *whoever is logged in*.

        Called when the active Zerodha account changes: these caches are keyed
        by symbol (or not at all), so without this a switch inside the TTL
        window would serve the previous account's portfolio. Candles and
        instruments are identical for every user and deliberately survive.
        """
        self._holdings_cache.clear()
        self._quote_cache.clear()

    # ── reference data ───────────────────────────────────────────────────────
    def get_instruments(
        self, exchange: str = "NSE", *, refresh: bool = False
    ) -> pd.DataFrame:
        """The instrument master for an exchange, refreshed at most daily."""
        if self._instruments_stale(exchange) or refresh:
            self._reload_instruments(exchange)
        return self._instruments.read(exchange)

    def resolve(self, symbol: str, exchange: str = "NSE") -> InstrumentRef:
        """Symbol → instrument handle, pulling the master once if needed."""
        symbol = _clean(symbol)
        ref = self._instruments.resolve(symbol, exchange)
        if ref is not None:
            return ref
        if self._reload_instruments(exchange):
            ref = self._instruments.resolve(symbol, exchange)
        if ref is None:
            raise SymbolNotFoundError(symbol, exchange)
        return ref

    def get_fundamentals(self, symbol: str) -> Fundamentals:
        """Company fundamentals.

        No provider ships this yet — Kite Connect has no fundamentals endpoint —
        so this raises `CapabilityNotSupportedError` today. The method exists so
        a future provider slots in without any caller changing.
        """
        self._provider.require(Capability.FUNDAMENTALS)
        return self._provider.fetch_fundamentals(self.resolve(symbol))

    # ── introspection ────────────────────────────────────────────────────────
    def status(self) -> dict:
        return {
            "provider": self._provider.name,
            "authenticated": self._provider.is_available(),
            "capabilities": sorted(str(c) for c in self._provider.capabilities),
            "last_updated": self._meta.get(META_LAST_UPDATED),
            "seed_complete": self._meta.get(META_SEED_COMPLETE) == "1",
            "symbol_count": self._candles.symbol_count(),
        }

    def last_refreshed(self, symbol: str | None = None) -> str | None:
        if symbol is None:
            return self._meta.get(META_LAST_UPDATED)
        return self._candles.last_date(_clean(symbol))

    def cached_symbols(self) -> list[str]:
        return self._candles.symbols()

    # ── internals ────────────────────────────────────────────────────────────
    def _window(
        self,
        start: datetime.date | None,
        end: datetime.date | None,
        lookback_days: int | None = None,
    ) -> tuple[datetime.date, datetime.date]:
        """Resolve a requested window against the service's clock.

        Callers say how much history they need, not which dates that is — one
        clock, in one place, instead of every feature calling `date.today()`.
        """
        end = end or self._today()
        if start is None:
            days = (
                lookback_days
                if lookback_days is not None
                else self._config.default_lookback_days
            )
            start = end - datetime.timedelta(days=int(days))
        if start > end:
            raise ValueError(f"start {start} is after end {end}")
        return start, end

    def _fill_window(
        self,
        symbol: str,
        start: datetime.date,
        end: datetime.date,
        interval: str,
        ref: InstrumentRef | None = None,
    ) -> int:
        """Fetch only the parts of [start, end] the store is missing."""
        attempt_key = (symbol, interval, start, end)
        if self._fill_attempts.get(attempt_key) is not None:
            return 0

        first, last = self._candles.date_range(symbol)
        gaps = _missing_ranges(first, last, start, end)
        if not gaps:
            return 0

        if not self._provider.is_available():
            # Serving a short window is better than failing the page; only a
            # completely empty cache leaves us with nothing to return.
            if first is None:
                raise NotAuthenticatedError(
                    f"no cached history for {symbol} and provider is unavailable"
                )
            logger.debug("provider unavailable; serving cached history for %s", symbol)
            return 0

        if ref is None or ref.token is None:
            ref = self.resolve(symbol)
        written = 0
        for gap_start, gap_end in gaps:
            written += self._candles.upsert(
                symbol, self._provider.fetch_candles(ref, gap_start, gap_end, interval)
            )
        self._fill_attempts.set(attempt_key, True)
        return written

    def _resume_from(
        self, symbol: str, seed: bool, lookback: int, today: datetime.date
    ) -> datetime.date:
        full_window = today - datetime.timedelta(days=lookback)
        if seed:
            return full_window
        last = self._candles.last_date(symbol)
        if last is None:
            return full_window
        return datetime.date.fromisoformat(last) + _ONE_DAY

    def _instruments_stale(self, exchange: str) -> bool:
        if self._instruments.count(exchange) == 0:
            return True
        stamp = self._meta.get(_instruments_stamp_key(exchange))
        if not stamp:
            return True
        try:
            age = datetime.datetime.now() - datetime.datetime.fromisoformat(stamp)
        except ValueError:
            return True
        return age.total_seconds() > self._config.instruments_ttl_seconds

    def _reload_instruments(self, exchange: str) -> bool:
        """Pull the instrument master. Returns whether anything was written."""
        if not self._provider.is_available():
            return False
        try:
            refs = self._provider.fetch_instruments(exchange)
        except DataServiceError as exc:
            # A stale master still resolves nearly every symbol; failing here
            # would take down features that only needed a token lookup.
            logger.warning("instrument master refresh failed for %s: %s", exchange, exc)
            return False
        if not refs:
            return False
        self._instruments.replace(exchange, refs)
        self._meta.set(
            _instruments_stamp_key(exchange),
            datetime.datetime.now().isoformat(timespec="seconds"),
        )
        return True

    def _ref_or_placeholder(self, symbol: str) -> InstrumentRef:
        """Quotes are addressed by exchange:symbol, so an unresolved symbol is
        still worth asking about — the provider simply returns no entry."""
        try:
            return self.resolve(symbol)
        except DataServiceError:
            return InstrumentRef(symbol=symbol)


# ── helpers ──────────────────────────────────────────────────────────────────
def _missing_ranges(
    cached_first: str | None,
    cached_last: str | None,
    start: datetime.date,
    end: datetime.date,
) -> list[tuple[datetime.date, datetime.date]]:
    """Which sub-ranges of [start, end] are not in the store.

    Only the head (before the earliest stored bar) and the tail (after the
    latest) are considered. The store is filled by contiguous appends, so an
    interior hole cannot occur — and probing for one would mean a query per
    trading day.
    """
    if cached_first is None or cached_last is None:
        return [(start, end)]

    first = datetime.date.fromisoformat(cached_first)
    last = datetime.date.fromisoformat(cached_last)
    gaps: list[tuple[datetime.date, datetime.date]] = []
    if start < first:
        gaps.append((start, first - _ONE_DAY))
    if end > last:
        gaps.append((last + _ONE_DAY, end))
    return gaps


def _clean(symbol: str) -> str:
    return str(symbol).strip().upper()


def _coerce_ref(value: str | InstrumentRef) -> tuple[str, InstrumentRef | None]:
    """Accept either a bare symbol or a fully-formed ref; return both views."""
    if isinstance(value, InstrumentRef):
        return _clean(value.symbol), value
    return _clean(value), None


def _as_sequence(symbols: str | Sequence[str]) -> Sequence[str]:
    return [symbols] if isinstance(symbols, str) else list(symbols)


def _unique(items: Iterable[str]) -> list[str]:
    seen: dict[str, None] = {}
    for item in items:
        if item:
            seen.setdefault(item, None)
    return list(seen)


__all__ = ["MarketDataService"]
