from core.kite import kite, set_access_token
from config import API_SECRET
from features.screener.service import screener_on_login


def complete_login(request_token: str) -> dict:
    """Single source of truth for turning a request_token into a live session.

    Shared by the REST /callback route and the MCP kite_complete_login tool:
    generate session -> set (and persist) token -> kick the screener refresh.
    """
    data = kite.generate_session(request_token, api_secret=API_SECRET)
    set_access_token(data["access_token"])
    screener_on_login()
    return {"user_id": data.get("user_id"), "access_token": data["access_token"]}
