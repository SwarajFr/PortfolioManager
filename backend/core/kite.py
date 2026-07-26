from datetime import datetime, timedelta, timezone

from kiteconnect import KiteConnect

from config import API_KEY
from core.settings_store import load_settings, save_settings

kite = KiteConnect(api_key=API_KEY)

_access_token = None

_IST = timezone(timedelta(hours=5, minutes=30))
_SESSION_TABLE = "kite_session"


def _today_ist() -> str:
    return datetime.now(_IST).date().isoformat()


def _persist_token(token: str) -> None:
    # Best-effort: a broken/missing settings.db must never break auth.
    try:
        save_settings(_SESSION_TABLE, {"access_token": token, "ist_date": _today_ist()})
    except Exception:
        pass


def _load_persisted_token() -> None:
    # Restore only a same-IST-day token; Kite tokens die ~06:00 IST daily, so a
    # prior-day token is dead and must be ignored, not reused.
    global _access_token
    try:
        data = load_settings(_SESSION_TABLE, {})
        if data.get("access_token") and data.get("ist_date") == _today_ist():
            _access_token = data["access_token"]
            kite.set_access_token(_access_token)
    except Exception:
        pass


def set_access_token(token: str):
    global _access_token
    _access_token = token
    kite.set_access_token(token)
    _persist_token(token)


def is_authenticated():
    return _access_token is not None


def get_kite():
    if not _access_token:
        raise Exception("Not authenticated")
    return kite


# Restore a same-day token on startup so a mid-day server restart isn't a re-login.
_load_persisted_token()
