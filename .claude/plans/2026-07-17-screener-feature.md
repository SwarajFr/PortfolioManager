# NSE Multi-Strategy Screener — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a self-contained `screener/` feature that screens the NSE500 universe across five technical strategies, reading from a three-layer SQLite cache so screens never recompute indicators or hit Kite.

**Architecture:** Backend feature module mirroring `exit/`/`fragility/` with an extra `cache.py` (SQLite OHLC + signals + meta). `data.py` does Kite I/O + cache orchestration (seed once, incremental append per login, skip-log missing symbols). `compute.py` holds pure per-stock strategy math + cross-stock aggregation. `engine.py` holds a `Strategy` ABC + self-registering classes + the two run paths that read cached signals. `service.py` spawns a Lock-guarded background refresh on login. Two React pages behind one nav view.

**Tech Stack:** Python 3.12+, FastAPI, pandas, numpy, SQLite (stdlib `sqlite3`), pytest, `uv` for all Python commands. React 19 (no TypeScript), Vite, Tailwind v4, axios.

## Global Constraints

- Run every Python command with `uv run` from `backend/`; never `pip`/bare `python`/`uvicorn`.
- **All configuration lives in `screener/settings.py`.** No numeric/string literals for strategy params, thresholds, paths, lookbacks, or rate limits anywhere in `data.py`/`compute.py`/`engine.py`.
- `settings.py` uses the **module-constant idiom** (a `_DEFAULTS` dict + `get_settings()`/`save_*()`/`reset_*()` wrapping `core/settings_store.py`), NOT pydantic Settings.
- Kite access only via `get_kite()` from `core/kite.py`. Never re-implement auth or store credentials.
- Price refresh must **skip-and-log** any symbol Kite rejects (delisted/removed) — never crash the run.
- **Screens read ONLY the cache.** `run_individual`/`run_combined`/scan/individual endpoints must issue zero Kite calls.
- `routes.py` uses a bare `APIRouter()`; the `/api/screener` prefix is added in `main.py`.
- Frontend: `apiClient` is a **named export** (`import { apiClient }`). Do NOT touch Portfolio/Exit/Fragility components. Styling is Tailwind v4 with `var(--color-*)` refs.
- Strategy defaults: MA `fast=20,slow=50`; Momentum `lookback=252,skip=21`; Breakout `n_high=20`; RSI `rsi_period=14,oversold=30`; 52w `window=252,proximity=0.90`. Screener: `default_k="all"`, weights equal, `fallback_n=10`, `normalization="percentile"`. Universe: `segment="NSE-EQ"`, NSE500 membership from static CSV. Data: `cache_backend="sqlite"`, `seed_lookback_days=500`, `kite_rate_limit_rps=3.0`.

---

## File Structure

**Backend — created:**
- `backend/features/screener/__init__.py` — empty
- `backend/features/screener/settings.py` — all config
- `backend/features/screener/cache.py` — SQLite candles/signals/meta store
- `backend/features/screener/compute.py` — pure strategy math + aggregation
- `backend/features/screener/engine.py` — Strategy ABC + registry + run paths
- `backend/features/screener/data.py` — Kite I/O + cache orchestration
- `backend/features/screener/service.py` — orchestration + background refresh
- `backend/features/screener/routes.py` — FastAPI router
- `backend/data/nse500.csv` — sample constituents file
- `backend/tests/test_screener.py` — all backend tests

**Backend — modified:**
- `backend/main.py` — mount `screener_router` at `/api/screener`
- `backend/features/auth/routes.py` — call `screener_on_login()` after `set_access_token()`

**Frontend — created:**
- `frontend/src/services/screenerService.js`
- `frontend/src/features/screener/ScreenerPage.jsx`
- `frontend/src/features/screener/hooks/useScreener.js`
- `frontend/src/features/screener/components/StrategiesPanel.jsx`
- `frontend/src/features/screener/components/ScreenerPanel.jsx`
- `frontend/src/features/screener/components/LastUpdated.jsx`

**Frontend — modified:**
- `frontend/src/constants/navigation.js` — add `screener` nav item
- `frontend/src/app/App.jsx` — lazy-register `ScreenerPage`

**Docs — modified (final task):** `CLAUDE.md` — add screener feature section.

---

### Task 1: Settings module + sample constituents file

**Files:**
- Create: `backend/features/screener/__init__.py` (empty)
- Create: `backend/features/screener/settings.py`
- Create: `backend/data/nse500.csv`
- Test: `backend/tests/test_screener.py`

