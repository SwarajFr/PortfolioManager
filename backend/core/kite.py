from datetime import datetime, timedelta, timezone

from kiteconnect import KiteConnect

from config import API_KEY
from core.identity import set_active_user
from core.settings_store import claim_legacy_rows, load_settings, save_settings

kite = KiteConnect(api_key=API_KEY)

_access_token = None

_IST = timezone(timedelta(hours=5, minutes=30))
_SESSION_TABLE = "kite_session"


def _today_ist() -> str:
    return datetime.now(_IST).date().isoformat()


def _persist_token(token: str, user_id: str) -> None:
    # Best-effort: a broken/missing settings.db must never break auth.
    # Only ever one token at rest — a new login overwrites the previous one.
    try:
        save_settings(
            _SESSION_TABLE,
            {"access_token": token, "user_id": user_id, "ist_date": _today_ist()},
        )
    except Exception:
        pass


def _activate(token: str, user_id: str) -> None:
    """Make `user_id` the account this process serves."""
    global _access_token
    _access_token = token
    kite.set_access_token(token)
    set_active_user(user_id)
    # Best-effort, like token persistence: a settings.db problem must not break auth.
    try:
        claim_legacy_rows(user_id)
    except Exception:
        pass


def _load_persisted_token() -> None:
    # Restore only a same-IST-day token; Kite tokens die ~06:00 IST daily, so a
    # prior-day token is dead and must be ignored, not reused.
    #
    # A row with no user_id predates account isolation. Resuming it would leave
    # the process authenticated as an account we cannot name — and therefore
    # unable to scope that account's settings. Discard it and require a login.
    try:
        data = load_settings(_SESSION_TABLE, {})
        if (
            data.get("access_token")
            and data.get("user_id")
            and data.get("ist_date") == _today_ist()
        ):
            _activate(data["access_token"], data["user_id"])
    except Exception:
        pass


def set_access_token(token: str, user_id: str):
    _activate(token, user_id)
    _persist_token(token, user_id)


def is_authenticated():
    return _access_token is not None


def get_kite():
    if not _access_token:
        raise Exception("Not authenticated")
    return kite


# Restore a same-day token on startup so a mid-day server restart isn't a re-login.
_load_persisted_token()
