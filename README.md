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

## Tech Stack

- Backend: FastAPI, Python (python 3.12 recommended ), Pandas, NumPy, SciPy, scikit-learn
- Frontend: React, Vite, Axios
- Broker integration: Zerodha Kite Connect API

## How to Run

### Backend

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
   ```

4. Start the backend server:
   ```bash
   uv run uvicorn main:app --reload
   ```

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