**Interfaces:**
- Produces: `get_settings() -> dict`, `save_screener_settings(dict) -> None`, `reset_screener_settings() -> dict`, module constant `_DEFAULTS`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_screener.py`:

```python
"""Tests for the NSE multi-strategy screener."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from features.screener import settings as screener_settings


def test_defaults_have_all_config_keys():
    d = screener_settings.get_settings()
    assert d["strategies"]["ma_crossover"] == {"fast": 20, "slow": 50}
    assert d["strategies"]["momentum_12_1"] == {"lookback": 252, "skip": 21}
    assert d["strategies"]["breakout"] == {"n_high": 20}
    assert d["strategies"]["rsi_reversion"] == {"rsi_period": 14, "oversold": 30}
    assert d["strategies"]["high_52w"] == {"window": 252, "proximity": 0.90}
    assert d["screener"]["default_k"] == "all"
    assert d["screener"]["fallback_n"] == 10
    assert d["screener"]["normalization"] == "percentile"
    assert d["universe"]["segment"] == "NSE-EQ"
    assert d["data"]["seed_lookback_days"] == 500
    assert d["data"]["kite_rate_limit_rps"] == 3.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_screener.py::test_defaults_have_all_config_keys -v`
Expected: FAIL — `ModuleNotFoundError: features.screener`.

- [ ] **Step 3: Write the settings module**

Create `backend/features/screener/__init__.py` empty. Create `backend/features/screener/settings.py`:

```python
from core.settings_store import (
    load_settings,
    reset_settings as reset_stored_settings,
    save_settings as save_stored_settings,
)

_TABLE = "screener_settings"

_DEFAULTS = {
    "strategies": {
        "ma_crossover": {"fast": 20, "slow": 50},
        "momentum_12_1": {"lookback": 252, "skip": 21},
        "breakout": {"n_high": 20},
        "rsi_reversion": {"rsi_period": 14, "oversold": 30},
        "high_52w": {"window": 252, "proximity": 0.90},
    },
    "screener": {
        "default_k": "all",       # "all" (strict AND) or an int
        "weights": {},            # empty -> equal 1/N at runtime
        "fallback_n": 10,
        "normalization": "percentile",
    },
    "universe": {
        "segment": "NSE-EQ",
        "constituents_path": "data/nse500.csv",  # relative to backend/
        "membership_column": "Symbol",
    },
    "data": {
        "cache_backend": "sqlite",
        "cache_path": "screener_cache.db",       # relative to backend/
        "seed_lookback_days": 500,
        "kite_rate_limit_rps": 3.0,
    },
}


def get_settings() -> dict:
    return load_settings(_TABLE, _DEFAULTS)


def save_screener_settings(config: dict) -> None:
    save_stored_settings(_TABLE, {**_DEFAULTS, **config})


def reset_screener_settings() -> dict:
    return reset_stored_settings(_TABLE, _DEFAULTS)
```

Create `backend/data/nse500.csv` (sample — user replaces quarterly):

```csv
Company Name,Industry,Symbol,Series,ISIN Code
Reliance Industries Ltd.,Oil Gas & Consumable Fuels,RELIANCE,EQ,INE002A01018
Tata Consultancy Services Ltd.,Information Technology,TCS,EQ,INE467B01029
HDFC Bank Ltd.,Financial Services,HDFCBANK,EQ,INE040A01034
Infosys Ltd.,Information Technology,INFY,EQ,INE009A01021
ICICI Bank Ltd.,Financial Services,ICICIBANK,EQ,INE090A01021
State Bank of India,Financial Services,SBIN,EQ,INE062A01020
ITC Ltd.,Fast Moving Consumer Goods,ITC,EQ,INE154A01025
Larsen & Toubro Ltd.,Construction,LT,EQ,INE018A01030
Hindustan Unilever Ltd.,Fast Moving Consumer Goods,HINDUNILVR,EQ,INE030A01027
Axis Bank Ltd.,Financial Services,AXISBANK,EQ,INE238A01034
Bharti Airtel Ltd.,Telecommunication,BHARTIARTL,EQ,INE397D01024
Kotak Mahindra Bank Ltd.,Financial Services,KOTAKBANK,EQ,INE237A01028
Bajaj Finance Ltd.,Financial Services,BAJFINANCE,EQ,INE296A01024
Asian Paints Ltd.,Consumer Durables,ASIANPAINT,EQ,INE021A01026
Maruti Suzuki India Ltd.,Automobile and Auto Components,MARUTI,EQ,INE585B01010
Sun Pharmaceutical Industries Ltd.,Healthcare,SUNPHARMA,EQ,INE044A01036
Titan Company Ltd.,Consumer Durables,TITAN,EQ,INE280A01028
Wipro Ltd.,Information Technology,WIPRO,EQ,INE075A01022
Nestle India Ltd.,Fast Moving Consumer Goods,NESTLEIND,EQ,INE239A01024
Tata Motors Ltd.,Automobile and Auto Components,TATAMOTORS,EQ,INE155A01022
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_screener.py::test_defaults_have_all_config_keys -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/features/screener/__init__.py backend/features/screener/settings.py backend/data/nse500.csv backend/tests/test_screener.py
git commit -m "feat(screener): settings module + sample NSE500 file"
```

---

### Task 2: SQLite cache layer

**Files:**
- Create: `backend/features/screener/cache.py`
- Test: `backend/tests/test_screener.py`

**Interfaces:**
- Produces (all take an explicit `path` so tests use a temp DB):
  - `init(path: str) -> None`
  - `upsert_candles(path, symbol: str, rows: list[dict]) -> int` — rows have keys `date,open,high,low,close,volume`; `date` is `YYYY-MM-DD` str; returns number of new rows inserted. `INSERT OR IGNORE` on PK `(symbol,date)`.
  - `last_candle_date(path, symbol) -> str | None`
  - `read_candles(path, symbol) -> pd.DataFrame` — columns `date,open,high,low,close,volume`, sorted ascending by date.
  - `upsert_signal(path, symbol, as_of_date: str, scores: dict, passes: dict) -> None`
  - `read_signals(path) -> list[dict]` — each `{symbol, as_of_date, scores, passes}` (json decoded).
  - `get_meta(path, key) -> str | None`, `set_meta(path, key, value: str) -> None`
  - `symbol_count(path) -> int` — distinct symbols in candles.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_screener.py`:

```python
from features.screener import cache as screener_cache


@pytest.fixture()
def db(tmp_path):
    path = str(tmp_path / "screener_cache.db")
    screener_cache.init(path)
    return path


def test_upsert_candles_is_append_only(db):
    rows = [
        {"date": "2026-01-01", "open": 1, "high": 2, "low": 1, "close": 1.5, "volume": 10},
        {"date": "2026-01-02", "open": 1.5, "high": 2.5, "low": 1.4, "close": 2.0, "volume": 12},
    ]
    assert screener_cache.upsert_candles(db, "RELIANCE", rows) == 2
    # Re-inserting the same dates + one new date appends only the new one.
    more = rows + [{"date": "2026-01-03", "open": 2, "high": 3, "low": 2, "close": 2.5, "volume": 9}]
    assert screener_cache.upsert_candles(db, "RELIANCE", more) == 1
    df = screener_cache.read_candles(db, "RELIANCE")
    assert list(df["date"]) == ["2026-01-01", "2026-01-02", "2026-01-03"]
    assert screener_cache.last_candle_date(db, "RELIANCE") == "2026-01-03"


def test_signals_roundtrip(db):
    screener_cache.upsert_signal(
        db, "TCS", "2026-01-03", {"ma_crossover": 0.1}, {"ma_crossover": True}
    )
    rows = screener_cache.read_signals(db)
    assert rows == [
        {"symbol": "TCS", "as_of_date": "2026-01-03",
         "scores": {"ma_crossover": 0.1}, "passes": {"ma_crossover": True}}
    ]


def test_meta_roundtrip(db):
    assert screener_cache.get_meta(db, "seed_complete") is None
    screener_cache.set_meta(db, "seed_complete", "1")
    assert screener_cache.get_meta(db, "seed_complete") == "1"
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && uv run pytest tests/test_screener.py -k "cache or candles or signals_roundtrip or meta_roundtrip" -v`
Expected: FAIL — `ModuleNotFoundError` / `AttributeError`.

- [ ] **Step 3: Write `cache.py`**

```python
from __future__ import annotations

import json
import sqlite3

import pandas as pd

_CANDLE_COLS = ("date", "open", "high", "low", "close", "volume")


def _connect(path: str) -> sqlite3.Connection:
    return sqlite3.connect(path)


def init(path: str) -> None:
    with _connect(path) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS candles ("
            "symbol TEXT, date TEXT, open REAL, high REAL, low REAL, "
            "close REAL, volume REAL, PRIMARY KEY (symbol, date))"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS signals ("
            "symbol TEXT PRIMARY KEY, as_of_date TEXT, "
            "scores_json TEXT, passes_json TEXT)"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)"
        )


def upsert_candles(path: str, symbol: str, rows: list[dict]) -> int:
    if not rows:
        return 0
    with _connect(path) as conn:
        before = conn.total_changes
        conn.executemany(
            "INSERT OR IGNORE INTO candles "
            "(symbol, date, open, high, low, close, volume) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (symbol, r["date"], r["open"], r["high"], r["low"], r["close"], r["volume"])
                for r in rows
            ],
        )
        return conn.total_changes - before


def last_candle_date(path: str, symbol: str) -> str | None:
    with _connect(path) as conn:
        row = conn.execute(
            "SELECT MAX(date) FROM candles WHERE symbol = ?", (symbol,)
        ).fetchone()
    return row[0] if row else None


def read_candles(path: str, symbol: str) -> pd.DataFrame:
    with _connect(path) as conn:
        rows = conn.execute(
            "SELECT date, open, high, low, close, volume FROM candles "
            "WHERE symbol = ? ORDER BY date ASC",
            (symbol,),
        ).fetchall()
    return pd.DataFrame(rows, columns=list(_CANDLE_COLS))


def upsert_signal(path: str, symbol: str, as_of_date: str, scores: dict, passes: dict) -> None:
    with _connect(path) as conn:
        conn.execute(
            "INSERT INTO signals (symbol, as_of_date, scores_json, passes_json) "
            "VALUES (?, ?, ?, ?) ON CONFLICT(symbol) DO UPDATE SET "
            "as_of_date = excluded.as_of_date, scores_json = excluded.scores_json, "
            "passes_json = excluded.passes_json",
            (symbol, as_of_date, json.dumps(scores), json.dumps(passes)),
        )


def read_signals(path: str) -> list[dict]:
    with _connect(path) as conn:
        rows = conn.execute(
            "SELECT symbol, as_of_date, scores_json, passes_json FROM signals"
        ).fetchall()
    return [
        {
            "symbol": s,
            "as_of_date": d,
            "scores": json.loads(sj),
            "passes": json.loads(pj),
        }
        for s, d, sj, pj in rows
    ]


def get_meta(path: str, key: str) -> str | None:
    with _connect(path) as conn:
        row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return row[0] if row else None


def set_meta(path: str, key: str, value: str) -> None:
    with _connect(path) as conn:
        conn.execute(
            "INSERT INTO meta (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )


def symbol_count(path: str) -> int:
    with _connect(path) as conn:
        row = conn.execute("SELECT COUNT(DISTINCT symbol) FROM candles").fetchone()
    return int(row[0]) if row else 0
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && uv run pytest tests/test_screener.py -k "candles or signals_roundtrip or meta_roundtrip" -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/features/screener/cache.py backend/tests/test_screener.py
git commit -m "feat(screener): SQLite cache layer (candles/signals/meta)"
```

---

### Task 3: Compute — per-stock strategy functions

**Files:**
- Create: `backend/features/screener/compute.py`
- Test: `backend/tests/test_screener.py`

**Interfaces:**
- Produces (all pure, take a single symbol's OHLC `df` with columns `open,high,low,close,volume` + explicit params, return `pd.Series` aligned to `df.index`):
  - `sma(series: pd.Series, window: int) -> pd.Series`
  - `rsi(close: pd.Series, period: int) -> pd.Series`
  - `ma_crossover_score(df, fast, slow) -> pd.Series` / `ma_crossover_pass(df, fast, slow) -> pd.Series`
  - `momentum_score(df, lookback, skip) -> pd.Series` / `momentum_pass(df, lookback, skip) -> pd.Series`
  - `breakout_score(df, n_high) -> pd.Series` / `breakout_pass(df, n_high) -> pd.Series`
  - `rsi_reversion_score(df, rsi_period) -> pd.Series` / `rsi_reversion_pass(df, rsi_period, oversold) -> pd.Series`
  - `high_52w_score(df, window) -> pd.Series` / `high_52w_pass(df, window, proximity) -> pd.Series`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_screener.py`:

```python
from features.screener import compute


def _uptrend_df(n=300):
    """Strictly rising close/high — MA fast>slow, momentum>0, near highs, and a
    genuine breakout. The slope MUST be steep enough that the daily close
    increment exceeds the +1 high offset; otherwise yesterday's high exceeds
    today's close and `breakout_pass` (which compares to the PRIOR window via
    shift(1)) is correctly False. linspace(100, 600, 300) gives a ~1.67/day
    increment > 1.0, so today's close clears the prior 20-day high."""
    idx = pd.date_range("2025-01-01", periods=n, freq="D")
    close = pd.Series(np.linspace(100, 600, n), index=idx)
    high = close + 1.0
    low = close - 1.0
    return pd.DataFrame(
        {"open": close, "high": high, "low": low, "close": close, "volume": 1000.0},
        index=idx,
    )


