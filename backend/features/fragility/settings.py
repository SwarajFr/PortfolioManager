"""Fragility settings — currently just the correlation estimation window.

`long_window` is doing more work than its size suggests. It is simultaneously
the covariance lookback, the baseline the short window is compared against for
regime detection, and the minimum history a ticker needs to be included at all
(`service.py` drops anything shorter). Raising it therefore steadies the
estimate *and* silently excludes more recent listings — the trade-off is real,
which is why it is exposed rather than fixed.

Saves merge over `_DEFAULTS` so a partial payload cannot delete a key the engine
depends on.

`save_fragility_settings` and `reset_fragility_settings` currently have no
caller — the feature exposes only `GET /analysis`, with no settings route — so
`long_window` is in practice fixed at its default. They are kept, rather than
deleted, as the ready-made other half of that endpoint.
"""
from core.settings_store import load_settings, save_settings, reset_settings

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
