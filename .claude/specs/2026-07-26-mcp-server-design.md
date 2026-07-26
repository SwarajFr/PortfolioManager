# Read-Only MCP Server over the Kite Portfolio Backend

**Date:** 2026-07-26
**Status:** Approved

## Goal

Add a new self-contained feature `mcp/` (sibling of `auth/`, `portfolio/`,
`exit/`, `fragility/`, `screener/`) that exposes the existing analytics to an AI
assistant over the Model Context Protocol. A FastMCP v3 server is mounted **into
the existing FastAPI process** via `http_app()` (streamable-HTTP transport), so
it shares the warm screener cache and the in-process Kite session. Tools import
the service layer **directly** — the same functions the REST routers call — with
no self-directed HTTP back into the API. Coarse-grained tools return
pre-formatted, pre-rounded summaries.

**Read-only for v1. No order flow of any kind** (live or paper), no intraday, no
new analytics. A read interface over existing work only.

## Decisions (confirmed with user)

- **`quote()` source:** live LTP via `kite.ltp(["NSE:SYM", …])` — real last-traded
  price for any tradable symbol, one batched call, reuses the warm Kite session.
  Not the EOD candle cache. Guarded so an expired token fails loud (see below).
- **Token persistence:** in `core/kite.py` (shared with the REST app), not
  MCP-local. `set_access_token()` persists `{access_token, ist_date}`; on import
  the token is restored **only if its stored IST date == today's IST date**
  (Kite tokens invalidate ~06:00 IST daily). A same-day server restart no longer
  forces re-auth; a stale token is ignored, never reused.
- **Module for `portfolio_metrics`:** `fragility_tools.py`, because the tool is
  backed by the fragility service. Modules mirror the *backend feature* they
  wrap, not the tool name.
- **Module for `quote`:** its own `market_tools.py` — there is no quote router to
  mirror, and it talks to the raw Kite session.
- **`screen_strategy` gains `limit: int = 20`** — "top-N" needs an adjustable N.
- **`kite_session_status()` does one cheap `kite.profile()` probe** to report
  *real* validity (`token_valid`), distinguishing "we hold a token string" from
  "the token still works."
- **MCP endpoint auth:** none. Localhost-only, read-only, single-user personal
  tool; the streamable-HTTP transport is trusted on `localhost`.

## Architecture

```
backend/features/mcp/
  __init__.py        empty (convention)
  server.py          builds FastMCP, calls each module's register(mcp),
                     exposes `mcp` and `mcp_app = mcp.http_app(path="/")`
  guards.py          @needs_kite decorator + compacting/rounding helpers
  auth_tools.py      kite_session_status(), kite_complete_login(request_token)
  portfolio_tools.py portfolio_holdings()   -> portfolio.data.get_holdings
  fragility_tools.py portfolio_metrics()    -> fragility.service.get_diversity_analysis
  screener_tools.py  screen_strategy(...)   -> screener.service.get_individual
  market_tools.py    quote(symbols)         -> core.kite.get_kite().ltp(...)
```

Each tool module exposes `register(mcp)` that attaches its `@mcp.tool` functions.
`server.py` creates the single `FastMCP` instance and calls each `register()`
explicitly — no import-for-side-effect, no circular imports. This mirrors the
per-feature convention: one bounded tool module per feature area.

## Mount into the existing process — `main.py`

The one edit outside `features/mcp/`. FastMCP v3's `http_app()` returns an ASGI
app whose **lifespan must be attached to the parent FastAPI app** (it runs the
MCP session manager). The current `main.py` builds `FastAPI()` with no lifespan.

```python
from features.mcp.server import mcp_app

app = FastAPI(lifespan=mcp_app.lifespan)   # was: FastAPI()
# ... existing CORS + include_router calls unchanged ...
app.mount("/mcp", mcp_app)                 # endpoint: http://localhost:8000/mcp/
```

`server.py` uses `mcp.http_app(path="/")`; mounted at `/mcp`, the client endpoint
is `http://localhost:8000/mcp/`. CORS is untouched — the MCP client is not
browser-CORS-bound.

## Fail-loud auth guard — `guards.py`

`@needs_kite` wraps every tool that touches Kite. It catches both the
not-authenticated case (`is_authenticated()` false / `get_kite()` raising) and
`kiteconnect.exceptions.TokenException` (token present but expired/invalid), and
**returns** a structured payload — it never lets an opaque exception surface to
the MCP client:

```json
{ "status": "auth_required",
  "login_url": "https://kite.zerodha.com/connect/login?api_key=...&v=3",
  "message": "Kite token missing or expired. Open login_url, authorize, then call kite_complete_login(request_token)." }
```

`screen_strategy` is **not** guarded — it reads the screener cache only and keeps
working with an expired token, as long as the cache is seeded.

## Tools (coarse-grained, pre-rounded, compact)