def test_ma_crossover_positive_case():
    df = _uptrend_df()
    assert bool(compute.ma_crossover_pass(df, 20, 50).iloc[-1]) is True
    assert compute.ma_crossover_score(df, 20, 50).iloc[-1] > 0


def test_momentum_positive_case():
    df = _uptrend_df()
    assert bool(compute.momentum_pass(df, 252, 21).iloc[-1]) is True
    assert compute.momentum_score(df, 252, 21).iloc[-1] > 0


def test_breakout_positive_case():
    df = _uptrend_df()
    # Rising series: today's close exceeds the prior 20-day high window.
    assert bool(compute.breakout_pass(df, 20).iloc[-1]) is True
    assert compute.breakout_score(df, 20).iloc[-1] > 1.0


def test_rsi_reversion_positive_case():
    # Strictly falling close -> RSI near 0 -> oversold, high contrarian score.
    idx = pd.date_range("2025-01-01", periods=100, freq="D")
    close = pd.Series(np.linspace(200, 100, 100), index=idx)
    df = pd.DataFrame(
        {"open": close, "high": close + 1, "low": close - 1, "close": close, "volume": 1.0},
        index=idx,
    )
    assert bool(compute.rsi_reversion_pass(df, 14, 30).iloc[-1]) is True
    assert compute.rsi_reversion_score(df, 14).iloc[-1] > 70


def test_high_52w_positive_case():
    df = _uptrend_df()
    assert bool(compute.high_52w_pass(df, 252, 0.90).iloc[-1]) is True
    assert compute.high_52w_score(df, 252).iloc[-1] == pytest.approx(1.0, abs=0.02)
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && uv run pytest tests/test_screener.py -k "positive_case" -v`
Expected: FAIL — `AttributeError` on `compute`.

- [ ] **Step 3: Write `compute.py` (strategy functions)**

```python
"""Pure computation layer for the NSE screener.

Per-stock strategy functions take one symbol's OHLC DataFrame plus explicit
params (params come from settings via the engine — never hardcoded here) and
return a pandas Series aligned to the input index. Cross-stock functions
(percentile_normalize, aggregate, k_of_n_match, rank_and_fallback,
build_signals_row) are added in the next task.
"""
from __future__ import annotations

import pandas as pd


def sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window).mean()


def rsi(close: pd.Series, period: int) -> pd.Series:
    """Wilder's RSI."""
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


# 1. MA crossover
def ma_crossover_score(df: pd.DataFrame, fast: int, slow: int) -> pd.Series:
    f = sma(df["close"], fast)
    s = sma(df["close"], slow)
    return (f - s) / s


def ma_crossover_pass(df: pd.DataFrame, fast: int, slow: int) -> pd.Series:
    return sma(df["close"], fast) > sma(df["close"], slow)


# 2. Momentum 12-1
def momentum_score(df: pd.DataFrame, lookback: int, skip: int) -> pd.Series:
    c = df["close"]
    return c.shift(skip) / c.shift(lookback) - 1


def momentum_pass(df: pd.DataFrame, lookback: int, skip: int) -> pd.Series:
    return momentum_score(df, lookback, skip) > 0


# 3. Breakout (prior-window high)
# NOTE: the `.shift(1)` is REQUIRED — it makes the rolling max cover the PRIOR
# window (excluding today's own bar), which is the definition of a breakout.
# Do NOT remove it to make a test pass; if the breakout test fails, the test
# DATA is wrong (slope too shallow), not this logic.
def breakout_score(df: pd.DataFrame, n_high: int) -> pd.Series:
    prior_high = df["high"].rolling(n_high).max().shift(1)
    return df["close"] / prior_high


def breakout_pass(df: pd.DataFrame, n_high: int) -> pd.Series:
    prior_high = df["high"].rolling(n_high).max().shift(1)
    return df["close"] > prior_high


# 4. RSI reversion (contrarian: weakness scores as strength)
def rsi_reversion_score(df: pd.DataFrame, rsi_period: int) -> pd.Series:
    return 100 - rsi(df["close"], rsi_period)


def rsi_reversion_pass(df: pd.DataFrame, rsi_period: int, oversold: int) -> pd.Series:
    return rsi(df["close"], rsi_period) < oversold


# 5. 52-week high proximity
def high_52w_score(df: pd.DataFrame, window: int) -> pd.Series:
    return df["close"] / df["high"].rolling(window).max()


def high_52w_pass(df: pd.DataFrame, window: int, proximity: float) -> pd.Series:
    return df["close"] >= proximity * df["high"].rolling(window).max()
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && uv run pytest tests/test_screener.py -k "positive_case" -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/features/screener/compute.py backend/tests/test_screener.py
git commit -m "feat(screener): pure per-stock strategy functions"
```

---

### Task 4: Compute — cross-stock aggregation + signal row

**Files:**
- Modify: `backend/features/screener/compute.py`
- Test: `backend/tests/test_screener.py`

**Interfaces:**
- Produces:
  - `build_signals_row(df: pd.DataFrame, strategies: list) -> dict` — `{name: {"score": float|None, "pass": bool}}`; uses each strategy's `.compute(df).iloc[-1]` / `.passes(df).iloc[-1]` (duck-typed; strategy objects injected, no import of `engine`).
  - `percentile_normalize(scores: pd.Series) -> pd.Series` — `scores.rank(pct=True)`, in [0,1], monotonic.
  - `aggregate(norm: pd.DataFrame, weights: dict) -> pd.Series` — `Σ(w·norm)/Σw` over the weighted columns.
  - `k_of_n_match(passes: pd.DataFrame, k) -> pd.Series` — bool per row; `k=="all"` → count == n columns; int → count >= k.
  - `rank_and_fallback(agg: pd.Series, matched_mask: pd.Series, fallback_n: int) -> tuple[list[str], bool]` — `(ranked_symbols, is_fallback)`.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_screener.py`:

```python
def test_percentile_normalize_range_and_monotonic():
    s = pd.Series([10.0, 20.0, 30.0, 40.0], index=["a", "b", "c", "d"])
    norm = compute.percentile_normalize(s)
    assert norm.min() >= 0.0 and norm.max() <= 1.0
    # Monotonic: order preserved.
    assert list(norm.sort_values().index) == ["a", "b", "c", "d"]


def test_aggregate_equal_weight_equals_mean():
    norm = pd.DataFrame(
        {"x": [0.2, 0.8], "y": [0.4, 0.6]}, index=["a", "b"]
    )
    agg = compute.aggregate(norm, {"x": 1.0, "y": 1.0})
    assert agg["a"] == pytest.approx((0.2 + 0.4) / 2)
    assert agg["b"] == pytest.approx((0.8 + 0.6) / 2)


def test_k_of_n_all_is_strict_and():
    passes = pd.DataFrame(
        {"x": [True, True, False], "y": [True, False, False]},
        index=["a", "b", "c"],
    )
    match = compute.k_of_n_match(passes, "all")
    assert list(match) == [True, False, False]


def test_k_of_n_one_is_union():
    passes = pd.DataFrame(
        {"x": [True, True, False], "y": [True, False, False]},
        index=["a", "b", "c"],
    )
    match = compute.k_of_n_match(passes, 1)
    assert list(match) == [True, True, False]


def test_rank_and_fallback_triggers_on_empty_match():
    agg = pd.Series([0.9, 0.5, 0.7, 0.1, 0.3], index=["a", "b", "c", "d", "e"])
    matched = pd.Series([False] * 5, index=agg.index)
    ranked, is_fallback = compute.rank_and_fallback(agg, matched, fallback_n=3)
    assert is_fallback is True
    assert ranked == ["a", "c", "b"]  # top-3 by aggregate desc


def test_rank_and_fallback_returns_matches_when_present():
    agg = pd.Series([0.9, 0.5, 0.7], index=["a", "b", "c"])
    matched = pd.Series([True, False, True], index=agg.index)
    ranked, is_fallback = compute.rank_and_fallback(agg, matched, fallback_n=10)
    assert is_fallback is False
    assert ranked == ["a", "c"]
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && uv run pytest tests/test_screener.py -k "normalize or aggregate or k_of_n or fallback" -v`
Expected: FAIL — `AttributeError`.

- [ ] **Step 3: Append cross-stock functions to `compute.py`**

