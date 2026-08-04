import anyio
from fastmcp import Client

from features.mcp.server import build_server

_EXPECTED_TOOLS = {
    # The four question-shaped tools the advisor rebuild added.
    "portfolio_actions",
    "buy_ideas",
    "advice_history",
    "investor_profile",
    # Raw-data tools kept for MCP clients driving a stronger model.
    "portfolio_holdings",
    "portfolio_metrics",
    "quote",
    "kite_session_status",
    "kite_complete_login",
}


def test_all_tools_registered():
    mcp = build_server()

    async def _list():
        async with Client(mcp) as client:
            return await client.list_tools()

    names = {t.name for t in anyio.run(_list)}
    assert names >= _EXPECTED_TOOLS


def test_screen_strategy_tool_is_gone():
    """Superseded by buy_ideas, which ranks across strategies and applies the
    caller's horizon and target instead of dumping one raw strategy."""
    mcp = build_server()

    async def _list():
        async with Client(mcp) as client:
            return await client.list_tools()

    assert "screen_strategy" not in {t.name for t in anyio.run(_list)}


def test_buy_ideas_callable_end_to_end(monkeypatch):
    """Registration + call + structured return, with no live session: the auth
    guard short-circuits before anything touches Kite or the cache."""
    import features.mcp.guards as guards

    monkeypatch.setattr(guards, "is_authenticated", lambda: False)
    monkeypatch.setattr(guards.kite, "login_url", lambda: "http://login-url")

    mcp = build_server()

    async def _call():
        async with Client(mcp) as client:
            return await client.call_tool(
                "buy_ideas", {"horizon_months": 2, "target_gain_pct": 5}
            )

    result = anyio.run(_call)
    assert "auth_required" in str(result.data)


def test_advisor_tools_declare_their_parameters():
    """A model can only pass the user's horizon and target if the schema
    advertises them."""
    mcp = build_server()

    async def _list():
        async with Client(mcp) as client:
            return await client.list_tools()

    tools = {t.name: t for t in anyio.run(_list)}
    for name in ("buy_ideas", "portfolio_actions"):
        properties = tools[name].inputSchema.get("properties", {})
        assert "horizon_months" in properties
        assert "target_gain_pct" in properties
