from core.settings_store import load_settings, save_settings, reset_settings

_TABLE = "fragility_settings"
_DEFAULTS = {
    "long_window": 90,
}


def get_settings() -> dict:
    return load_settings(_TABLE, _DEFAULTS)


def save_fragility_settings(data: dict) -> dict:
    return save_settings(_TABLE, {**_DEFAULTS, **data})


def reset_fragility_settings() -> dict:
    return reset_settings(_TABLE, _DEFAULTS)
