"""Advisor configuration: the investor profile plus the model's tuning knobs.

`advisor_settings` is deliberately absent from `core.settings_store._UNSCOPED_TABLES`
— it holds one person's risk appetite, capital and exclusions, so it must stay
keyed by Zerodha `user_id` like every other portfolio table. Contrast
`agent_settings`, which is unscoped because it configures the LLM, not the money.
"""
from core.settings_store import (
    load_settings,
    reset_settings as reset_stored_settings,
    save_settings as save_stored_settings,
)

from .metrics import DEFAULT_REACHABILITY_TIERS

_TABLE = "advisor_settings"

#: The user-editable half: everything the profile drawer writes.
_PROFILE_DEFAULTS = {
    "risk_tolerance": "balanced",  # conservative | balanced | aggressive
    "default_horizon_months": 3,
    "default_target_gain_pct": 10,
    "capital_available": 0,  # 0 = unspecified; suppresses rupee sizing
    "avoid_symbols": [],
    "notes": "",
}

#: The model's knobs. Exposed so the thresholds behind a recommendation can be
#: audited and changed without a code edit — none of them are hardcoded downstream.
_TUNING_DEFAULTS = {
    "atr_stop_multiple": 2.0,
    "reachability_tiers": dict(DEFAULT_REACHABILITY_TIERS),
    # A candidate whose stop sits further away than its target is a trade that
    # risks more than it aims to make. Reachability alone does not catch these:
    # a stock can easily be volatile enough to reach the target and still be
    # likelier to hit the stop on the way.
    "min_reward_risk": 1.0,
    # Which technical strategies matter at which holding period. A two-month
    # trade rides breakouts and mean reversion; a year-long one rides momentum.
    "horizon_bands": {"short_max_months": 2, "medium_max_months": 6},
    "horizon_strategy_weights": {
        "short": {"breakout": 3, "rsi_reversion": 2, "ma_crossover": 2, "high_52w": 1, "momentum_12_1": 1},
        "medium": {"breakout": 2, "ma_crossover": 2, "momentum_12_1": 2, "high_52w": 2, "rsi_reversion": 1},
        "long": {"momentum_12_1": 3, "high_52w": 3, "ma_crossover": 2, "breakout": 1, "rsi_reversion": 1},
    },
    # How many strategies a stock must pass to qualify for the combined screen.
    "min_strategies_passed": 2,
    # Candidates pulled from the screener before per-stock metrics are computed.
    "shortlist_size": 60,
    # A holding must score at or below this on the exit engine to be a top-up,
    # and show at least this much technical strength (0-100, see ranking.py).
    "topup_max_exit_score": 30,
    "topup_min_strength": 60,
    # How much of a position to shed on a TRIM that is not over the weight cap.
    "trim_fraction": 0.33,
    # Risk-tolerance tilt applied to the buy ranking: how much reward:risk counts
    # relative to raw screener conviction.
    "risk_weights": {
        "conservative": {"conviction": 0.4, "reward_risk": 0.6},
        "balanced": {"conviction": 0.6, "reward_risk": 0.4},
        "aggressive": {"conviction": 0.8, "reward_risk": 0.2},
    },
}

DEFAULT = {"profile": _PROFILE_DEFAULTS, "tuning": _TUNING_DEFAULTS}


def _merged(stored: dict) -> dict:
    """Fill gaps from the defaults so a config saved before a knob existed still
    loads. Only the two known groups are merged; unknown keys are dropped."""
    return {
        "profile": {**_PROFILE_DEFAULTS, **(stored.get("profile") or {})},
        "tuning": {**_TUNING_DEFAULTS, **(stored.get("tuning") or {})},
    }


def get_settings() -> dict:
    return _merged(load_settings(_TABLE, DEFAULT))


def get_profile() -> dict:
    return get_settings()["profile"]


def get_tuning() -> dict:
    return get_settings()["tuning"]


def save_advisor_settings(config: dict) -> None:
    """Accepts a partial config; unspecified groups keep their current values."""
    current = get_settings()
    save_stored_settings(
        _TABLE,
        {
            "profile": {**current["profile"], **(config.get("profile") or {})},
            "tuning": {**current["tuning"], **(config.get("tuning") or {})},
        },
    )


def reset_advisor_settings() -> dict:
    return reset_stored_settings(_TABLE, DEFAULT)


def strategy_weights_for_horizon(horizon_months: float, tuning: dict) -> tuple[str, dict]:
    """Pick the strategy weighting that suits the caller's holding period."""
    bands = tuning["horizon_bands"]
    if horizon_months <= bands["short_max_months"]:
        band = "short"
    elif horizon_months <= bands["medium_max_months"]:
        band = "medium"
    else:
        band = "long"
    return band, dict(tuning["horizon_strategy_weights"][band])
