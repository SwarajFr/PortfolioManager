# NSE Multi-Strategy Stock Screener

**Date:** 2026-07-17
**Status:** Approved

## Goal

Add a new self-contained feature `screener/` (sibling of `exit/`, `fragility/`,
`portfolio/`) that screens the NSE500 universe across five technical strategies.
Nothing heavy is recomputed at screen time: a three-layer cache seeds full price
history once, appends new candles incrementally on each login, and stores
per-stock strategy signals so a screen only runs the cheap cross-stock step.
Two frontend pages: single-strategy raw-ranked results, and a multi-strategy
weighted screener with K-of-N matching and a fallback list.

## Decisions (confirmed with user)

- **Login refresh trigger:** hook one `screener_on_login()` call into
  `auth/routes.py` `callback()` after `set_access_token()`. Spawns a background
  thread; does not re-implement auth.
- **Cache backend:** SQLite (`screener_cache.db`), separate from `settings.db`.
  Switchable to parquet later via a settings key, but SQLite is the default and
  the only implementation built now.
- **NSE500 file:** NSE official constituents CSV (`ind_nifty500list.csv` shape)
  with a `Symbol` column. A small sample file is committed at the settings path;
  the user replaces it by hand ~quarterly.
- **Seed lookback:** `seed_lookback_days = 500` calendar days (clears momentum
  252+21 and 52w-high 252 trading days with buffer). A setting.
- **Kite rate limit:** `kite_rate_limit_rps = 3.0`. A setting.
- **Frontend structure:** one nav view `screener` with an internal tab toggle for
  the two pages (not two top-level nav items).
- **Signals storage:** one latest row per symbol (rewritten when the symbol gets
  a new candle).

## HARD RULE — all config in `screener/settings.py`

Module-constant idiom matching existing `settings.py` files: a `_DEFAULTS` dict +
`get_settings()` / `save_screener_settings()` / `reset_screener_settings()`
wrapping `core/settings_store.py` (table `screener_settings`). No literals in
`data.py` / `compute.py` / `engine.py`. Defaults:

```
strategies:
  ma_crossover:   { fast: 20, slow: 50 }
  momentum_12_1:  { lookback: 252, skip: 21 }
  breakout:       { n_high: 20 }
  rsi_reversion:  { rsi_period: 14, oversold: 30 }
  high_52w:       { window: 252, proximity: 0.90 }
screener:
  default_k:      "all"        # "all" (strict AND) or an int
  weights:        {}           # empty -> equal 1/N at runtime
  fallback_n:     10
  normalization:  "percentile"
universe:
  segment:            "NSE-EQ"
  constituents_path:  "data/nse500.csv"   # relative to backend/
  membership_column:  "Symbol"
data:
  cache_backend:        "sqlite"
  cache_path:           "screener_cache.db"
  seed_lookback_days:   500
  kite_rate_limit_rps:  3.0
```

## Architecture

```
backend/features/screener/
  __init__.py     empty (convention)
  settings.py     ALL config (module-constant idiom)
  cache.py        NEW: SQLite OHLC + signals + meta store
  data.py         Kite I/O: build_universe, seed_history, refresh_ohlc,
                  read_ohlc, last_updated
  compute.py      pure functions (no I/O): 5 strategies, normalize, aggregate,
                  k_of_n_match, rank_and_fallback, build_signals_row
  engine.py       Strategy ABC + registry + run_individual / run_combined
  service.py      orchestration: on_login, status, individual, scan, refresh
  routes.py       APIRouter (prefix added in main.py)
```

`cache.py` is a deliberate 5th module: the three-layer cache is its own bounded
unit (schema + append/read/meta), keeping `compute`/`engine` pure and testable
against an in-memory DB, and decoupled from Kite I/O in `data.py`.

## Data model — `screener_cache.db`

- `candles(symbol TEXT, date TEXT, open, high, low, close, volume)` —
  PK `(symbol, date)`. Incremental append only; never backfilled or deduped.
- `signals(symbol TEXT PRIMARY KEY, as_of_date TEXT, scores_json TEXT, passes_json TEXT)` —
  one latest row per symbol; rewritten only when that symbol gets a new candle.
  This is the only layer screens read.
- `meta(key TEXT PRIMARY KEY, value TEXT)` — `last_updated`, `seed_complete`.

## Three-layer caching flow

1. **History (once):** `seed_history()` fetches `seed_lookback_days` of daily
   OHLC for every universe symbol, writes `candles`, computes+writes `signals`,
   sets `meta.seed_complete=1`.
2. **Incremental (per login):** `refresh_ohlc()` fetches candles strictly after
   each symbol's stored `max(date)` (throttled to `kite_rate_limit_rps`),
   **skip-and-logs** any symbol Kite rejects (delisted/removed), appends new
   rows, and for each symbol that got >=1 new candle recomputes
   `build_signals_row` and upserts `signals`. Updates `meta.last_updated`.
3. **Screen (per request):** reads `signals` only. Cross-stock step runs live on
   ~500 rows: percentile-normalize -> weighted aggregate -> K-of-N -> rank /
   fallback. Milliseconds. **Never calls Kite.**

