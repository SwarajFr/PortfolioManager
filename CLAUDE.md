# CLAUDE.md

Guidance for Claude Code when working in this repository.

## What This Project Is

A full-stack portfolio analytics dashboard for Zerodha Kite Connect brokerage data. Three feature areas:

- **Portfolio Overview** — allocation table, concentration metrics, sector exposure
- **Exit Signals** — rule-based scoring (0–100) across 5 KPIs, maps to HOLD/WATCH/TRIM/EXIT per holding
- **Fragility & Diversification** — MRC-based ENB, effective weight (hidden concentration), urgency scores, correlation regime detection, stress-test VaR, what-if trim simulator

## Dev Commands

### Backend (Python / FastAPI)

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux

pip install -r requirements.txt
uvicorn main:app --reload       # http://localhost:8000
```

Required `backend/.env`:
```
KITE_API_KEY=...
KITE_API_SECRET=...
REDIRECT_URL=...
FRONTEND_URL=...
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

`main.py` mounts four routers at `/api/{auth,portfolio,exit,fragility}`. CORS locked to `http://localhost:5173`.

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

### Frontend

`App.jsx` checks auth on mount; renders `LoginPage` or the shell. `activeView` string drives lazy-loaded page switching (`overview` / `exit` / `fragility`).

Services in `src/services/` call `apiClient.js` (axios instance → `http://localhost:8000`). `apiClient` is a **named export** `{ apiClient }`, not a default export.

**Design system** — dark "risk operations cockpit" theme defined as CSS custom properties in `src/styles/globals.css`. Semantic aliases: `--profit`, `--loss`, `--warning`, `--accent`. All styling is Tailwind v4 with inline CSS var references. Tone mappings live in `src/constants/theme.js`.

**`useAsyncData(loader, options?)`** — options is an object `{ errorMessage }`, not a deps array. Returns `{ data, loading, error, refresh }`.

## Key Constraints

- Kite access token is in-memory only — server restart requires re-auth via `/api/auth/login`.
- Fragility engine silently drops tickers with insufficient price history; `tickers_excluded[]` in the response lists what was dropped.
- `settings.db` is created relative to the directory where uvicorn is launched (`backend/`).
- No TypeScript — plain JSX with React 19 and the React Compiler enabled.

## Agent Files

Plans, specs, and other AI working documents live under `.claude/`:

```
.claude/
  specs/      — approved design specs
  plans/      — implementation plans
```
