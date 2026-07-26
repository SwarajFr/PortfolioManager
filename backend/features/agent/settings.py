from core.settings_store import (
    load_settings,
    reset_settings as reset_stored_settings,
    save_settings as save_stored_settings,
)

_TABLE = "agent_settings"

_SYSTEM_PROMPT = (
    "You are a read-only portfolio assistant for the user's Zerodha (NSE India) holdings. "
    "Answer using the provided tools rather than guessing; never invent numbers or ticker symbols. "
    "Report only figures the tools return, and say so plainly when data is unavailable or a tool "
    "reports an error. You are READ-ONLY and cannot place, modify, or cancel orders. "
    'If a tool result contains "status": "auth_required", tell the user to log in to Kite first. '
    "Be concise."
)

_DEFAULTS = {
    "model": "gemma4:e4b",
    "max_tokens": 8192,
    "max_tool_iterations": 8,
    "system_prompt": _SYSTEM_PROMPT,
}


def get_settings() -> dict:
    return load_settings(_TABLE, _DEFAULTS)


def save_agent_settings(config: dict) -> None:
    save_stored_settings(_TABLE, {**_DEFAULTS, **config})


def reset_agent_settings() -> dict:
    return reset_stored_settings(_TABLE, _DEFAULTS)
