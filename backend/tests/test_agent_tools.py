import features.agent.tools as agent_tools


def test_schemas_cover_all_handlers():
    names = {s["function"]["name"] for s in agent_tools.SCHEMAS}
    assert names == set(agent_tools._HANDLERS)


def test_dispatch_routes_and_parses_args(monkeypatch):
    seen = {}
    monkeypatch.setitem(
        agent_tools._HANDLERS, "screen_strategy",
        lambda **kw: (seen.update(kw), {"ok": True})[1],
    )
    out = agent_tools.dispatch("screen_strategy", '{"name": "breakout", "limit": 5}')
    assert out == {"ok": True}
    assert seen == {"name": "breakout", "limit": 5}


def test_dispatch_unknown_tool():
    assert "error" in agent_tools.dispatch("nope", "{}")


def test_dispatch_bad_json():
    assert "error" in agent_tools.dispatch("quote", "{not json")


def test_dispatch_handler_exception(monkeypatch):
    def boom(**kw):
        raise ValueError("kaboom")

    monkeypatch.setitem(agent_tools._HANDLERS, "quote", boom)
    out = agent_tools.dispatch("quote", '{"symbols": ["X"]}')
    assert "error" in out and "kaboom" in out["error"]