`screener_on_login()` runs in a background thread guarded by a module `Lock`
(stacked logins don't overlap): if `seed_complete` unset -> `seed_history()`,
else -> `refresh_ohlc()`. Non-blocking; UI serves cached data throughout.

## Universe filter

`build_universe()`: `kite.instruments()` -> keep `segment == settings.segment`
("NSE-EQ") -> keep symbols present in the static NSE500 file. The membership test
lives behind one function `_passes_liquidity_filter(symbols, universe_df)` so a
turnover floor can replace the NSE500 check later without touching callers.

## Compute (pure functions on DataFrames, params from settings)

Each strategy yields a continuous `score` and a boolean `pass`:

1. **MA crossover** — pass: `fastMA > slowMA`; score: `(fastMA - slowMA)/slowMA`
2. **Momentum 12-1** — pass: `ret > 0`; score: `price[t-skip]/price[t-lookback] - 1`
3. **Breakout** — pass: `close > rolling_max(high, n_high)` of the PRIOR window;
   score: `close / rolling_max(high, n_high)`
4. **RSI reversion** — pass: `RSI(rsi_period) < oversold`; score: `100 - RSI`
   (contrarian: scores weakness as strength)
5. **52w high** — pass: `close >= proximity * max(high, window)`;
   score: `close / max(high, window)`

Plus: `build_signals_row(df)` -> `{score, pass}` for all 5 (populates the signals
layer); `percentile_normalize()` -> rank each strategy's score across the universe
to [0,1]; `aggregate()` -> `sum(w_s * norm_s)/sum(w_s)`; `k_of_n_match()` ->
qualifies if passes >= K selected; `rank_and_fallback()` -> matched sorted by
aggregate desc, else top `fallback_n` by aggregate.

## Engine

- `Strategy` ABC: `name`, `compute(df)->Series`, `passes(df)->Series`. One class
  per strategy, params pulled from settings, self-registering into `REGISTRY`.
  New strategy = one new class, no other edits. `/strategies` lists the registry.
- `run_individual(strategy)` -> Page 1: symbols passing that ONE strategy, ranked
  by RAW score (no normalize/aggregate). Reads cached signals.
- `run_combined(selected, weights, k, fallback_n)` -> Page 2: normalize ->
  weighted aggregate -> K-of-N -> rank + fallback. Reads cached signals.
  Weights default equal (1/N); k default "all" (strict AND), accepts int to loosen.

## Routes (prefix `/api/screener` in `main.py`)

- `GET  /strategies` -> registered strategy metadata (name + params)
- `GET  /individual?strategy=` -> Page 1
- `POST /scan` (body: `strategies[]`, `weights{}`, `k`, `fallback_n`; all
  optional -> settings defaults) -> Page 2, with `is_fallback` flag
- `POST /refresh` -> manual incremental refresh
- `GET  /status` -> `last_updated` + seed/cache state

Scan/individual endpoints read ONLY the cache — no live Kite calls. All responses
JSON-serializable.

## Frontend

- `services/screenerService.js` (named `apiClient` import), nav entry `screener`
  in `navigation.js`, lazy page in `App.jsx` `PAGES` map.
- `features/screener/ScreenerPage.jsx` with an internal tab toggle:
  - **Strategies:** single-select strategy -> table of passing stocks ranked by
    raw score.
  - **Screener:** multi-select strategies, per-strategy weight inputs (pre-filled
    equal), K selector (default "all"), fallback-N input (default 10) -> ranked
    table with a clear **fallback badge** when the fallback list is shown.
  - Both show a **"last updated"** indicator from `/status`.
- Reuses `Card` / `DataTable` / `PanelHeader` / `EmptyState` / theme vars.
- **Does NOT touch** Portfolio, Exit, or Fragility components.

## Files changed vs created

- **Created (backend):** `features/screener/{__init__,settings,cache,data,compute,engine,service,routes}.py`,
  `data/nse500.csv` (sample), `tests/test_screener.py`.
- **Created (frontend):** `services/screenerService.js`,
  `features/screener/ScreenerPage.jsx` + `components/*` + `hooks/*`.
- **Changed (minimal):** `main.py` (+1 router), `auth/routes.py` (+1 on-login
  hook), `constants/navigation.js` (+1 nav item), `app/App.jsx` (+1 lazy page),
  CLAUDE.md (feature doc). No behavior change to existing features.

## Tests (pytest, `uv run`)

On synthetic OHLC with known structure:
- Each strategy's pass/score fires on a constructed positive case.
- `percentile_normalize` outputs in [0,1] and monotonic in raw score.
- `k_of_n_match`: k="all" == strict AND; k=1 == union of any pass.
- Empty matched set triggers fallback of exactly `fallback_n` rows.
- Equal-weight aggregate == plain mean of normalized scores.
- Universe filter keeps only NSE500 names on a synthetic instruments list.
- Incremental refresh appends only new-dated candles (no duplicate/backfill).
- Cached signals are read, not recomputed, at screen time (assert compute path
  is not re-invoked on a screen call).
- Endpoints return JSON-serializable payloads.

## Success criteria

- `uv run pytest` passes (backend); `npm run build` + `npm run lint` pass (frontend).
- Login triggers a non-blocking background refresh; UI usable on cached data.
- `/status` surfaces `last_updated`; both pages show it.
- A screen call issues zero Kite requests.
- Adding a new strategy requires only one new `Strategy` subclass.
