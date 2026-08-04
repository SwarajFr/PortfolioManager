"""Shared MCP tool helpers: the fail-loud Kite auth guard and its payloads."""
from __future__ import annotations

import functools

from kiteconnect.exceptions import TokenException

from core.data import NotAuthenticatedError
from core.kite import is_authenticated, kite


def login_payload() -> dict:
    return {
        "login_url": kite.login_url(),
        "message": (
            "Kite token missing or expired. Open login_url, authorize, then call "
            "kite_complete_login(request_token) with the request_token from the redirect."
        ),
    }


def auth_required() -> dict:
    return {"status": "auth_required", **login_payload()}


def needs_kite(fn):
    """Wrap a tool that touches Kite so a missing/expired token returns a
    login-URL payload instead of raising an opaque exception to the client."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        if not is_authenticated():
            return auth_required()
        try:
            return fn(*args, **kwargs)
        except (TokenException, NotAuthenticatedError):
            # A token that expires mid-call surfaces either as the raw Kite
            # exception or as the data layer's translation of it.
            return auth_required()

    return wrapper
