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
        "segment": "NSE-EQ",
        "constituents_path": "data/nse500.csv",  # relative to backend/
        "membership_column": "Symbol",
    },
    "data": {
        "cache_backend": "sqlite",
        "cache_path": "screener_cache.db",       # relative to backend/
        "seed_lookback_days": 500,
        "kite_rate_limit_rps": 3.0,
    },
}


def get_settings() -> dict:
    return load_settings(_TABLE, _DEFAULTS)


def save_screener_settings(config: dict) -> None:
    save_stored_settings(_TABLE, {**_DEFAULTS, **config})


def reset_screener_settings() -> dict:
    return reset_stored_settings(_TABLE, _DEFAULTS)
