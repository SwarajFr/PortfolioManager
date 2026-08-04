"""Portfolio settings: user-defined groups, target bands and concentration caps.

Groups and targets are two halves of one structure that the UI edits separately,
so they drift: renaming a group leaves its old target behind, and adding one
leaves it with no target at all. `_normalize_settings` is the reconciliation
step that runs on every write — it gives new groups a neutral `[0, 0]` band and
drops targets whose group is gone, so `compute.py` can trust that a target
lookup either matches a live group or is absent.

Note the table name is the bare `"settings"` for historical reasons: this was
the first feature, written before the per-feature naming convention existed.
Renaming it would orphan every existing user's saved config.
"""
from core.settings_store import (
    load_settings,
    reset_settings as reset_stored_settings,
    save_settings as save_stored_settings,
)

DEFAULT = {
    "groups": {
        "Metals": [],
        "US Equity": [],
        "Indian Equity ETF": [],
        "Indian Equity": [],
    },
    "targets": {
        "Metals": [15, 18],
        "US Equity": [15, 18],
        "Indian Equity ETF": [20, 24],
        "Indian Equity": [40, 50],
    },
    "concentration": {
        "top5": 35,
        "single": 5,
    },
}


def get_settings():
    return load_settings("settings", DEFAULT)


def _normalize_settings(config: dict):
    for group in config.get("groups", {}):
        if group not in config.get("targets", {}):
            config["targets"][group] = [0, 0]

    stale_targets = [group for group in config.get("targets", {}) if group not in config.get("groups", {})]
    for group in stale_targets:
        del config["targets"][group]

    return config


def save_settings(config: dict):
    save_stored_settings("settings", config, normalizer=_normalize_settings)


def reset_settings():
    return reset_stored_settings("settings", DEFAULT)
