"""Kite OAuth endpoints: status, login redirect, and the provider callback.

The callback redirects to the frontend rather than returning JSON because Kite
navigates the *browser* here — this is a page load, not an XHR, so the only
useful response is somewhere for the user to land.

All session work is delegated to `service.complete_login`; this module stays
transport-only so the MCP login tool can reuse the same logic without going
through HTTP.
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse

from core.identity import get_active_user
from core.kite import kite, is_authenticated
from config import FRONTEND_URL
from .service import complete_login

router = APIRouter()


@router.get("/status")
def status():
    # user_id lets the UI name the live account, which is the visible proof that
    # account scoping is in effect.
    return {"authenticated": is_authenticated(), "user_id": get_active_user()}


@router.get("/login")
def login():
    return RedirectResponse(kite.login_url())


@router.get("/callback")
def callback(request_token: str):
    try:
        complete_login(request_token)
        return RedirectResponse(f"{FRONTEND_URL}/")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
