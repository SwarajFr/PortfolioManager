from kiteconnect.exceptions import TokenException

import features.mcp.guards as guards


def _fake_login_url(monkeypatch):
    monkeypatch.setattr(guards.kite, "login_url", lambda: "http://login-url")


def test_needs_kite_passes_through_when_authenticated(monkeypatch):
    _fake_login_url(monkeypatch)
    monkeypatch.setattr(guards, "is_authenticated", lambda: True)

    @guards.needs_kite
    def tool():
        return {"ok": True}

    assert tool() == {"ok": True}


def test_needs_kite_blocks_when_unauthenticated(monkeypatch):
    _fake_login_url(monkeypatch)
    monkeypatch.setattr(guards, "is_authenticated", lambda: False)

    @guards.needs_kite
    def tool():
        raise AssertionError("must not run")

    out = tool()
    assert out["status"] == "auth_required"
    assert out["login_url"] == "http://login-url"


def test_needs_kite_catches_token_exception(monkeypatch):
    _fake_login_url(monkeypatch)
    monkeypatch.setattr(guards, "is_authenticated", lambda: True)

    @guards.needs_kite
    def tool():
        raise TokenException("Token is invalid or has expired.")

    out = tool()
    assert out["status"] == "auth_required"
    assert "login_url" in out
