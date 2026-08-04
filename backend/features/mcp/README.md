# MCP Server (read-only)

A FastMCP v3 server mounted into the FastAPI app at `http://localhost:8000/mcp/`
(streamable-HTTP). Read-only: no order flow. Tools import the feature services
directly, so they share the running process's Kite session and read the same
`core.data` market data service — and therefore the same warm cache — as the web
app. No HTTP self-calls, no second data path.

## Tools

Answer-shaped tools first — each one answers a whole question, so a model makes
one call instead of five and assembles nothing itself. Every candidate they
return already carries `reasons[]` with a written `text` and the numbers behind
it; the model narrates those rather than deriving its own.

| Tool | Auth | What it returns |
|------|------|-----------------|
| `portfolio_actions(horizon_months?, target_gain_pct?, limit?)` | required | Ranked `sell` + `topup` with reasons and suggested sizes |
| `buy_ideas(horizon_months?, target_gain_pct?, limit?, exclude_held?)` | required | Buy candidates with entry/target/stop/reward:risk, plus why others were excluded |
| `advice_history(limit?, kind?)` | required | Past recommendations and the move since |
| `investor_profile()` | required | Risk tolerance, defaults, avoid-list |
| `portfolio_holdings()` | required | Per-holding value/P&L + portfolio totals |
| `portfolio_metrics()` | required | Five-metric diversification suite (compact) |
| `quote(symbols)` | required | Live LTP for NSE symbols |
| `kite_session_status()` | none | authenticated / token_valid / login_url |
| `kite_complete_login(request_token)` | none | Completes the Zerodha login handshake |

Auth-required tools return `{"status": "auth_required", "login_url": ...}` when
the token is missing or expired — never an exception.

**Nothing is hardcoded.** `horizon_months` and `target_gain_pct` come from the
user's question: "5% in two months" → `horizon_months=2, target_gain_pct=5`.
Different numbers give genuinely different lists. Omit both and the user's saved
profile defaults apply — never a literal in the code.

`buy_ideas` reads only the screener cache, so it never blocks on the broker. If
that cache is unseeded it says so in `notes` instead of returning nothing.

> `screen_strategy` was removed. `buy_ideas` supersedes it: it ranks across the
> strategies that suit the horizon rather than dumping one raw strategy, and it
> filters on whether the target is actually reachable. See
> `backend/features/advisor/README.md`.

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
