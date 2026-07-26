import features.auth.service as auth_service


def test_complete_login_sets_token_and_refreshes(monkeypatch):
    calls = {}
    monkeypatch.setattr(
        auth_service.kite, "generate_session",
        lambda rt, api_secret: {"access_token": "tok-xyz", "user_id": "AB1234"},
    )
    monkeypatch.setattr(auth_service, "set_access_token", lambda t: calls.setdefault("token", t))
    monkeypatch.setattr(auth_service, "screener_on_login", lambda: calls.setdefault("refresh", True))

    result = auth_service.complete_login("req-token")

    assert calls["token"] == "tok-xyz"
    assert calls["refresh"] is True
    assert result["user_id"] == "AB1234"
    assert result["access_token"] == "tok-xyz"