```python
def build_signals_row(df: pd.DataFrame, strategies: list) -> dict:
    """Per-stock {score, pass} for every strategy. Used to fill the cache's
    signals layer. `strategies` are engine.Strategy instances (duck-typed)."""
    row: dict[str, dict] = {}
    for st in strategies:
        score = st.compute(df).iloc[-1]
        passed = st.passes(df).iloc[-1]
        row[st.name] = {
            "score": None if pd.isna(score) else float(score),
            "pass": bool(passed) if pd.notna(passed) else False,
        }
    return row


def percentile_normalize(scores: pd.Series) -> pd.Series:
    """Cross-sectional rank in [0,1], monotonic in the raw score."""
    return scores.rank(pct=True)


def aggregate(norm: pd.DataFrame, weights: dict) -> pd.Series:
    """Weighted mean of normalized scores: Σ(wₛ·normₛ)/Σwₛ."""
    w = pd.Series(weights, dtype=float)
    return (norm[w.index] * w).sum(axis=1) / w.sum()


def k_of_n_match(passes: pd.DataFrame, k) -> pd.Series:
    """Row qualifies if it passes >= K of the given strategies.
    k == 'all' -> strict AND (all columns); int -> at least k."""
    counts = passes.astype(bool).sum(axis=1)
    if k == "all":
        return counts == passes.shape[1]
    return counts >= int(k)


def rank_and_fallback(
    agg: pd.Series, matched_mask: pd.Series, fallback_n: int
) -> tuple[list[str], bool]:
    """Matched sorted by aggregate desc; if empty, top fallback_n by aggregate."""
    matched = agg[matched_mask].sort_values(ascending=False)
    if len(matched) > 0:
        return list(matched.index), False
    return list(agg.sort_values(ascending=False).head(fallback_n).index), True
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && uv run pytest tests/test_screener.py -k "normalize or aggregate or k_of_n or fallback" -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/features/screener/compute.py backend/tests/test_screener.py
git commit -m "feat(screener): cross-stock normalize/aggregate/k-of-n/fallback"
```

---

### Task 5: Engine — Strategy ABC + registry + run paths

**Files:**
- Create: `backend/features/screener/engine.py`
- Test: `backend/tests/test_screener.py`

**Interfaces:**
- Produces:
  - `class Strategy(ABC)` with class attr `name`, `__init__(self, params: dict)`, abstract `compute(df)->pd.Series`, `passes(df)->pd.Series`.
  - `REGISTRY: dict[str, type[Strategy]]` and `@register` decorator.
  - Concrete classes: `MACrossover`("ma_crossover"), `Momentum121`("momentum_12_1"), `Breakout`("breakout"), `RSIReversion`("rsi_reversion"), `High52Week`("high_52w").
  - `build_strategies(settings: dict, names: list[str] | None = None) -> list[Strategy]` — instantiates registered classes from `settings["strategies"][name]`.
  - `strategy_metadata(settings: dict) -> list[dict]` — `[{name, params}]` for `/strategies`.
  - `run_individual(name: str, scores: pd.DataFrame, passes: pd.DataFrame) -> list[dict]` — passing symbols ranked by raw score desc; each `{symbol, score}`.
  - `run_combined(selected, weights, k, fallback_n, scores, passes) -> dict` — `{results:[{symbol,aggregate,passes}], is_fallback, selected, k}`.
- Consumes: `compute.*` (Task 3/4).

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_screener.py`:

```python
from features.screener import engine


def test_registry_has_all_five_strategies():
    assert set(engine.REGISTRY) == {
        "ma_crossover", "momentum_12_1", "breakout", "rsi_reversion", "high_52w"
    }


def test_build_strategies_pulls_params_from_settings():
    s = screener_settings.get_settings()
    strategies = engine.build_strategies(s)
    by_name = {st.name: st for st in strategies}
    assert by_name["ma_crossover"].params == {"fast": 20, "slow": 50}


def test_run_individual_ranks_passing_by_raw_score():
    scores = pd.DataFrame({"ma_crossover": [0.3, 0.1, 0.9]}, index=["a", "b", "c"])
    passes = pd.DataFrame({"ma_crossover": [True, False, True]}, index=["a", "b", "c"])
    out = engine.run_individual("ma_crossover", scores, passes)
    assert [r["symbol"] for r in out] == ["c", "a"]  # b filtered (no pass)
    assert out[0]["score"] == 0.9


def test_run_combined_equal_weight_and_fallback():
    scores = pd.DataFrame(
        {"ma_crossover": [0.9, 0.2], "breakout": [0.1, 0.8]}, index=["a", "b"]
    )
    passes = pd.DataFrame(
        {"ma_crossover": [False, False], "breakout": [False, False]},
        index=["a", "b"],
    )
    out = engine.run_combined(
        ["ma_crossover", "breakout"], {}, "all", 2, scores, passes
    )
    assert out["is_fallback"] is True
    assert len(out["results"]) == 2  # exactly fallback_n rows
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && uv run pytest tests/test_screener.py -k "registry or build_strategies or run_individual or run_combined" -v`
Expected: FAIL — `ModuleNotFoundError` on `engine`.

- [ ] **Step 3: Write `engine.py`**

```python
"""Strategy ABC, self-registering strategy classes, and the two run paths that
read the cached signals table. Adding a strategy = one new @register class."""
from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd

from . import compute

REGISTRY: dict[str, type["Strategy"]] = {}


def register(cls: type["Strategy"]) -> type["Strategy"]:
    REGISTRY[cls.name] = cls
    return cls


class Strategy(ABC):
    name: str = ""

    def __init__(self, params: dict):
        self.params = params

    @abstractmethod
    def compute(self, df: pd.DataFrame) -> pd.Series: ...

    @abstractmethod
    def passes(self, df: pd.DataFrame) -> pd.Series: ...


@register
class MACrossover(Strategy):
    name = "ma_crossover"

    def compute(self, df):
        return compute.ma_crossover_score(df, self.params["fast"], self.params["slow"])

    def passes(self, df):
        return compute.ma_crossover_pass(df, self.params["fast"], self.params["slow"])


@register
class Momentum121(Strategy):
    name = "momentum_12_1"

    def compute(self, df):
        return compute.momentum_score(df, self.params["lookback"], self.params["skip"])

    def passes(self, df):
        return compute.momentum_pass(df, self.params["lookback"], self.params["skip"])


@register
class Breakout(Strategy):
    name = "breakout"

    def compute(self, df):
        return compute.breakout_score(df, self.params["n_high"])

    def passes(self, df):
        return compute.breakout_pass(df, self.params["n_high"])


@register
class RSIReversion(Strategy):
    name = "rsi_reversion"

    def compute(self, df):
        return compute.rsi_reversion_score(df, self.params["rsi_period"])

    def passes(self, df):
        return compute.rsi_reversion_pass(
            df, self.params["rsi_period"], self.params["oversold"]
        )


@register
class High52Week(Strategy):
    name = "high_52w"

    def compute(self, df):
        return compute.high_52w_score(df, self.params["window"])

    def passes(self, df):
        return compute.high_52w_pass(df, self.params["window"], self.params["proximity"])


def build_strategies(settings: dict, names: list[str] | None = None) -> list[Strategy]:
    sconf = settings["strategies"]
    names = names if names is not None else list(REGISTRY)
    return [REGISTRY[n](sconf[n]) for n in names]


def strategy_metadata(settings: dict) -> list[dict]:
    sconf = settings["strategies"]
    return [{"name": n, "params": sconf[n]} for n in REGISTRY]


def run_individual(name: str, scores: pd.DataFrame, passes: pd.DataFrame) -> list[dict]:
    mask = passes[name].astype(bool)
    ranked = scores.loc[mask, name].sort_values(ascending=False)
    return [{"symbol": sym, "score": round(float(v), 4)} for sym, v in ranked.items()]


def run_combined(
    selected: list[str],
    weights: dict,
    k,
    fallback_n: int,
    scores: pd.DataFrame,
    passes: pd.DataFrame,
) -> dict:
    weights = weights or {s: 1.0 for s in selected}
    weights = {s: float(weights.get(s, 1.0)) for s in selected}
    norm = pd.DataFrame(
        {s: compute.percentile_normalize(scores[s]) for s in selected}
    )
    agg = compute.aggregate(norm, weights)
    matched = compute.k_of_n_match(passes[selected], k)
    ranked, is_fallback = compute.rank_and_fallback(agg, matched, fallback_n)
    results = [
        {
            "symbol": sym,
            "aggregate": round(float(agg[sym]), 4),
            "passes": int(passes.loc[sym, selected].astype(bool).sum()),
        }
        for sym in ranked
    ]
    return {
        "results": results,
        "is_fallback": is_fallback,
        "selected": list(selected),
        "k": k,
    }
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && uv run pytest tests/test_screener.py -k "registry or build_strategies or run_individual or run_combined" -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/features/screener/engine.py backend/tests/test_screener.py
git commit -m "feat(screener): Strategy ABC, registry, run_individual/run_combined"
```

---

### Task 6: Data layer — universe filter + incremental refresh

**Files:**
- Create: `backend/features/screener/data.py`
- Test: `backend/tests/test_screener.py`

**Interfaces:**
- Produces:
  - `load_nse500(path: str, column: str) -> set[str]` — read CSV, return the membership column as a set.
  - `filter_universe(instruments: list[dict], segment: str, members: set[str]) -> pd.DataFrame` — keep `segment` rows whose `tradingsymbol ∈ members`; columns `tradingsymbol,instrument_token`. Membership behind `_passes_liquidity_filter`.
  - `build_universe() -> pd.DataFrame` — `get_kite().instruments()` → `filter_universe(...)`.
  - `read_ohlc(symbol: str) -> pd.DataFrame` — indexed by datetime, cache-backed.
  - `last_updated() -> str | None` — `meta.last_updated`.
  - `seed_history(universe_df=None, fetch=None, today=None) -> dict` — seed all symbols; returns `{seeded, skipped}`.
  - `refresh_ohlc(universe_df=None, fetch=None, today=None) -> dict` — incremental; returns `{updated, skipped}`. `fetch(token, from_date, to_date) -> list[dict]` is injectable for tests.
- Consumes: `cache.*`, `engine.build_strategies`, `compute.build_signals_row`, `settings.get_settings`, `core.kite.get_kite`.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_screener.py`:

