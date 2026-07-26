import anyio
from fastmcp import Client

from features.mcp.server import build_server

_EXPECTED_TOOLS = {
    "portfolio_holdings",
    "portfolio_metrics",
    "screen_strategy",
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


def test_screen_strategy_callable_end_to_end():
    # Unknown-strategy path returns before touching the cache or Kite, so this
    # exercises registration + call + structured return with no live session.
    mcp = build_server()

    async def _call():
        async with Client(mcp) as client:
            return await client.call_tool("screen_strategy", {"name": "bogus"})

    result = anyio.run(_call)
    assert "bogus" in str(result.data)
    assert "valid_strategies" in str(result.data)
