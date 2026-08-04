# portfolio-optimizer

## Intro
portfolio-optimizer is a full-stack portfolio analytics system for analyzing live brokerage holdings, measuring concentration risk, generating rule-based exit and fragility insights, and screening the NSE500 universe with multi-strategy technical signals — all from Zerodha Kite Connect data.

It uses the finance formulas and methods we actually built into the project:

- `portfolio value = last_price * quantity`
- `invested capital = average_price * quantity`
- `P&L = current value - invested capital`
- `return % = P&L / invested capital * 100`
- `portfolio weight % = holding value / total portfolio value * 100`
- `Herfindahl Index (HHI) = sum(weight_i^2)` for concentration and diversification analysis
- `volatility-threshold exit logic` for rule-based position monitoring
- `Ledoit-Wolf shrinkage covariance` for more stable correlation and fragility analysis

This project helps turn raw brokerage data into a structured decision-making workflow for portfolio review, concentration control, diversification analysis, and exit planning.

You can also query it in plain English — through an in-app **Agent** tab powered by a local, free LLM (Ollama / Gemma 4), or from an external assistant like Claude Desktop via a read-only **MCP server**. Both are read-only; neither can place orders.

## Screener Strategies

The Screener runs five technical strategies over the NSE500 universe. Each strategy produces two
things per stock from its daily OHLC history:

- a continuous **`score`** — used to rank stocks, and
- a boolean **`pass`** — a hard gate used by the combined screen.

Strategy parameters below are the defaults and are user-configurable.

| Strategy | What it measures | `score` | `pass` when | Defaults |
|---|---|---|---|---|
| **MA Crossover** | Trend via fast vs. slow moving average | `(SMA_fast − SMA_slow) / SMA_slow` | `SMA_fast > SMA_slow` | fast = 20, slow = 50 |
| **Momentum 12‑1** | Classic 12-month-minus-1-month return | `close₋₂₁ / close₋₂₅₂ − 1` | score > 0 | lookback = 252, skip = 21 |
| **Breakout** | Close relative to the prior N-day high | `close / prior_N_high` | `close > prior_N_high` | n_high = 20 |
| **RSI Reversion** | Contrarian — oversold reads as strong | `100 − RSI` (Wilder) | `RSI < oversold` | period = 14, oversold = 30 |
| **52-Week High** | Proximity to the 1-year high | `close / 252d_high` | `close ≥ proximity × 252d_high` | window = 252, proximity = 0.90 |