```python
import datetime

from features.screener import data as screener_data


def test_filter_universe_keeps_only_nse500_equities():
    instruments = [
        {"tradingsymbol": "RELIANCE", "instrument_token": 1, "segment": "NSE-EQ"},
        {"tradingsymbol": "TCS", "instrument_token": 2, "segment": "NSE-EQ"},
        {"tradingsymbol": "NIFTY 50", "instrument_token": 3, "segment": "INDICES"},
        {"tradingsymbol": "PENNYX", "instrument_token": 4, "segment": "NSE-EQ"},
    ]
    out = screener_data.filter_universe(instruments, "NSE-EQ", {"RELIANCE", "TCS"})
    assert set(out["tradingsymbol"]) == {"RELIANCE", "TCS"}
    assert 3 not in list(out["instrument_token"])  # index dropped
    assert 4 not in list(out["instrument_token"])  # non-member dropped


def test_refresh_appends_only_new_dated_candles(db, monkeypatch, tmp_path):
    # Point settings at the temp cache DB.
    s = screener_settings.get_settings()
    s["data"]["cache_path"] = db
    monkeypatch.setattr(screener_data.settings, "get_settings", lambda: s)

    universe = pd.DataFrame(
        {"tradingsymbol": ["RELIANCE"], "instrument_token": [1]}
    )
    # Seed one candle at 2026-01-01.
    screener_cache.upsert_candles(
        db, "RELIANCE",
        [{"date": "2026-01-01", "open": 1, "high": 2, "low": 1, "close": 1.5, "volume": 5}],
    )

    calls = {}

    def fake_fetch(token, from_date, to_date):
        calls["from_date"] = from_date
        # Kite would only return candles from `from_date` onward.
        return [
            {"date": datetime.date(2026, 1, 2), "open": 1.5, "high": 2.5,
             "low": 1.4, "close": 2.0, "volume": 6}
        ]

    result = screener_data.refresh_ohlc(
        universe_df=universe, fetch=fake_fetch, today=datetime.date(2026, 1, 2)
    )
    # Incremental fetch starts strictly after the last stored date.
    assert calls["from_date"] == datetime.date(2026, 1, 2)
    df = screener_cache.read_candles(db, "RELIANCE")
    assert list(df["date"]) == ["2026-01-01", "2026-01-02"]  # appended, not backfilled
    assert result["updated"] == 1


def test_refresh_skips_and_logs_missing_symbol(db, monkeypatch):
    s = screener_settings.get_settings()
    s["data"]["cache_path"] = db
    monkeypatch.setattr(screener_data.settings, "get_settings", lambda: s)
    universe = pd.DataFrame({"tradingsymbol": ["DELISTED"], "instrument_token": [99]})

    def boom(token, from_date, to_date):
        raise Exception("instrument not found")

    result = screener_data.refresh_ohlc(
        universe_df=universe, fetch=boom, today=datetime.date(2026, 1, 2)
    )
    assert result["skipped"] == 1  # did not crash
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && uv run pytest tests/test_screener.py -k "filter_universe or refresh_appends or refresh_skips" -v`
Expected: FAIL — `ModuleNotFoundError` on `data`.

- [ ] **Step 3: Write `data.py`**

```python
"""Data layer: Kite instruments → NSE500 universe, and the three-layer OHLC
cache orchestration (seed once, incremental append per refresh). Decoupled from
screening: screens never call anything here."""
from __future__ import annotations

import datetime
import logging
import time

import pandas as pd

from core.kite import get_kite

from . import cache, compute, settings
from .engine import build_strategies

logger = logging.getLogger(__name__)


# ── Universe ─────────────────────────────────────────────────────────────────
def load_nse500(path: str, column: str) -> set[str]:
    df = pd.read_csv(path)
    return set(df[column].astype(str).str.strip())


def _passes_liquidity_filter(symbol: str, members: set[str]) -> bool:
    """The one pluggable membership gate. Swap NSE500 for a turnover floor here
    without touching callers."""
    return symbol in members


def filter_universe(
    instruments: list[dict], segment: str, members: set[str]
) -> pd.DataFrame:
    rows = [
        {"tradingsymbol": i["tradingsymbol"], "instrument_token": i["instrument_token"]}
        for i in instruments
        if i.get("segment") == segment
        and _passes_liquidity_filter(i["tradingsymbol"], members)
    ]
    return pd.DataFrame(rows, columns=["tradingsymbol", "instrument_token"])


def build_universe() -> pd.DataFrame:
    conf = settings.get_settings()["universe"]
    members = load_nse500(conf["constituents_path"], conf["membership_column"])
    instruments = get_kite().instruments()
    return filter_universe(instruments, conf["segment"], members)


# ── Cache reads ──────────────────────────────────────────────────────────────
def _cache_path() -> str:
    return settings.get_settings()["data"]["cache_path"]


def read_ohlc(symbol: str) -> pd.DataFrame:
    df = cache.read_candles(_cache_path(), symbol)
    if not df.empty:
        df = df.set_index(pd.to_datetime(df["date"]))
    return df


def last_updated() -> str | None:
    return cache.get_meta(_cache_path(), "last_updated")


# ── Fetch + refresh ──────────────────────────────────────────────────────────
def _default_fetch(token: int, from_date, to_date) -> list[dict]:
    return get_kite().historical_data(token, from_date, to_date, "day")


def _normalize_rows(records: list[dict]) -> list[dict]:
    out = []
    for r in records:
        d = r["date"]
        d = d.date() if isinstance(d, datetime.datetime) else d
        out.append({
            "date": d.isoformat() if hasattr(d, "isoformat") else str(d),
            "open": r["open"], "high": r["high"], "low": r["low"],
            "close": r["close"], "volume": r.get("volume", 0),
        })
    return out


def _recompute_signal(path: str, symbol: str, strategies: list) -> None:
    df = cache.read_candles(path, symbol)
    if df.empty:
        return
    row = compute.build_signals_row(df, strategies)
    scores = {n: v["score"] for n, v in row.items()}
    passes = {n: v["pass"] for n, v in row.items()}
    cache.upsert_signal(path, symbol, str(df["date"].iloc[-1]), scores, passes)


def _run(universe_df, fetch, today, seed: bool) -> dict:
    conf = settings.get_settings()
    path = conf["data"]["cache_path"]
    cache.init(path)
    rps = conf["data"]["kite_rate_limit_rps"]
    lookback = conf["data"]["seed_lookback_days"]
    delay = (1.0 / rps) if (rps and fetch is None) else 0.0

    if universe_df is None:
        universe_df = build_universe()
    if fetch is None:
        fetch = _default_fetch
    if today is None:
        today = datetime.date.today()

    strategies = build_strategies(conf)
    updated = 0
    skipped = 0

    for _, r in universe_df.iterrows():
        symbol = str(r["tradingsymbol"])
        token = int(r["instrument_token"])
        if seed:
            from_date = today - datetime.timedelta(days=lookback)
        else:
            last = cache.last_candle_date(path, symbol)
            if last is None:
                from_date = today - datetime.timedelta(days=lookback)
            else:
                from_date = datetime.date.fromisoformat(last) + datetime.timedelta(days=1)
        if from_date > today:
            continue
        try:
            records = fetch(token, from_date, today)
        except Exception as exc:  # delisted/removed → skip-and-log, never crash
            logger.warning("screener refresh skipped %s: %s", symbol, exc)
            skipped += 1
            continue
        new = cache.upsert_candles(path, symbol, _normalize_rows(records))
        if new > 0:
            _recompute_signal(path, symbol, strategies)
            updated += 1
        if delay:
            time.sleep(delay)

    cache.set_meta(path, "last_updated", datetime.datetime.now().isoformat(timespec="seconds"))
    if seed:
        cache.set_meta(path, "seed_complete", "1")
    key = "seeded" if seed else "updated"
    return {key: updated, "skipped": skipped}


def seed_history(universe_df=None, fetch=None, today=None) -> dict:
    return _run(universe_df, fetch, today, seed=True)


def refresh_ohlc(universe_df=None, fetch=None, today=None) -> dict:
    return _run(universe_df, fetch, today, seed=False)
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && uv run pytest tests/test_screener.py -k "filter_universe or refresh_appends or refresh_skips" -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/features/screener/data.py backend/tests/test_screener.py
git commit -m "feat(screener): universe filter + incremental OHLC refresh"
```

---

### Task 7: Service layer — orchestration + background refresh

**Files:**
- Create: `backend/features/screener/service.py`
- Test: `backend/tests/test_screener.py`

