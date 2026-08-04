"""Screener configuration: strategy parameters, screen defaults, and universe.

Three groups with different owners. `strategies` holds the per-strategy
parameters the compute functions read; `screener` holds the combining rules
(how many strategies must agree, their relative weights, how scores are made
comparable); `universe` decides which symbols are in scope at all.

This table is one of the `_UNSCOPED_TABLES` — global rather than per-account —
and that is a correctness requirement, not a shortcut. Strategy parameters feed
the shared `signals` table, which stores one row per symbol; if two accounts
could set different parameters, whichever refreshed last would leave the other
reading signals computed under settings they never chose.

Note `default_k` is intentionally a union type: the string `"all"` means a
strict AND across every selected strategy, while an int means K-of-N. Storing
"all" rather than a number keeps the strict screen correct when the user later
adds or removes a strategy.
"""
from core.settings_store import (
    load_settings,
    reset_settings as reset_stored_settings,
    save_settings as save_stored_settings,
)

_TABLE = "screener_settings"

_DEFAULTS = {
    "strategies": {
        "ma_crossover": {"fast": 20, "slow": 50},
        "momentum_12_1": {"lookback": 252, "skip": 21},
        "breakout": {"n_high": 20},
        "rsi_reversion": {"rsi_period": 14, "oversold": 30},
        "high_52w": {"window": 252, "proximity": 0.90},
    },
    "screener": {
        "default_k": "all",       # "all" (strict AND) or an int
        "weights": {},            # empty -> equal 1/N at runtime
        "fallback_n": 10,
        "normalization": "percentile",
    },
    "universe": {
        "exchange": "NSE",  # which instrument master the data service pulls
        "segment": "NSE",   # segment value for NSE cash equity (instrument_type "EQ")
        "constituents_path": "data/nse500.csv",  # relative to backend/
        "membership_column": "Symbol",
    },
    # Cache location, seed depth and the upstream rate limit are no longer
    # screener settings: they belong to the shared data layer (core.data.config)
    # now that every feature reads through it.
}


def get_settings() -> dict:
    return load_settings(_TABLE, _DEFAULTS)


def save_screener_settings(config: dict) -> None:
    save_stored_settings(_TABLE, {**_DEFAULTS, **config})


def reset_screener_settings() -> dict:
    return reset_stored_settings(_TABLE, _DEFAULTS)
