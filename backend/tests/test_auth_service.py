import core.identity as identity
import features.auth.service as auth_service


def test_complete_login_sets_token_and_refreshes(monkeypatch):
    calls = {}
    monkeypatch.setattr(
        auth_service.kite, "generate_session",
        lambda rt, api_secret: {"access_token": "tok-xyz", "user_id": "AB1234"},
    )
    monkeypatch.setattr(
        auth_service, "set_access_token",
        lambda t, u: calls.update(token=t, user=u),
    )
    monkeypatch.setattr(auth_service, "screener_on_login", lambda: calls.setdefault("refresh", True))
    # Same account as the session already serves, so no cache purge is attempted
    # and the market data singleton stays out of this test.
    identity.set_active_user("AB1234")

    result = auth_service.complete_login("req-token")

    assert calls["token"] == "tok-xyz"
    assert calls["user"] == "AB1234"
    assert calls["refresh"] is True
    assert result["user_id"] == "AB1234"


def test_complete_login_rejects_a_session_without_a_user_id(monkeypatch):
    """No identity means no way to scope that account's settings — fail closed
    rather than authenticate an account we cannot name."""
    monkeypatch.setattr(
        auth_service.kite, "generate_session",
        lambda rt, api_secret: {"access_token": "tok-xyz"},
    )

    try:
        auth_service.complete_login("req-token")
    except ValueError as e:
        assert "user_id" in str(e)
    else:
        raise AssertionError("expected complete_login to reject a session with no user_id")
