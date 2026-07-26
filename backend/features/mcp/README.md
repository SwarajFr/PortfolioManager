# MCP Server (read-only)

A FastMCP v3 server mounted into the FastAPI app at `http://localhost:8000/mcp/`
(streamable-HTTP). Read-only: no order flow. Tools import the service layer
directly and share the running process's warm screener cache and Kite session.

## Tools

| Tool | Auth | What it returns |
|------|------|-----------------|
| `portfolio_holdings()` | required | Per-holding value/P&L + portfolio totals |
| `portfolio_metrics()` | required | Five-metric diversification suite (compact) |
| `screen_strategy(name, universe="NSE500", limit=20)` | none (cache) | Top-N passers + total_matches |
| `quote(symbols)` | required | Live LTP for NSE symbols |
| `kite_session_status()` | none | authenticated / token_valid / login_url |
| `kite_complete_login(request_token)` | none | Completes the Zerodha login handshake |

Auth-required tools return `{"status": "auth_required", "login_url": ...}` when
the token is missing or expired — never an exception.

Valid `screen_strategy` names: `ma_crossover`, `momentum_12_1`, `breakout`,
`rsi_reversion`, `high_52w`.

## Connect Claude Desktop

The backend must be running (`uv run python -m uvicorn main:app --reload` from
`backend/`) and you must have completed a Kite login (via the web app, or the
`kite_session_status` → `kite_complete_login` tool flow).

> On Windows with Smart App Control / WDAC enabled, launch uvicorn as a module
> (`python -m uvicorn …`) rather than the `uvicorn` shim — the unsigned
> `.venv\Scripts\uvicorn.exe` launcher is blocked (os error 4551), but going
> through the signed `python.exe` is not. The same applies to other console
> tools: prefer `uv run python -m pytest` over `uv run pytest` if the shim is
> blocked.

Edit Claude Desktop's config file:
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "kite-portfolio": {
      "command": "uvx",
      "args": ["fastmcp-remote", "http://localhost:8000/mcp/"]
    }
  }
}
```

`uvx` ships with `uv` (already installed). The `fastmcp-remote` bridge turns the
streamable-HTTP endpoint into the stdio transport Claude Desktop expects. Restart
Claude Desktop after editing the config. (Alternative bridge if you prefer npm:
`"command": "npx", "args": ["-y", "mcp-remote", "http://localhost:8000/mcp/"]`.)