> **Breakout uses the _prior_ window high** (excluding today's own bar), which is what makes a new
> high an actual breakout. **RSI Reversion is deliberately contrarian**: it ranks weakness as
> strength, so oversold names float to the top.

### Two ways to screen

**1. Individual (raw-score ranking).** Pick one strategy. Stocks that `pass` that strategy are
listed, sorted by its raw `score` descending. A simple single-signal leaderboard.

**2. Combined (weighted K-of-N).** Pick several strategies and screen them together:

1. **Normalize** — each strategy's scores become a cross-sectional percentile rank in `[0, 1]`, so
   differently-scaled signals are comparable.
2. **Aggregate** — a weighted mean of the normalized scores, `Σ(wₛ · normₛ) / Σwₛ` (equal weight if
   none supplied).
3. **K-of-N gate** — a stock qualifies only if it `pass`es at least **K** of the **N** selected
   strategies. `K = "all"` is a strict AND.
4. **Rank + fallback** — qualifying stocks are ranked by their aggregate score. If _nothing_
   qualifies, the top-N by aggregate are shown instead and the result is flagged as a fallback.

### When it re-screens

Signals are precomputed into an on-disk cache during a **data refresh** — which runs on login and
via `POST /api/screener/refresh` — and only for symbols that received a new daily candle. The
screening endpoints then rank over that cache on **every request** and never call Kite directly, so
changing strategies, weights, or K re-screens instantly against cached data.

## Architecture

Every feature reads market data through one **data service**. Nothing else in the app talks to the
broker:

```
Portfolio  ·  Exit Signals  ·  Fragility  ·  Screener  ·  MCP tools  ·  Agent
                                  │
                            Data Service
                                  │
                      ┌───────────┴───────────┐
                  Local cache            Kite Connect
                   (SQLite)             (or any provider)
```

The service is the only place that decides where a value comes from. **Historical candles are
cache-first** — a settled daily bar never changes, so it fetches only the part of a requested window
that is missing and appends it to the store. **Holdings and live quotes always come from the broker**,
since they are current account and market state.

Underneath it are two swappable halves: *providers* (one class per upstream — Kite today; each
declares which capabilities it supports and owns all vendor quirks, chunking and rate limiting) and
*repositories* (SQLite persistence). Adding a data source is one new provider class; no feature
changes.

## Tech Stack

- Backend: FastAPI, Python (python 3.12 recommended ), Pandas, NumPy, SciPy, scikit-learn
- Frontend: React, Vite, Axios
- AI layer: FastMCP (read-only MCP server) · OpenAI SDK → local Ollama / Gemma 4 for the in-app Agent (provider-agnostic — any OpenAI-compatible endpoint)
- Broker integration: Zerodha Kite Connect API

## How to Run

### Backend with Docker (easiest)

Needs only Docker Desktop — no Python or uv on the host. Create `backend/.env` first (see the
variables in the next section), then from the repo root:

```bash
docker compose up --build      # backend at http://localhost:8000
```

The source directory is bind-mounted, so edits hot-reload and both SQLite files
(`settings.db`, `screener_cache.db`) stay on the host — your cached candles survive rebuilds
and are shared with native runs.

```bash
docker compose run --rm backend pytest -q     # tests
docker compose logs -f backend                # follow logs
docker compose down                           # stop
```

Two notes:
- The **frontend still runs on the host** (`npm run dev`). Only the backend is containerized.
- The Agent tab reaches **Ollama on your host** via `host.docker.internal` — compose sets
  `LLM_BASE_URL` for this, so no `.env` change is needed. Keep Ollama running as usual.

### Backend natively

Dependencies are managed with [uv](https://docs.astral.sh/uv/). Install it once:

##### Windows
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```
##### Linux / macOS
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

1. Go to the backend directory:
   ```bash
   cd backend
   ```

2. Install dependencies. This creates `.venv` and installs the exact versions from
   `uv.lock`, downloading Python 3.12 automatically if you don't have it:
   ```bash
   uv sync
   ```

3. Configure environment variables in `.env`:
   ```env
   KITE_API_KEY=your_api_key
   KITE_API_SECRET=your_api_secret
   REDIRECT_URL=your_redirect_url
   FRONTEND_URL=http://localhost:5173

   # Optional — local LLM for the Agent tab (defaults shown; any OpenAI-compatible endpoint)
   LLM_BASE_URL=http://localhost:11434/v1
   LLM_API_KEY=ollama
   ```

4. Start the backend server (`http://localhost:8000`):
   ```bash
   uv run uvicorn main:app --reload
   ```
   > On Windows with **Smart App Control / WDAC** enabled, the unsigned `uvicorn.exe` shim is
   > blocked (os error 4551). Launch it as a module instead — same result:
   > `uv run python -m uvicorn main:app --reload`

`uv run` re-syncs the environment before each command, so there is no virtual environment
to activate. To add or remove a dependency, use `uv add <package>` / `uv remove <package>` —
both update `pyproject.toml` and `uv.lock`, which are committed to the repo.

### Frontend

1. Go to the frontend directory:
   ```bash
   cd frontend
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Start the frontend:
   ```bash
   npm run dev
   ```

### Using the app

Open `http://localhost:5173`, click **Login** (redirects through Zerodha and back), and the
dashboard loads with five views — **Overview · Exit Signals · Fragility · Screener · Agent**. The
screener seeds its price cache in the background on first login, so its results fill in shortly
after.

## Ask about your portfolio in plain English

Two independent, **read-only** AI interfaces sit on top of the same analytics — use either or both.
Neither can place, modify, or cancel orders.

### Agent tab (in-app, local & free)

A chat tab that answers portfolio questions by calling the analytics as tools. It runs a **local**
model via [Ollama](https://ollama.com) — no API key, no per-message cost, and your data never leaves
your machine.

1. Install Ollama, then pull the default model:
   ```bash
   ollama pull gemma4:e4b     # 9.6 GB; laptop/CPU-friendly
   ```
2. Make sure Ollama is running — `ollama list` should show the model. The Agent tab talks to it at
   `http://localhost:11434/v1` by default.
3. Open the **Agent** tab and ask, e.g. *"What are my holdings?"*, *"How diversified am I?"*, or
   *"Run the momentum screen."*

To use a larger local model or a cloud endpoint instead, set `LLM_BASE_URL` / `LLM_API_KEY` in
`backend/.env` and the model in settings — no code change. More detail:
[`backend/features/agent/README.md`](backend/features/agent/README.md).

### MCP server (external assistants like Claude Desktop)

The backend also exposes the same read-only tools as a **Model Context Protocol** server at
`http://localhost:8000/mcp/`, so an external assistant such as Claude Desktop can drive them —
powered by your existing assistant, no extra API key. Add this to Claude Desktop's
`claude_desktop_config.json`:

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

More detail: [`backend/features/mcp/README.md`](backend/features/mcp/README.md).