**Interfaces:**
- Produces:
  - `get_strategies() -> dict` — `{"strategies": strategy_metadata(...)}`.
  - `get_individual(strategy: str) -> dict` — `{"strategy", "results"}`.
  - `run_scan(strategies=None, weights=None, k=None, fallback_n=None) -> dict` — fills defaults from settings; returns `run_combined(...)` shape + `last_updated`.
  - `get_status() -> dict` — `{last_updated, seed_complete, symbol_count, refreshing}`.
  - `screener_on_login() -> None` — spawn Lock-guarded background thread (seed if needed, else refresh).
  - `trigger_refresh() -> dict` — manual: spawn same background refresh, return current status.
  - `_read_signal_frames(path) -> tuple[pd.DataFrame, pd.DataFrame]` — `(scores, passes)` DataFrames indexed by symbol, columns = strategy names.
- Consumes: `cache`, `data`, `engine`, `settings`.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_screener.py`:

```python
from features.screener import service as screener_service


def _seed_two_signals(db):
    screener_cache.upsert_signal(
        db, "AAA", "2026-01-03",
        {"ma_crossover": 0.9, "breakout": 0.1},
        {"ma_crossover": True, "breakout": False},
    )
    screener_cache.upsert_signal(
        db, "BBB", "2026-01-03",
        {"ma_crossover": 0.2, "breakout": 0.8},
        {"ma_crossover": False, "breakout": True},
    )


def test_scan_reads_cache_without_recomputing(db, monkeypatch):
    s = screener_settings.get_settings()
    s["data"]["cache_path"] = db
    monkeypatch.setattr(screener_service.settings, "get_settings", lambda: s)
    _seed_two_signals(db)

    calls = {"n": 0}
    real = compute.build_signals_row

    def spy(*a, **k):
        calls["n"] += 1
        return real(*a, **k)

    monkeypatch.setattr(compute, "build_signals_row", spy)

    out = screener_service.run_scan(strategies=["ma_crossover", "breakout"], k=1)
    assert calls["n"] == 0  # screen reads cached signals; no per-stock recompute
    assert {r["symbol"] for r in out["results"]} == {"AAA", "BBB"}


def test_scan_payload_is_json_serializable(db, monkeypatch):
    s = screener_settings.get_settings()
    s["data"]["cache_path"] = db
    monkeypatch.setattr(screener_service.settings, "get_settings", lambda: s)
    _seed_two_signals(db)
    out = screener_service.run_scan()
    json.dumps(out)  # must not raise


def test_status_reports_seed_state(db, monkeypatch):
    s = screener_settings.get_settings()
    s["data"]["cache_path"] = db
    monkeypatch.setattr(screener_service.settings, "get_settings", lambda: s)
    screener_cache.set_meta(db, "seed_complete", "1")
    status = screener_service.get_status()
    assert status["seed_complete"] is True
    json.dumps(status)
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && uv run pytest tests/test_screener.py -k "scan_reads or scan_payload or status_reports" -v`
Expected: FAIL — `ModuleNotFoundError` on `service`.

- [ ] **Step 3: Write `service.py`**

```python
"""Orchestration: screen reads (cache-only), status, and the Lock-guarded
background refresh triggered on login."""
from __future__ import annotations

import threading

import pandas as pd

from . import cache, data, engine, settings

_refresh_lock = threading.Lock()


def _cache_path() -> str:
    return settings.get_settings()["data"]["cache_path"]


