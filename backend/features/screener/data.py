"""Data layer: Kite instruments → NSE500 universe, and the three-layer OHLC
cache orchestration (seed once, incremental append per refresh). Decoupled from
screening: screens never call anything here."""
from __future__ import annotations

import datetime
import logging
import time

import pandas as pd

from core.kite import get_kite

from . import cache, compute, settings
from .engine import build_strategies

logger = logging.getLogger(__name__)


# ── Universe ─────────────────────────────────────────────────────────────────
def load_nse500(path: str, column: str) -> set[str]:
    df = pd.read_csv(path)
    return set(df[column].astype(str).str.strip())


def _passes_liquidity_filter(symbol: str, members: set[str]) -> bool:
    """The one pluggable membership gate. Swap NSE500 for a turnover floor here
    without touching callers."""
    return symbol in members


def filter_universe(
    instruments: list[dict], segment: str, members: set[str]
) -> pd.DataFrame:
    rows = [
        {"tradingsymbol": i["tradingsymbol"], "instrument_token": i["instrument_token"]}
        for i in instruments
        if i.get("segment") == segment
        and _passes_liquidity_filter(i["tradingsymbol"], members)
    ]
    return pd.DataFrame(rows, columns=["tradingsymbol", "instrument_token"])


def build_universe() -> pd.DataFrame:
    conf = settings.get_settings()["universe"]
    members = load_nse500(conf["constituents_path"], conf["membership_column"])
    instruments = get_kite().instruments()
    return filter_universe(instruments, conf["segment"], members)


# ── Cache reads ──────────────────────────────────────────────────────────────
def _cache_path() -> str:
    return settings.get_settings()["data"]["cache_path"]


def read_ohlc(symbol: str) -> pd.DataFrame:
    df = cache.read_candles(_cache_path(), symbol)
    if not df.empty:
        df = df.set_index(pd.to_datetime(df["date"]))
    return df


def last_updated() -> str | None:
    return cache.get_meta(_cache_path(), "last_updated")


# ── Fetch + refresh ──────────────────────────────────────────────────────────
def _default_fetch(token: int, from_date, to_date) -> list[dict]:
    return get_kite().historical_data(token, from_date, to_date, "day")


def _normalize_rows(records: list[dict]) -> list[dict]:
    out = []
    for r in records:
        d = r["date"]
        d = d.date() if isinstance(d, datetime.datetime) else d
        out.append({
            "date": d.isoformat() if hasattr(d, "isoformat") else str(d),
            "open": r["open"], "high": r["high"], "low": r["low"],
            "close": r["close"], "volume": r.get("volume", 0),
        })
    return out


def _recompute_signal(path: str, symbol: str, strategies: list) -> None:
    df = cache.read_candles(path, symbol)
    if df.empty:
        return
    row = compute.build_signals_row(df, strategies)
    scores = {n: v["score"] for n, v in row.items()}
    passes = {n: v["pass"] for n, v in row.items()}
    cache.upsert_signal(path, symbol, str(df["date"].iloc[-1]), scores, passes)


def _run(universe_df, fetch, today, seed: bool) -> dict:
    conf = settings.get_settings()
    path = conf["data"]["cache_path"]
    cache.init(path)
    rps = conf["data"]["kite_rate_limit_rps"]
    lookback = conf["data"]["seed_lookback_days"]
    delay = (1.0 / rps) if (rps and fetch is None) else 0.0

    if universe_df is None:
        universe_df = build_universe()
    if fetch is None:
        fetch = _default_fetch
    if today is None:
        today = datetime.date.today()

    strategies = build_strategies(conf)
    updated = 0
    skipped = 0

    for _, r in universe_df.iterrows():
        symbol = str(r["tradingsymbol"])
        token = int(r["instrument_token"])
        if seed:
            from_date = today - datetime.timedelta(days=lookback)
        else:
            last = cache.last_candle_date(path, symbol)
            if last is None:
                from_date = today - datetime.timedelta(days=lookback)
            else:
                from_date = datetime.date.fromisoformat(last) + datetime.timedelta(days=1)
        if from_date > today:
            continue
        try:
            records = fetch(token, from_date, today)
        except Exception as exc:  # delisted/removed → skip-and-log, never crash
            logger.warning("screener refresh skipped %s: %s", symbol, exc)
            skipped += 1
            continue
        new = cache.upsert_candles(path, symbol, _normalize_rows(records))
        if new > 0:
            _recompute_signal(path, symbol, strategies)
            updated += 1
        if delay:
            time.sleep(delay)

    cache.set_meta(path, "last_updated", datetime.datetime.now().isoformat(timespec="seconds"))
    if seed:
        cache.set_meta(path, "seed_complete", "1")
    key = "seeded" if seed else "updated"
    return {key: updated, "skipped": skipped}


def seed_history(universe_df=None, fetch=None, today=None) -> dict:
    return _run(universe_df, fetch, today, seed=True)


def refresh_ohlc(universe_df=None, fetch=None, today=None) -> dict:
    return _run(universe_df, fetch, today, seed=False)
