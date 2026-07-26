from fastapi import FastAPI
from starlette.testclient import TestClient

import features.agent.routes as routes


def _app():
    app = FastAPI()
    app.include_router(routes.router, prefix="/api/agent")
    return app


def test_requires_messages():
    client = TestClient(_app())
    assert client.post("/api/agent/chat", json={}).status_code == 400


def test_happy_path(monkeypatch):
    monkeypatch.setattr(routes, "run_chat", lambda msgs: {"reply": "ok", "tool_calls": []})
    client = TestClient(_app())
    r = client.post("/api/agent/chat", json={"messages": [{"role": "user", "content": "hi"}]})
    assert r.status_code == 200 and r.json()["reply"] == "ok"