def _read_signal_frames(path: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = cache.read_signals(path)
    scores = {r["symbol"]: r["scores"] for r in rows}
    passes = {r["symbol"]: r["passes"] for r in rows}
    scores_df = pd.DataFrame.from_dict(scores, orient="index")
    passes_df = pd.DataFrame.from_dict(passes, orient="index")
    return scores_df, passes_df


def get_strategies() -> dict:
    return {"strategies": engine.strategy_metadata(settings.get_settings())}


def get_individual(strategy: str) -> dict:
    scores, passes = _read_signal_frames(_cache_path())
    if scores.empty or strategy not in scores.columns:
        return {"strategy": strategy, "results": [], "last_updated": data.last_updated()}
    results = engine.run_individual(strategy, scores, passes)
    return {"strategy": strategy, "results": results, "last_updated": data.last_updated()}


def run_scan(strategies=None, weights=None, k=None, fallback_n=None) -> dict:
    conf = settings.get_settings()["screener"]
    selected = strategies or list(engine.REGISTRY)
    weights = weights or conf["weights"]
    k = conf["default_k"] if k is None else k
    fallback_n = conf["fallback_n"] if fallback_n is None else int(fallback_n)

    scores, passes = _read_signal_frames(_cache_path())
    if scores.empty:
        return {"results": [], "is_fallback": False, "selected": selected,
                "k": k, "last_updated": data.last_updated()}
    out = engine.run_combined(selected, weights, k, fallback_n, scores, passes)
    out["last_updated"] = data.last_updated()
    return out


def get_status() -> dict:
    path = _cache_path()
    return {
        "last_updated": cache.get_meta(path, "last_updated"),
        "seed_complete": cache.get_meta(path, "seed_complete") == "1",
        "symbol_count": cache.symbol_count(path),
        "refreshing": _refresh_lock.locked(),
    }


def _refresh_core() -> None:
    path = _cache_path()
    cache.init(path)
    if cache.get_meta(path, "seed_complete") == "1":
        data.refresh_ohlc()
    else:
        data.seed_history()


def _locked_refresh() -> None:
    try:
        _refresh_core()
    finally:
        _refresh_lock.release()


def screener_on_login() -> None:
    """Non-blocking. Skip if a refresh is already running (stacked logins)."""
    if not _refresh_lock.acquire(blocking=False):
        return
    threading.Thread(target=_locked_refresh, daemon=True).start()


def trigger_refresh() -> dict:
    screener_on_login()
    return get_status()
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && uv run pytest tests/test_screener.py -k "scan_reads or scan_payload or status_reports" -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/features/screener/service.py backend/tests/test_screener.py
git commit -m "feat(screener): service orchestration + background login refresh"
```

---

### Task 8: Routes + main.py wiring + auth login hook

**Files:**
- Create: `backend/features/screener/routes.py`
- Modify: `backend/main.py`
- Modify: `backend/features/auth/routes.py`
- Test: `backend/tests/test_screener.py`

**Interfaces:**
- Produces `router` with: `GET /strategies`, `GET /individual?strategy=`, `POST /scan`, `POST /refresh`, `GET /status`.
- Consumes `service.*`.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_screener.py`:

```python
def test_routes_module_exposes_all_endpoints():
    from features.screener import routes as screener_routes

    paths = {r.path for r in screener_routes.router.routes}
    assert paths == {"/strategies", "/individual", "/scan", "/refresh", "/status"}
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && uv run pytest tests/test_screener.py::test_routes_module_exposes_all_endpoints -v`
Expected: FAIL — `ModuleNotFoundError` on `routes`.

- [ ] **Step 3: Write `routes.py`**

```python
from fastapi import APIRouter, HTTPException, Request

from .service import (
    get_individual,
    get_status,
    get_strategies,
    run_scan,
    trigger_refresh,
)

router = APIRouter()


@router.get("/strategies")
def strategies():
    return get_strategies()


@router.get("/individual")
def individual(strategy: str):
    return get_individual(strategy)


@router.post("/scan")
async def scan(request: Request):
    body = await request.json() if await request.body() else {}
    return run_scan(
        strategies=body.get("strategies"),
        weights=body.get("weights"),
        k=body.get("k"),
        fallback_n=body.get("fallback_n"),
    )


@router.post("/refresh")
def refresh():
    try:
        return trigger_refresh()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
def status():
    return get_status()
```

- [ ] **Step 4: Wire the router in `main.py`**

Add the import next to the others (after line 7) and the include (after line 22):

```python
from features.screener.routes import router as screener_router
```
```python
app.include_router(screener_router, prefix="/api/screener")
```

- [ ] **Step 5: Hook the login refresh into `auth/routes.py`**

In `backend/features/auth/routes.py`, add the import and call `screener_on_login()` in `callback()` right after `set_access_token(...)`:

```python
from features.screener.service import screener_on_login
```

```python
        data = kite.generate_session(request_token, api_secret=API_SECRET)
        set_access_token(data["access_token"])
        screener_on_login()  # non-blocking background history/incremental refresh

        return RedirectResponse(f"{FRONTEND_URL}/")
```

- [ ] **Step 6: Run tests + import check**

Run: `cd backend && uv run pytest tests/test_screener.py -v && uv run python -c "import main"`
Expected: all screener tests PASS; `import main` prints nothing and exits 0 (router + auth hook import cleanly).

- [ ] **Step 7: Commit**

```bash
git add backend/features/screener/routes.py backend/main.py backend/features/auth/routes.py backend/tests/test_screener.py
git commit -m "feat(screener): routes, main.py wiring, login refresh hook"
```

---

### Task 9: Frontend service + nav + page shell wiring

**Files:**
- Create: `frontend/src/services/screenerService.js`
- Create: `frontend/src/features/screener/hooks/useScreener.js`
- Create: `frontend/src/features/screener/components/LastUpdated.jsx`
- Create: `frontend/src/features/screener/ScreenerPage.jsx`
- Modify: `frontend/src/constants/navigation.js`
- Modify: `frontend/src/app/App.jsx`

**Interfaces:**
- `screenerService.js` exports: `getStrategies()`, `getIndividual(strategy)`, `postScan(body)`, `postRefresh()`, `getStatus()`.
- `useScreener.js` exports: `useStrategies()`, `useScreenerStatus()` (both via `useAsyncData`).

- [ ] **Step 1: Write `screenerService.js`**

```javascript
import { apiClient } from "./apiClient";

export async function getStrategies() {
  const { data } = await apiClient.get("/screener/strategies");
  return data;
}

export async function getIndividual(strategy) {
  const { data } = await apiClient.get("/screener/individual", { params: { strategy } });
  return data;
}

export async function postScan(body) {
  const { data } = await apiClient.post("/screener/scan", body);
  return data;
}

export async function postRefresh() {
  const { data } = await apiClient.post("/screener/refresh");
  return data;
}

export async function getStatus() {
  const { data } = await apiClient.get("/screener/status");
  return data;
}
```

- [ ] **Step 2: Write `hooks/useScreener.js`**

```javascript
import { useCallback } from "react";
import { useAsyncData } from "../../../hooks/useAsyncData";
import { getStrategies, getStatus } from "../../../services/screenerService";

export function useStrategies() {
  return useAsyncData(useCallback(() => getStrategies(), []), {
    errorMessage: "Failed to load strategies",
  });
}

export function useScreenerStatus() {
  return useAsyncData(useCallback(() => getStatus(), []), {
    errorMessage: "Failed to load screener status",
  });
}
```

- [ ] **Step 3: Write `components/LastUpdated.jsx`**

```jsx
export default function LastUpdated({ status }) {
  const ts = status?.last_updated;
  const label = ts ? new Date(ts).toLocaleString() : "never";
  const seeding = status && !status.seed_complete;
  return (
    <div className="flex items-center gap-1.5">
      <span
        className={`h-1.5 w-1.5 rounded-full ${
          status?.refreshing ? "bg-[var(--color-warning)]" : "bg-[var(--color-profit)]"
        }`}
      />
      <span className="font-mono text-[0.5625rem] uppercase tracking-[0.14em] text-[var(--color-text-faint)]">
        {seeding ? "Seeding history…" : `Updated · ${label}`}
      </span>
    </div>
  );
}
```

- [ ] **Step 4: Write the `ScreenerPage.jsx` shell (tabs + last-updated; panels stubbed)**

```jsx
import { useState } from "react";
import PageShell from "../../components/layout/PageShell";
import { cn } from "../../utils/classNames";
import { useScreenerStatus } from "./hooks/useScreener";
import LastUpdated from "./components/LastUpdated";
import StrategiesPanel from "./components/StrategiesPanel";
import ScreenerPanel from "./components/ScreenerPanel";

const TABS = [
  { id: "strategies", label: "Strategies" },
  { id: "screener", label: "Screener" },
];

export default function ScreenerPage() {
  const [tab, setTab] = useState("strategies");
  const { data: status } = useScreenerStatus();

  return (
    <PageShell eyebrow="Signals" title="Stock Screener">
      <div className="flex flex-col gap-5">
        <div className="flex items-center justify-between">
          <div className="flex gap-1">
            {TABS.map((t) => (
              <button
                key={t.id}
                type="button"
                onClick={() => setTab(t.id)}
                className={cn(
                  "rounded-[var(--radius-sm)] border px-3 py-1.5 font-mono text-[0.625rem] uppercase tracking-[0.12em] transition",
                  tab === t.id
                    ? "border-[var(--color-accent)] bg-[var(--color-surface-soft)] text-[var(--color-text)]"
                    : "border-[var(--color-border)] text-[var(--color-text-muted)] hover:text-[var(--color-text)]",
                )}
              >
                {t.label}
              </button>
            ))}
          </div>
          <LastUpdated status={status} />
        </div>

        {tab === "strategies" ? <StrategiesPanel /> : <ScreenerPanel />}
      </div>
    </PageShell>
  );
}
```

- [ ] **Step 5: Add nav item in `constants/navigation.js`**

Append to `NAV_ITEMS`:

```javascript
  {
    id: "screener",
    label: "Screener",
    eyebrow: "Signals",
    description: "Multi-strategy NSE500 stock screener",
  },
```

- [ ] **Step 6: Register the page in `app/App.jsx`**

Add the lazy import next to the others and the `PAGES` entry:

```javascript
const ScreenerPage = lazy(() => import("../features/screener/ScreenerPage"));
```
```javascript
const PAGES = {
  overview: PortfolioOverviewPage,
  exit: ExitSignalsPage,
  fragility: FragilityPage,
  screener: ScreenerPage,
};
```

- [ ] **Step 7: Create placeholder panels so the build compiles**

Create `frontend/src/features/screener/components/StrategiesPanel.jsx` and `ScreenerPanel.jsx` each temporarily returning `export default function X() { return null; }` (fleshed out in Tasks 10–11). This keeps this task's deliverable independently buildable.

- [ ] **Step 8: Verify build + lint**

Run: `cd frontend && npm run build && npm run lint`
Expected: build succeeds; lint clean. The new "Screener" tab appears in the nav and renders the shell.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/services/screenerService.js frontend/src/features/screener frontend/src/constants/navigation.js frontend/src/app/App.jsx
git commit -m "feat(screener): frontend service, nav entry, page shell"
```

---

### Task 10: Frontend — Strategies panel (single-strategy raw ranking)

**Files:**
- Modify: `frontend/src/features/screener/components/StrategiesPanel.jsx`
- Test: manual via `npm run build`/`npm run dev`.

**Interfaces:**
- Consumes `useStrategies()`, `getIndividual(strategy)` from Task 9.

- [ ] **Step 1: Implement `StrategiesPanel.jsx`**

The table uses the codebase's composable primitives (`TableShell`/`TableHeader`/`TableRow` with a shared `GRID` template) — there is no `columns`/`rows` prop API. Pattern taken from `features/portfolio/components/ConcentrationTable.jsx`.

```jsx
import { useEffect, useState } from "react";
import Card from "../../../components/ui/Card";
import { TableHeader, TableRow, TableShell } from "../../../components/ui/DataTable";
import EmptyState from "../../../components/ui/EmptyState";
import { useStrategies } from "../hooks/useScreener";
import { getIndividual } from "../../../services/screenerService";

const GRID = "grid-cols-[0.5fr_2fr_1fr] gap-4 items-center";

export default function StrategiesPanel() {
  const { data: meta } = useStrategies();
  const strategies = meta?.strategies ?? [];
  const [selected, setSelected] = useState("");
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!selected && strategies.length) setSelected(strategies[0].name);
  }, [selected, strategies]);

  useEffect(() => {
    if (!selected) return;
    let cancelled = false;
    setLoading(true);
    getIndividual(selected)
      .then((res) => !cancelled && setResults(res.results ?? []))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [selected]);

  return (
    <Card className="p-4">
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <span className="label">Strategy</span>
        <select
          value={selected}
          onChange={(e) => setSelected(e.target.value)}
          className="rounded-[var(--radius-sm)] border border-[var(--color-border)] bg-[var(--color-surface-soft)] px-2 py-1 font-mono text-xs text-[var(--color-text)]"
        >
          {strategies.map((s) => (
            <option key={s.name} value={s.name}>
              {s.name}
            </option>
          ))}
        </select>
      </div>

      {loading ? (
        <p className="label">Loading…</p>
      ) : results.length === 0 ? (
        <EmptyState title="No passing stocks" description="No symbols pass this strategy yet." />
      ) : (
        <TableShell title={`Passing · ${selected}`}>
          <TableHeader className={GRID}>
            <div>#</div>
            <div>Symbol</div>
            <div className="text-right">Raw score</div>
          </TableHeader>
          {results.map((row, i) => (
            <TableRow key={row.symbol} className={GRID}>
              <div className="font-mono text-[var(--color-text-muted)]">{i + 1}</div>
              <div className="font-medium text-[var(--color-text)]">{row.symbol}</div>
              <div className="text-right font-mono tabular-nums">{row.score}</div>
            </TableRow>
          ))}
        </TableShell>
      )}
    </Card>
  );
}
```

- [ ] **Step 2: Verify build + lint + visual**

Run: `cd frontend && npm run build && npm run lint`
Then `npm run dev`, open the Screener → Strategies tab, pick a strategy, confirm the raw-ranked table renders (after a login has seeded data).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/features/screener/components/StrategiesPanel.jsx
git commit -m "feat(screener): Strategies panel with raw-score ranking"
```

---

### Task 11: Frontend — Screener panel (multi-strategy weighted + fallback badge)

**Files:**
- Modify: `frontend/src/features/screener/components/ScreenerPanel.jsx`

**Interfaces:**
- Consumes `useStrategies()`, `postScan(body)` from Task 9.

- [ ] **Step 1: Implement `ScreenerPanel.jsx`**

Results use the same `TableShell`/`TableHeader`/`TableRow` primitives as Task 10 (no `columns`/`rows` prop API).

