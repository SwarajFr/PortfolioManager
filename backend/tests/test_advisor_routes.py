"""The REST surface — the path that lets the recommendations be inspected and
regression-tested with no LLM anywhere in the loop."""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

import core.identity as identity
import core.settings_store as store
import features.advisor.routes as routes
from core.data import NotAuthenticatedError


@pytest.fixture()
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(store, "DB_PATH", str(tmp_path / "settings.db"))
    identity.set_active_user("AB1234")
    app = FastAPI()
    app.include_router(routes.router, prefix="/api/advisor")
    yield TestClient(app)
    identity.set_active_user(None)


def test_ideas_passes_query_params_through(client, monkeypatch):
    seen = {}
    monkeypatch.setattr(
        routes, "buy_ideas",
        lambda h, t, limit, held: seen.update(h=h, t=t, limit=limit, held=held) or {"ideas": []},
    )

    response = client.get("/api/advisor/ideas?horizon_months=2&target_gain_pct=5&limit=3")

    assert response.status_code == 200
    assert seen == {"h": 2.0, "t": 5.0, "limit": 3, "held": True}


def test_ideas_omits_params_it_was_not_given(client, monkeypatch):
    seen = {}
    monkeypatch.setattr(
        routes, "buy_ideas",
        lambda h, t, limit, held: seen.update(h=h, t=t) or {"ideas": []},
    )

    client.get("/api/advisor/ideas")
    assert seen == {"h": None, "t": None}


def test_non_positive_params_are_rejected(client):
    assert client.get("/api/advisor/ideas?target_gain_pct=0").status_code == 422
    assert client.get("/api/advisor/ideas?horizon_months=-1").status_code == 422


def test_cold_session_is_a_401_not_a_500(client, monkeypatch):
    """A missing Kite token is a login problem; reporting it as a server fault
    leaves the user with nothing to act on."""
    def _boom(*args, **kwargs):
        raise NotAuthenticatedError("no token")

    monkeypatch.setattr(routes, "portfolio_actions", _boom)

    response = client.get("/api/advisor/actions")
    assert response.status_code == 401
    assert "Log in" in response.json()["detail"]


def test_profile_round_trips(client):
    saved = client.put(
        "/api/advisor/profile",
        json={"profile": {"risk_tolerance": "conservative", "avoid_symbols": ["IDEA"]}},
    )
    assert saved.status_code == 200

    profile = client.get("/api/advisor/profile").json()["config"]["profile"]
    assert profile["risk_tolerance"] == "conservative"
    assert profile["avoid_symbols"] == ["IDEA"]
    # Untouched keys keep their defaults rather than vanishing.
    assert profile["default_horizon_months"] == 3


def test_profile_reset_restores_defaults(client):
    client.put("/api/advisor/profile", json={"profile": {"risk_tolerance": "aggressive"}})
    reset = client.post("/api/advisor/profile/reset").json()["config"]
    assert reset["profile"]["risk_tolerance"] == "balanced"


def test_journal_is_empty_before_anything_is_recommended(client):
    assert client.get("/api/advisor/journal").json()["entries"] == []
