"""MCP tools: report Kite session status and complete the login handshake."""
from __future__ import annotations

from kiteconnect.exceptions import TokenException

from core.kite import get_kite, is_authenticated, kite
from features.auth.service import complete_login


def kite_session_status() -> dict:
    """Report whether the Kite session is live.

    `authenticated` reflects whether a token is held; `token_valid` is confirmed
    by a lightweight profile probe (so an expired token reads as invalid, not
    merely present). Always returns a login_url to guide re-auth.
    """
    if not is_authenticated():
        return {"authenticated": False, "token_valid": False, "user_id": None, "login_url": kite.login_url()}
    try:
        profile = get_kite().profile()
        return {
            "authenticated": True,
            "token_valid": True,
            "user_id": profile.get("user_id"),
            "login_url": kite.login_url(),
        }
    except TokenException:
        return {"authenticated": True, "token_valid": False, "user_id": None, "login_url": kite.login_url()}


def kite_complete_login(request_token: str) -> dict:
    """Exchange a Zerodha request_token for a live session.

    Obtain request_token by opening the login_url (from kite_session_status),
    authorizing, and copying it from the redirect URL. On success the screener
    refresh is kicked off automatically.
    """
    try:
        result = complete_login(request_token)
        return {"status": "authenticated", "user_id": result.get("user_id")}
    except Exception as e:  # noqa: BLE001 - any login failure is reported to the caller with a retry URL
        # Keep the real failure reason; still hand back a login_url to retry.
        return {"status": "error", "message": str(e), "login_url": kite.login_url()}


def register(mcp) -> None:
    mcp.tool(kite_session_status)
    mcp.tool(kite_complete_login)
