"""Orchestration: screen reads (cache-only), status, and the Lock-guarded
background refresh triggered on login."""
from __future__ import annotations

import logging
import threading

import pandas as pd

from core.data import get_market_data

from . import cache, data, engine, settings

logger = logging.getLogger(__name__)

_refresh_lock = threading.Lock()


def _read_signal_frames() -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = cache.read_signals()
    scores = {r["symbol"]: r["scores"] for r in rows}
    passes = {r["symbol"]: r["passes"] for r in rows}
    scores_df = pd.DataFrame.from_dict(scores, orient="index")
    passes_df = pd.DataFrame.from_dict(passes, orient="index")
    return scores_df, passes_df


def get_strategies() -> dict:
    return {"strategies": engine.strategy_metadata(settings.get_settings())}


def get_individual(strategy: str) -> dict:
    scores, passes = _read_signal_frames()
    if scores.empty or strategy not in scores.columns:
        return {"strategy": strategy, "results": [], "last_updated": data.last_updated()}
    results = engine.run_individual(strategy, scores, passes)
    return {"strategy": strategy, "results": results, "last_updated": data.last_updated()}


def run_scan(strategies=None, weights=None, k=None, fallback_n=None) -> dict:
    conf = settings.get_settings()["screener"]
    selected = strategies or list(engine.REGISTRY)
    # Unknown/misspelled strategy names are a client error (surfaced as 400 by
    # the route), not a 500.
    unknown = [s for s in selected if s not in engine.REGISTRY]
    if unknown:
        raise ValueError(f"Unknown strategies: {unknown}")
    weights = weights or conf["weights"]
    k = conf["default_k"] if k is None else k
    fallback_n = conf["fallback_n"] if fallback_n is None else int(fallback_n)

    scores, passes = _read_signal_frames()
    # Keep only strategies actually present in the cache; a registered strategy
    # not yet seeded is dropped rather than causing a KeyError in run_combined.
    available = [] if scores.empty else [s for s in selected if s in scores.columns]
    if not available:
        return {"results": [], "is_fallback": False, "selected": [],
                "k": k, "last_updated": data.last_updated()}
    out = engine.run_combined(available, weights, k, fallback_n, scores, passes)
    out["last_updated"] = data.last_updated()
    return out


def get_status() -> dict:
    status = get_market_data().status()
    return {
        "last_updated": status["last_updated"],
        "seed_complete": status["seed_complete"],
        "symbol_count": status["symbol_count"],
        "refreshing": _refresh_lock.locked(),
    }


def _refresh_core() -> None:
    cache.init()
    if get_market_data().status()["seed_complete"]:
        data.refresh_ohlc()
    else:
        data.seed_history()


def _locked_refresh() -> None:
    try:
        _refresh_core()
    except Exception:
        # Runs in a background thread — a raw traceback would just print to
        # stderr while /refresh already returned 200. Log it instead.
        logger.exception("screener background refresh failed")
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
