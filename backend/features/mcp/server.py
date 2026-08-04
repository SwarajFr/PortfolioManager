"""Builds the read-only FastMCP server and its ASGI app for mounting.

Tools import the service layer directly (no HTTP self-calls). Each feature
module exposes register(mcp); this module is the only one that imports fastmcp.
"""
from __future__ import annotations

from fastmcp import FastMCP

from . import advisor_tools, auth_tools, fragility_tools, market_tools, portfolio_tools

#: Advisor first: those four answer whole questions, and listing them ahead of
#: the raw-data tools nudges a model towards one call instead of five.
_MODULES = (advisor_tools, auth_tools, portfolio_tools, fragility_tools, market_tools)


def build_server() -> FastMCP:
    mcp = FastMCP("Kite Portfolio (read-only)")
    for module in _MODULES:
        module.register(mcp)
    return mcp


mcp = build_server()
mcp_app = mcp.http_app(path="/")
