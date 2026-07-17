"""Orchestration: screen reads (cache-only), status, and the Lock-guarded
background refresh triggered on login."""
from __future__ import annotations

import threading

import pandas as pd

from . import cache, data, engine, settings

_refresh_lock = threading.Lock()


def _cache_path() -> str:
    return settings.get_settings()["data"]["cache_path"]


def _read_signal_frames(path: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = cache.read_signals(path)
    scores = {r["symbol"]: r["scores"] for r in rows}
    passes = {r["symbol"]: r["passes"] for r in rows}
    scores_df = pd.DataFrame.from_dict(scores, orient="index")
    passes_df = pd.DataFrame.from_dict(passes, orient="index")
    return scores_df, passes_df


def get_strategies() -> dict:
    return {"strategies": engine.strategy_metadata(settings.get_settings())}


def get_individual(strategy: str) -> dict:
    scores, passes = _read_signal_frames(_cache_path())
    if scores.empty or strategy not in scores.columns:
        return {"strategy": strategy, "results": [], "last_updated": data.last_updated()}
    results = engine.run_individual(strategy, scores, passes)
    return {"strategy": strategy, "results": results, "last_updated": data.last_updated()}


def run_scan(strategies=None, weights=None, k=None, fallback_n=None) -> dict:
    conf = settings.get_settings()["screener"]
    selected = strategies or list(engine.REGISTRY)
    weights = weights or conf["weights"]
    k = conf["default_k"] if k is None else k
    fallback_n = conf["fallback_n"] if fallback_n is None else int(fallback_n)

    scores, passes = _read_signal_frames(_cache_path())
    if scores.empty:
        return {"results": [], "is_fallback": False, "selected": selected,
                "k": k, "last_updated": data.last_updated()}
    out = engine.run_combined(selected, weights, k, fallback_n, scores, passes)
    out["last_updated"] = data.last_updated()
    return out


def get_status() -> dict:
    path = _cache_path()
    return {
        "last_updated": cache.get_meta(path, "last_updated"),
        "seed_complete": cache.get_meta(path, "seed_complete") == "1",
        "symbol_count": cache.symbol_count(path),
        "refreshing": _refresh_lock.locked(),
    }


def _refresh_core() -> None:
    path = _cache_path()
    cache.init(path)
    if cache.get_meta(path, "seed_complete") == "1":
        data.refresh_ohlc()
    else:
        data.seed_history()


def _locked_refresh() -> None:
    try:
        _refresh_core()
    finally:
        _refresh_lock.release()


def screener_on_login() -> None:
    """Non-blocking. Skip if a refresh is already running (stacked logins)."""
    if not _refresh_lock.acquire(blocking=False):
        return
    threading.Thread(target=_locked_refresh, daemon=True).start()


def trigger_refresh() -> dict:
    screener_on_login()
    return get_status()
