"""Screener universe construction and refresh orchestration.

Fetching, caching and rate-limiting moved to `core.data`. What stays here is
genuinely screener-specific: which symbols are in scope, and recomputing signals
for the symbols that received a new bar.
"""
from __future__ import annotations

import datetime

import pandas as pd

from core.data import InstrumentRef, get_market_data

from . import cache, compute, settings
from .engine import build_strategies


# ── Universe ─────────────────────────────────────────────────────────────────
def load_nse500(path: str, column: str) -> set[str]:
    df = pd.read_csv(path)
    return set(df[column].astype(str).str.strip())


def _passes_liquidity_filter(symbol: str, members: set[str]) -> bool:
    """The one pluggable membership gate. Swap NSE500 for a turnover floor here
    without touching callers."""
    return symbol in members


def filter_universe(
    instruments: pd.DataFrame, segment: str, members: set[str]
) -> list[InstrumentRef]:
    if instruments.empty:
        return []
    rows = instruments[instruments["segment"] == segment]
    return [
        InstrumentRef(
            symbol=str(r.tradingsymbol),
            token=int(r.instrument_token),
            exchange=str(r.exchange),
            segment=str(r.segment),
        )
        for r in rows.itertuples()
        if _passes_liquidity_filter(str(r.tradingsymbol), members)
    ]


def build_universe() -> list[InstrumentRef]:
    conf = settings.get_settings()["universe"]
    members = load_nse500(conf["constituents_path"], conf["membership_column"])
    instruments = get_market_data().get_instruments(conf["exchange"])
    return filter_universe(instruments, conf["segment"], members)


# ── Cache reads ──────────────────────────────────────────────────────────────
def last_updated() -> str | None:
    return get_market_data().last_refreshed()


# ── Refresh ──────────────────────────────────────────────────────────────────
def _recompute_signal(symbol: str, strategies: list) -> None:
    """Recompute and store one symbol's signal row from its cached candles."""
    df = get_market_data().get_history(symbol, refresh=False)
    if df.empty:
        return
    row = compute.build_signals_row(df, strategies)
    cache.upsert_signal(
        symbol,
        df.index[-1].date().isoformat(),
        {n: v["score"] for n, v in row.items()},
        {n: v["pass"] for n, v in row.items()},
    )


def _run(
    universe: list[InstrumentRef] | None,
    today: datetime.date | None,
    seed: bool,
) -> dict:
    conf = settings.get_settings()
    cache.init()
    if universe is None:
        universe = build_universe()

    strategies = build_strategies(conf)
    report = get_market_data().refresh_history(
        universe,
        seed=seed,
        today=today,
        on_updated=lambda symbol: _recompute_signal(symbol, strategies),
    )
    return {
        ("seeded" if seed else "updated"): report.updated,
        "skipped": report.skipped,
    }


def seed_history(universe=None, today=None) -> dict:
    return _run(universe, today, seed=True)


def refresh_ohlc(universe=None, today=None) -> dict:
    return _run(universe, today, seed=False)
