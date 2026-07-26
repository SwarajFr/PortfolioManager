# CLAUDE.md

Guidance for Claude Code when working in this repository.

## What This Project Is

A full-stack portfolio analytics dashboard for Zerodha Kite Connect brokerage data. Six feature areas:

- **Portfolio Overview** — allocation table, concentration metrics, sector exposure
- **Exit Signals** — rule-based scoring (0–100) across 5 KPIs, maps to HOLD/WATCH/TRIM/EXIT per holding
- **Fragility & Diversification** — MRC-based ENB, effective weight (hidden concentration), urgency scores, correlation regime detection, stress-test VaR, what-if trim simulator
- **Screener** — NSE500 multi-strategy technical screener (5 strategies) over a three-layer OHLC cache; single-strategy raw ranking + weighted K-of-N combined screen with fallback
- **MCP Server** — read-only Model Context Protocol server (`features/mcp/`) mounted into the FastAPI app at `/mcp`, exposing holdings, the diversification suite, the screener, live quotes, and Kite session tools to an AI assistant
- **Agent** — in-app chat tab (`features/agent/`) where a local LLM (Ollama / Gemma 4, provider-agnostic via the OpenAI-compatible API) answers portfolio questions by calling the read-only MCP tools; no order flow

## Dev Commands

### Backend (Python / FastAPI)

Dependencies are managed with **uv**. There is no `requirements.txt` and no venv to activate —
`uv run` syncs the environment before every command.

```bash
cd backend
uv sync                         # create .venv + install from uv.lock
uv run uvicorn main:app --reload    # http://localhost:8000

uv add <pkg>                    # add a dep (updates pyproject.toml + uv.lock)
uv remove <pkg>
uv run python -c "..."          # any command inside the project env
```

Always run backend commands from `backend/` (the `settings.db` path depends on it) and always
prefix them with `uv run` — never `pip install` or a bare `python`/`uvicorn`.

Required `backend/.env`:
```
KITE_API_KEY=...
KITE_API_SECRET=...
REDIRECT_URL=...
FRONTEND_URL=...

# Optional — local LLM for the Agent tab (defaults shown; any OpenAI-compatible endpoint)
LLM_BASE_URL=http://localhost:11434/v1
LLM_API_KEY=ollama
```

### Frontend (React / Vite)

```bash
cd frontend
npm install
npm run dev       # http://localhost:5173
npm run build
npm run lint
```

## Architecture

### Backend

`main.py` mounts six routers at `/api/{auth,portfolio,exit,fragility,screener,agent}` (plus the MCP app at `/mcp`). CORS locked to `http://localhost:5173`.

Each feature is layered identically:
- `data.py` — fetches from Kite via `core/kite.py`
- `service.py` — orchestrates data → compute/engine
- `routes.py` — FastAPI router calling the service
- `settings.py` — reads/writes per-feature config via `core/settings_store.py`

**`core/kite.py`** — singleton `KiteConnect` instance, in-memory `_access_token`. Token is lost on server restart.

**`core/settings_store.py`** — persists settings to `settings.db` (SQLite, one table per feature, single row `id=1`).

**Exit signals** (`features/exit/`) — scores 5 KPIs per holding (loss severity, risk vs. median, risk-adjusted inefficiency, trend weakness, concentration), sums to 0–100, thresholds to HOLD/WATCH/TRIM/EXIT. Weights and thresholds are user-configurable.

**Fragility engine** (`features/fragility/engine.py`) — `FragilityEngine.run(prices, weights)`:
1. Log returns, filter tickers with `< long_window` days of history
2. LedoitWolf covariance → MRC-based ENB (`1/sum(mrc²)`), regime delta (short vs. long rolling mean off-diagonal correlation → LOW/RISING/CRISIS)
3. Effective weight `ew = w + (corr − I) @ w` — amplifies hidden concentration
4. MRC trim targets, stress loss (99% VaR, off-diagonal corr forced to 0.85)
5. Urgency score per holding (MONITOR/WATCH/ACT) from ENB falling + regime + MRC outlier + hidden concentration signals

ENB history is persisted in SQLite (`fragility_enb_history` table) and returned in the response for the sparkline.