```jsx
import { useEffect, useState } from "react";
import Card from "../../../components/ui/Card";
import { TableHeader, TableRow, TableShell } from "../../../components/ui/DataTable";
import EmptyState from "../../../components/ui/EmptyState";
import { useStrategies } from "../hooks/useScreener";
import { postScan } from "../../../services/screenerService";

const RESULT_GRID = "grid-cols-[0.5fr_2fr_1fr_1fr] gap-4 items-center";

export default function ScreenerPanel() {
  const { data: meta } = useStrategies();
  const strategies = meta?.strategies ?? [];
  const [selected, setSelected] = useState({});
  const [weights, setWeights] = useState({});
  const [k, setK] = useState("all");
  const [fallbackN, setFallbackN] = useState(10);
  const [scan, setScan] = useState(null);
  const [loading, setLoading] = useState(false);

  // Pre-fill equal weights + all strategies selected once metadata loads.
  useEffect(() => {
    if (strategies.length && Object.keys(selected).length === 0) {
      const all = Object.fromEntries(strategies.map((s) => [s.name, true]));
      const eq = Object.fromEntries(strategies.map((s) => [s.name, 1]));
      setSelected(all);
      setWeights(eq);
    }
  }, [strategies, selected]);

  const chosen = strategies.filter((s) => selected[s.name]).map((s) => s.name);

  async function runScan() {
    setLoading(true);
    try {
      const body = {
        strategies: chosen,
        weights: Object.fromEntries(chosen.map((n) => [n, Number(weights[n]) || 1])),
        k: k === "all" ? "all" : Number(k),
        fallback_n: Number(fallbackN) || 10,
      };
      setScan(await postScan(body));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <Card className="p-4">
        <h2 className="label mb-3">Configure screen</h2>
        <div className="flex flex-col gap-2">
          {strategies.map((s) => (
            <div key={s.name} className="flex items-center gap-3">
              <label className="flex w-48 items-center gap-2 font-mono text-xs text-[var(--color-text)]">
                <input
                  type="checkbox"
                  checked={!!selected[s.name]}
                  onChange={(e) => setSelected({ ...selected, [s.name]: e.target.checked })}
                />
                {s.name}
              </label>
              <input
                type="number"
                step="0.1"
                value={weights[s.name] ?? 1}
                onChange={(e) => setWeights({ ...weights, [s.name]: e.target.value })}
                disabled={!selected[s.name]}
                className="w-20 rounded-[var(--radius-sm)] border border-[var(--color-border)] bg-[var(--color-surface-soft)] px-2 py-1 font-mono text-xs disabled:opacity-40"
              />
            </div>
          ))}
        </div>

        <div className="mt-4 flex flex-wrap items-end gap-4">
          <label className="flex flex-col gap-1">
            <span className="label">K (matches required)</span>
            <select
              value={k}
              onChange={(e) => setK(e.target.value)}
              className="rounded-[var(--radius-sm)] border border-[var(--color-border)] bg-[var(--color-surface-soft)] px-2 py-1 font-mono text-xs"
            >
              <option value="all">all (AND)</option>
              {chosen.map((_, i) => (
                <option key={i + 1} value={i + 1}>{i + 1}</option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1">
            <span className="label">Fallback N</span>
            <input
              type="number"
              value={fallbackN}
              onChange={(e) => setFallbackN(e.target.value)}
              className="w-20 rounded-[var(--radius-sm)] border border-[var(--color-border)] bg-[var(--color-surface-soft)] px-2 py-1 font-mono text-xs"
            />
          </label>
          <button
            type="button"
            onClick={runScan}
            disabled={loading || chosen.length === 0}
            className="rounded-[var(--radius-sm)] border border-[var(--color-accent)] bg-[var(--color-surface-soft)] px-4 py-1.5 font-mono text-xs uppercase tracking-[0.1em] text-[var(--color-text)] disabled:opacity-40"
          >
            {loading ? "Scanning…" : "Run screen"}
          </button>
        </div>
      </Card>

      {scan && (
        <Card className="p-4">
          <div className="mb-3 flex items-center gap-3">
            <h2 className="label">Results</h2>
            {scan.is_fallback && (
              <span className="rounded-[var(--radius-sm)] bg-[var(--color-warning)]/15 px-2 py-0.5 font-mono text-[0.625rem] uppercase tracking-[0.1em] text-[var(--color-warning)]">
                Fallback · no true matches — showing top {scan.results.length} by aggregate
              </span>
            )}
          </div>
          {scan.results.length === 0 ? (
            <EmptyState title="No results" description="Refresh data or loosen K." />
          ) : (
            <TableShell>
              <TableHeader className={RESULT_GRID}>
                <div>#</div>
                <div>Symbol</div>
                <div className="text-right">Aggregate</div>
                <div className="text-right">Passes</div>
              </TableHeader>
              {scan.results.map((row, i) => (
                <TableRow key={row.symbol} className={RESULT_GRID}>
                  <div className="font-mono text-[var(--color-text-muted)]">{i + 1}</div>
                  <div className="font-medium text-[var(--color-text)]">{row.symbol}</div>
                  <div className="text-right font-mono tabular-nums">{row.aggregate}</div>
                  <div className="text-right font-mono tabular-nums">{row.passes}</div>
                </TableRow>
              ))}
            </TableShell>
          )}
        </Card>
      )}
    </div>
  );
}
```

Note: `--color-warning` is a raw CSS variable, so the `bg-[var(--color-warning)]/15` opacity shorthand may not apply an alpha under Tailwind v4. If the tint doesn't render, use an inline `style={{ backgroundColor: "color-mix(in srgb, var(--color-warning) 15%, transparent)" }}` on the badge instead.

- [ ] **Step 2: Verify build + lint + visual**

Run: `cd frontend && npm run build && npm run lint`
Then `npm run dev`: select strategies, set weights/K/fallback, Run screen; confirm ranked table and the fallback badge appears when K yields no matches.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/features/screener/components/ScreenerPanel.jsx
git commit -m "feat(screener): Screener panel with weighted K-of-N + fallback badge"
```

---

### Task 12: Full verification + CLAUDE.md docs

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Run the full backend suite**

Run: `cd backend && uv run pytest -v`
Expected: all screener tests + the existing diversity-engine tests PASS.

- [ ] **Step 2: Full frontend build + lint**

Run: `cd frontend && npm run build && npm run lint`
Expected: both clean.

- [ ] **Step 3: Manual smoke test of the login refresh**

Start backend `uv run uvicorn main:app --reload`, log in via `/api/auth/login`. Confirm: the UI is usable immediately; `GET /api/screener/status` shows `seed_complete` flipping to true and `last_updated` advancing; a second login triggers only an incremental refresh; `POST /api/screener/scan` returns without any Kite call.

- [ ] **Step 4: Update `CLAUDE.md`**

Under the feature-areas list add a **Screener** bullet, and add a backend section documenting: `features/screener/` layout incl. `cache.py`, the three-layer cache model, the login-triggered background refresh (`screener_on_login()` hooked in `auth/routes.py`), and that `screener_cache.db` + `data/nse500.csv` are new artifacts (the NSE500 file is a manual quarterly drop-in). Note `/api/screener` routes.

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md
git commit -m "docs(screener): document screener feature + cache model in CLAUDE.md"
```

---

## Self-Review

**1. Spec coverage:**
- Settings idiom + all config keys → Task 1. ✓
- Three-layer cache (history/incremental/signals) → Tasks 2, 6. ✓
- Skip-and-log missing symbols → Task 6 (`test_refresh_skips_and_logs_missing_symbol`). ✓
- 5 strategies score+pass → Task 3. ✓
- normalize/aggregate/k-of-n/fallback/build_signals_row → Task 4. ✓
- Strategy ABC + registry + run_individual/run_combined → Task 5. ✓
- Universe filter behind one function → Task 6 (`_passes_liquidity_filter`). ✓
- Login background non-blocking refresh + manual endpoint + last_updated → Task 7, 8. ✓
- 5 routes, cache-only screens → Task 8; "no recompute at screen" → Task 7 (`test_scan_reads_cache_without_recomputing`). ✓
- Two frontend pages + last-updated + fallback badge, no touching other features → Tasks 9–11. ✓
- All spec tests → Tasks 1–8 (JSON-serializable → Task 7; incremental-append → Task 6; equal-weight==mean → Task 4; k semantics → Task 4; fallback exactly N → Task 4/5). ✓

**2. Placeholder scan:** Panels are intentionally stubbed in Task 9 then implemented in Tasks 10–11 (noted, not a placeholder). Two "confirm DataTable API" / "confirm Tailwind opacity" notes are real verification instructions, not deferred code. No TBD/TODO in shipped code.

**3. Type consistency:** `build_signals_row(df, strategies)` signature consistent across Task 4 (def), Task 6 (`_recompute_signal` call). `run_combined(selected, weights, k, fallback_n, scores, passes)` consistent Task 5 (def) ↔ Task 7 (call). Signal frame shape (`scores`/`passes` DataFrames indexed by symbol, columns = strategy names) consistent Task 5 ↔ Task 7. `_run(...)` returns `{"seeded"|"updated", "skipped"}` — service ignores the varying key, tests assert the right one. Cache function signatures consistent Task 2 ↔ Tasks 6–7.
