"""Login orchestration — the one path from a request_token to a live session.

Both entry points (the REST `/callback` route and the MCP login tool) funnel
through `complete_login`, which is what makes "on account change, purge the
caches" enforceable: there is a single place where the active account can
change, so there is a single place that has to remember.
"""
from config import API_SECRET
from core.data import get_market_data
from core.identity import get_active_user
from core.kite import kite, set_access_token
from features.screener.service import screener_on_login


def complete_login(request_token: str) -> dict:
    """Single source of truth for turning a request_token into a live session.

    Shared by the REST /callback route and the MCP kite_complete_login tool:
    generate session -> purge any previous account's cached state -> set (and
    persist) token -> kick the screener refresh.

    The purge lives here rather than in core.kite because core.data.providers.kite
    imports core.kite, so core.kite importing core.data would be a cycle. This is
    also the single chokepoint both login paths pass through.
    """
    data = kite.generate_session(request_token, api_secret=API_SECRET)

    user_id = data.get("user_id")
    if not user_id:
        # Without an identity we cannot scope this account's settings, and every
        # later read would silently fall back to defaults. Fail closed.
        raise ValueError("Kite session response contained no user_id")

    if user_id != get_active_user():
        # A different account: nothing cached for the previous one may survive.
        get_market_data().clear_user_caches()

    set_access_token(data["access_token"], user_id)
    screener_on_login()
    # Deliberately no access_token in the response: no caller reads it, and
    # handing back a credential nobody needs is a standing footgun.
    return {"user_id": user_id}