**Screener** (`features/screener/`) — adds a `cache.py` layer beyond the standard `data/service/routes/settings` files. All config lives in `settings.py` (module-constant idiom; strategy params, universe, cache paths, rate limit). Layout:
- `compute.py` — pure per-stock strategy functions (MA crossover, momentum 12-1, breakout, RSI reversion, 52w-high; each yields a `score` + boolean `pass`) plus cross-stock `percentile_normalize` / `aggregate` / `k_of_n_match` / `rank_and_fallback`.
- `engine.py` — `Strategy` ABC + self-registering classes + `REGISTRY`; `run_individual` (Page 1, raw-score rank) and `run_combined` (Page 2, normalize → weighted aggregate → K-of-N → rank + fallback). New strategy = one `@register` class, no other edits.
- `cache.py` — SQLite store (`screener_cache.db`): `candles` (append-only, PK `(symbol,date)`), `signals` (one latest row per symbol), `meta` (`last_updated`, `seed_complete`).
- `data.py` — `build_universe()` (Kite instruments → `NSE-EQ` → NSE500 members from a static CSV, behind one pluggable `_passes_liquidity_filter`); three-layer cache: `seed_history()` once, `refresh_ohlc()` incremental (fetch only candles after each symbol's stored max date, **skip-and-log** missing symbols), recompute+store signals only for symbols that got a new candle.

**Login-triggered refresh** — `auth/routes.py` `callback()` calls `screener_on_login()` after `set_access_token()`. It runs a Lock-guarded background thread (seed on first login, else incremental), non-blocking so the UI stays usable on cached data. `POST /api/screener/refresh` is the manual trigger. **Screens read ONLY the cache — scan/individual endpoints never call Kite.** The callback's session logic lives in `auth/service.py` `complete_login()`, shared with the MCP `kite_complete_login` tool.

**MCP server** (`features/mcp/`) — a read-only FastMCP v3 server mounted into the same FastAPI process via `mcp.http_app()` (`main.py` attaches `mcp_app.lifespan` and mounts at `/mcp`). One tool module per feature area (`portfolio_tools`, `fragility_tools`, `screener_tools`, `market_tools`, `auth_tools`); each exposes `register(mcp)` that attaches plain functions via `mcp.tool(fn)`. Tools import the service layer directly — no HTTP self-calls. Kite-touching tools use the `@needs_kite` guard (`guards.py`), which returns a `login_url` payload on a missing/expired token instead of raising. Screener tools are cache-only and ungated. Six tools: `portfolio_holdings`, `portfolio_metrics`, `screen_strategy`, `quote`, `kite_session_status`, `kite_complete_login`. See `features/mcp/README.md` for the Claude Desktop client config.

**Agent** (`features/agent/`) — a read-only in-app chat agent. `service.run_chat(history)` runs a manual OpenAI-format tool loop (`openai` SDK) against a provider-agnostic endpoint (`config.LLM_BASE_URL`/`LLM_API_KEY`, default local Ollama at `:11434/v1`; `model` from `agent_settings`, default `gemma4:e4b`). `tools.py` exposes the four read-only MCP tool functions as OpenAI function tools and dispatches calls to them (a tool failure returns `{"error": …}`, never crashes the loop). `routes.py` mounts `POST /api/agent/chat`. Requires a local model — see `features/agent/README.md`.

### Frontend

`App.jsx` checks auth on mount; renders `LoginPage` or the shell. `activeView` string drives lazy-loaded page switching (`overview` / `exit` / `fragility` / `screener` / `agent`). The Screener view has two internal tabs (Strategies / Screener) and a "last updated" indicator from `/api/screener/status`.

Services in `src/services/` call `apiClient.js` (axios instance → `http://localhost:8000`). `apiClient` is a **named export** `{ apiClient }`, not a default export.

**Design system** — dark "risk operations cockpit" theme defined as CSS custom properties in `src/styles/globals.css`. Semantic aliases: `--profit`, `--loss`, `--warning`, `--accent`. All styling is Tailwind v4 with inline CSS var references. Tone mappings live in `src/constants/theme.js`.

**`useAsyncData(loader, options?)`** — options is an object `{ errorMessage }`, not a deps array. Returns `{ data, loading, error, refresh }`.

## Key Constraints

- Kite access token is persisted (table `kite_session` in `settings.db`) and restored on startup only if generated the same IST day; tokens still expire ~06:00 IST daily, requiring re-auth via `/api/auth/login` or the `kite_complete_login` MCP tool.
- Fragility engine silently drops tickers with insufficient price history; `tickers_excluded[]` in the response lists what was dropped.
- `settings.db` is created relative to the directory where uvicorn is launched (`backend/`). The screener's `screener_cache.db` is separate and created the same way.
- The NSE500 universe file (`backend/data/nse500.csv`, path is a setting) is a **static, manual, ~quarterly** drop-in (NSE official constituents CSV with a `Symbol` column) — never fetched or scheduled. The screener refresh skip-and-logs any symbol it can't fetch (delisted/removed) rather than crashing.
- Frontend lint (`eslint-plugin-react-hooks` v7 flat-recommended) enforces `react-hooks/set-state-in-effect` as an error — no synchronous `setState` in a `useEffect`; load via `useAsyncData` and derive during render.
- No TypeScript — plain JSX with React 19 and the React Compiler enabled.

## Agent Files

Plans, specs, and other AI working documents live under `.claude/`:

```
.claude/
  specs/      — approved design specs
  plans/      — implementation plans
```
