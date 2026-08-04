"""Fragility settings — currently just the minimum-history threshold.

Despite the name, `long_window` is not a lookback: the analysis always requests
`MAX_LOOKBACK_DAYS` (900) of prices and estimates the covariance off whatever
survives. What it actually sets is a *floor*, used twice in `service.py` — a
ticker needs at least this many observations to be included at all, and the
whole analysis is skipped if fewer rows than this remain after aligning.

That makes it the dial between stability and coverage. Raising it steadies the
correlation estimate and silently excludes more recently listed holdings, which
is why it is exposed rather than fixed. Excluded tickers are named in
`tickers_excluded` so the omission is visible rather than a quiet distortion.

Saves merge over `_DEFAULTS` so a partial payload cannot delete a key the engine
depends on.

`save_fragility_settings` and `reset_fragility_settings` currently have no
caller — the feature exposes only `GET /analysis`, with no settings route — so
`long_window` is in practice fixed at its default. They are kept, rather than
deleted, as the ready-made other half of that endpoint.
"""
from core.settings_store import load_settings, reset_settings, save_settings

_TABLE = "fragility_settings"
_DEFAULTS = {
    "long_window": 90,
}


def get_settings() -> dict:
    return load_settings(_TABLE, _DEFAULTS)


def save_fragility_settings(data: dict) -> None:
    save_settings(_TABLE, {**_DEFAULTS, **data})


def reset_fragility_settings() -> dict:
    return reset_settings(_TABLE, _DEFAULTS)