| Tool | Guard | Backed by | Returns |
|---|---|---|---|
| `portfolio_holdings()` | needs_kite | `get_holdings()` | per-holding `{symbol, qty, avg_price, ltp, value, pnl, pnl_pct}` sorted by value desc, + `totals{value, invested, pnl, pnl_pct, num_holdings}`. Drops instrument tokens and raw Kite fields. |
| `portfolio_metrics()` | needs_kite | `get_diversity_analysis()` | 5-metric suite (`diversification_ratio`, `enb`, `weight_entropy`/`effective_positions`/`normalized_entropy`, `avg_correlation`/`max_correlation`, `concentration_gap`) + `portfolio_vol`, `num_positions`, `max_correlation_pair`, top principal bet, `tickers_excluded`. **No** correlation/covariance matrix. Empty portfolio → clear insufficient-data note. |
| `screen_strategy(name, universe="NSE500", limit=20)` | none (cache) | `get_individual(name)` | `{strategy, universe, total_matches, top:[{symbol,score}][:limit], last_updated}`. Unknown `name` → error listing `REGISTRY` keys; `universe != "NSE500"` → error listing supported. Empty/unseeded cache → `total_matches: 0` + hint to log in. |
| `quote(symbols: list[str])` | needs_kite | `kite.ltp(["NSE:SYM", …])` | `{quotes:[{symbol, ltp}], not_found:[…]}`. One batched call, capped at 50 symbols. Maps input `SYM` → `NSE:SYM` and back. |
| `kite_session_status()` | none | `is_authenticated()` + cheap `kite.profile()` probe | `{authenticated, token_valid, user_id, login_url}`. Probe distinguishes a held token string from a still-working one; on `TokenException` → `token_valid: false` + login_url. |
| `kite_complete_login(request_token)` | none | extracted `auth` service fn | `complete_login()` → `generate_session` → `set_access_token` (persists) → `screener_on_login()`. Returns `{status:"authenticated", user_id}` or `{status:"error", message, login_url}`. |

## Token persistence — `core/kite.py`

- Storage via the existing `core/settings_store.py`, table `kite_session` (lands
  in `settings.db`; no new storage layer). Payload `{access_token, ist_date}`.
- `set_access_token(token)` also persists the payload with `ist_date` = today in
  IST (`UTC+05:30`).
- `_load_persisted_token()` runs on module import: load the payload; if
  `ist_date == today_ist()`, call `kite.set_access_token(...)` and set the
  module global; else ignore (stale/dead token). Failures are swallowed — a
  missing/corrupt row must not break startup.
- Extract the callback's inline session logic into an `auth` **service** function
  `complete_login(request_token) -> dict` so the REST `/callback` route and the
  `kite_complete_login` tool share exactly one path (generate_session →
  set_access_token → screener_on_login).

## Dependencies

`uv add fastmcp` (v3.2.x). No other new runtime deps. Managed via `uv` per
project convention — updates `pyproject.toml` + `uv.lock`.

## Files changed vs created

- **Created (backend):** `features/mcp/{__init__,server,guards,auth_tools,portfolio_tools,fragility_tools,screener_tools,market_tools}.py`,
  `tests/test_mcp_tools.py`.
- **Changed (minimal):**
  - `main.py` — attach `mcp_app.lifespan`, mount `/mcp` (+2 lines, +1 import).
  - `core/kite.py` — persist/restore token (in-memory behavior preserved when no
    persisted row).
  - `features/auth/` — extract `complete_login()` into a service function;
    `routes.py` `callback()` calls it. No behavior change to the REST flow.
  - `pyproject.toml` / `uv.lock` — `fastmcp` dependency.
  - CLAUDE.md — document the MCP feature.
- **No changes** to portfolio/exit/fragility/screener compute, engine, or
  frontend. The React app is untouched.

## Error / edge behavior

- No token / expired token on a guarded tool → `auth_required` payload with
  `login_url` (never raises).
- Unknown strategy / unsupported universe → structured error listing valid values.
- Empty portfolio → holdings/metrics return well-formed empty summaries.
- Unseeded screener cache → `total_matches: 0` + hint.
- `quote` unknown/invalid symbols → collected in `not_found`, valid ones still returned.

## Tests (pytest, `uv run`, existing `backend/tests/` layout, TDD)

No live Kite session required — Kite is mocked.

- `@needs_kite` returns the `login_url` payload when `get_kite()` raises the
  not-authenticated error, and when a wrapped call raises `TokenException`.
- `screen_strategy`: `total_matches == len(results)`; `top` is exactly the first
  `limit` rows; unknown strategy → error listing registry keys; unseeded cache →
  `total_matches: 0`.
- `quote`: input `["INFY","TCS"]` → `kite.ltp` called with `["NSE:INFY","NSE:TCS"]`;
  a symbol absent from the ltp response lands in `not_found`; LTPs are rounded.
- `portfolio_holdings`: totals reconcile with per-row values; rows sorted by value
  desc; no raw instrument tokens leak.
- `portfolio_metrics`: passes through the 5 scalars; the correlation matrix is
  absent from the payload.
- Token persistence: `set_access_token` writes a row; `_load_persisted_token`
  restores a same-IST-date token and ignores a prior-day one.

## Deliverable — Claude Desktop client config

The MCP endpoint is streamable-HTTP at `http://localhost:8000/mcp/`. The exact
`claude_desktop_config.json` is provided on completion — the current
Claude-Desktop-supported form (native remote URL if supported by the installed
version, else the `mcp-remote` stdio bridge), confirmed against current FastMCP /
MCP client docs at write time.

## Success criteria

- `uv run pytest` passes (backend).
- The mounted server responds on `http://localhost:8000/mcp/`; the six tools are
  discoverable and callable from an MCP client, sharing the running process's
  cache and Kite session.
- A guarded tool with no/expired token returns the `login_url` payload rather
  than throwing; `kite_complete_login(request_token)` restores the session and
  triggers the screener refresh.
- `screen_strategy` returns top-N + `total_matches`, never the full ~500-row dump;
  it issues zero Kite requests.
- A same-day server restart reuses the persisted token (no re-login required).
- The existing REST app and React frontend behave exactly as before.
