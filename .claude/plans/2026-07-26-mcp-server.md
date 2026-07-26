# Read-Only MCP Server Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose the existing Kite portfolio analytics to an AI assistant via a read-only FastMCP v3 server mounted into the running FastAPI process.

**Architecture:** A new `features/mcp/` package holds one tool module per feature area. Each module defines plain, importable functions and a `register(mcp)` that attaches them via `mcp.tool(fn)`. `server.py` builds one `FastMCP`, registers all modules, and exposes `mcp_app = mcp.http_app(path="/")`, which `main.py` mounts at `/mcp` with its lifespan attached. Tools import the service layer directly (no HTTP self-calls). Kite-touching tools are wrapped by a `@needs_kite` guard that returns a login-URL payload instead of throwing on a missing/expired token. The Kite token is persisted in `core/kite.py` so a same-day restart doesn't force re-auth.

**Tech Stack:** Python ≥3.12, FastAPI, FastMCP v3.2.x, kiteconnect, pytest, uv.

## Global Constraints

Every task's requirements implicitly include this section.

- **Dependency management is `uv`** — add deps with `uv add <pkg>` (updates `pyproject.toml` + `uv.lock`); never `pip`. There is no `requirements.txt`.
- **Run everything from `backend/`** and prefix with `uv run` — e.g. `uv run pytest`, `uv run uvicorn main:app --reload`. `settings.db` / `screener_cache.db` paths are relative to `backend/`.
- **Python floor ≥3.12**, FastMCP pinned to **v3.2.x**.
- **Read-only. No order flow of any kind** (live or paper), no intraday, no new analytics.
- **Tools import the service layer directly** — no `httpx`/requests back into our own API.
- **Coarse-grained, compact, pre-rounded output.** Never `FastMCP.from_fastapi()`. Screener returns top-N + `total_matches`, never the full universe dump. No raw covariance/correlation matrices.
- **One tool module per feature area**, mirroring the backend feature it wraps.
- **Mount via `http_app()` + attach `mcp_app.lifespan`** to the FastAPI app. CORS unchanged. Existing REST endpoints and the React frontend must behave exactly as before.
- **Every commit message ends with the trailer** (shown once in Task 1; repeat it on every commit):
  `-m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"`
- Suggested branch: `feat/mcp-server` (created at execution time via the worktree skill).

---

### Task 1: Persist & restore the Kite token in `core/kite.py`

**Files:**
- Modify: `backend/core/kite.py`
- Test: `backend/tests/test_kite_session.py`

**Interfaces:**
- Consumes: `core.settings_store.load_settings`, `core.settings_store.save_settings`.
- Produces: `set_access_token(token: str)` (now also persists), `_persist_token(token: str) -> None`, `_load_persisted_token() -> None`, `_today_ist() -> str`. Table name `kite_session`. Existing `is_authenticated() -> bool` and `get_kite() -> KiteConnect` unchanged.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_kite_session.py`:

```python
import core.kite as kite_mod
import core.settings_store as store


def _use_tmp_db(monkeypatch, tmp_path):
    monkeypatch.setattr(store, "DB_PATH", str(tmp_path / "settings.db"))


def test_set_access_token_persists_row(monkeypatch, tmp_path):
    _use_tmp_db(monkeypatch, tmp_path)
    monkeypatch.setattr(kite_mod.kite, "set_access_token", lambda t: None)

    kite_mod.set_access_token("tok-123")

    saved = store.load_settings("kite_session", {})
    assert saved["access_token"] == "tok-123"
    assert saved["ist_date"] == kite_mod._today_ist()


def test_load_restores_same_day_token(monkeypatch, tmp_path):
    _use_tmp_db(monkeypatch, tmp_path)
    monkeypatch.setattr(kite_mod.kite, "set_access_token", lambda t: None)
    store.save_settings("kite_session", {"access_token": "tok-abc", "ist_date": kite_mod._today_ist()})

    kite_mod._access_token = None
    kite_mod._load_persisted_token()

    assert kite_mod._access_token == "tok-abc"
    assert kite_mod.is_authenticated() is True


def test_load_ignores_stale_token(monkeypatch, tmp_path):
    _use_tmp_db(monkeypatch, tmp_path)
    monkeypatch.setattr(kite_mod.kite, "set_access_token", lambda t: None)
    store.save_settings("kite_session", {"access_token": "tok-old", "ist_date": "1999-01-01"})

    kite_mod._access_token = None
    kite_mod._load_persisted_token()

    assert kite_mod._access_token is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_kite_session.py -v`
Expected: FAIL with `AttributeError: module 'core.kite' has no attribute '_today_ist'` (and `_load_persisted_token`).

- [ ] **Step 3: Implement persistence in `core/kite.py`**

Replace the whole file with:

```python
from datetime import datetime, timedelta, timezone

from kiteconnect import KiteConnect

from config import API_KEY
from core.settings_store import load_settings, save_settings

kite = KiteConnect(api_key=API_KEY)

_access_token = None

_IST = timezone(timedelta(hours=5, minutes=30))
_SESSION_TABLE = "kite_session"


def _today_ist() -> str:
    return datetime.now(_IST).date().isoformat()


def _persist_token(token: str) -> None:
    # Best-effort: a broken/missing settings.db must never break auth.
    try:
        save_settings(_SESSION_TABLE, {"access_token": token, "ist_date": _today_ist()})
    except Exception:
        pass


def _load_persisted_token() -> None:
    # Restore only a same-IST-day token; Kite tokens die ~06:00 IST daily, so a
    # prior-day token is dead and must be ignored, not reused.
    global _access_token
    try:
        data = load_settings(_SESSION_TABLE, {})
        if data.get("access_token") and data.get("ist_date") == _today_ist():
            _access_token = data["access_token"]
            kite.set_access_token(_access_token)
    except Exception:
        pass


def set_access_token(token: str):
    global _access_token
    _access_token = token
    kite.set_access_token(token)
    _persist_token(token)


def is_authenticated():
    return _access_token is not None


def get_kite():
    if not _access_token:
        raise Exception("Not authenticated")
    return kite


# Restore a same-day token on startup so a mid-day server restart isn't a re-login.
_load_persisted_token()
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_kite_session.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/core/kite.py backend/tests/test_kite_session.py
git commit -m "feat(kite): persist and restore the access token for same-day restarts" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Extract `complete_login()` into an auth service

**Files:**
- Create: `backend/features/auth/service.py`
- Create (if missing): `backend/features/auth/__init__.py`
- Modify: `backend/features/auth/routes.py`
- Test: `backend/tests/test_auth_service.py`

**Interfaces:**
- Consumes: `core.kite.kite`, `core.kite.set_access_token` (Task 1), `config.API_SECRET`, `features.screener.service.screener_on_login`.
- Produces: `complete_login(request_token: str) -> dict` returning `{"user_id": str | None, "access_token": str}`.

- [ ] **Step 1: Confirm the auth package init exists**

Run: `ls backend/features/auth/`
If `__init__.py` is absent, create an empty `backend/features/auth/__init__.py`.

- [ ] **Step 2: Write the failing test**

Create `backend/tests/test_auth_service.py`:

```python
import features.auth.service as auth_service


def test_complete_login_sets_token_and_refreshes(monkeypatch):
    calls = {}
    monkeypatch.setattr(
        auth_service.kite, "generate_session",
        lambda rt, api_secret: {"access_token": "tok-xyz", "user_id": "AB1234"},
    )
    monkeypatch.setattr(auth_service, "set_access_token", lambda t: calls.setdefault("token", t))
    monkeypatch.setattr(auth_service, "screener_on_login", lambda: calls.setdefault("refresh", True))

    result = auth_service.complete_login("req-token")

    assert calls["token"] == "tok-xyz"
    assert calls["refresh"] is True
    assert result["user_id"] == "AB1234"
    assert result["access_token"] == "tok-xyz"
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `uv run pytest tests/test_auth_service.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'features.auth.service'`.

- [ ] **Step 4: Implement `features/auth/service.py`**

```python
from core.kite import kite, set_access_token
from config import API_SECRET
from features.screener.service import screener_on_login


def complete_login(request_token: str) -> dict:
    """Single source of truth for turning a request_token into a live session.

    Shared by the REST /callback route and the MCP kite_complete_login tool:
    generate session -> set (and persist) token -> kick the screener refresh.
    """
    data = kite.generate_session(request_token, api_secret=API_SECRET)
    set_access_token(data["access_token"])
    screener_on_login()
    return {"user_id": data.get("user_id"), "access_token": data["access_token"]}
```

- [ ] **Step 5: Refactor `features/auth/routes.py` to use it**

Replace the file with:

```python
from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse

from core.kite import kite, is_authenticated
from config import FRONTEND_URL
from .service import complete_login

router = APIRouter()


@router.get("/status")
def status():
    return {"authenticated": is_authenticated()}


@router.get("/login")
def login():
    return RedirectResponse(kite.login_url())


@router.get("/callback")
def callback(request_token: str):
    try:
        complete_login(request_token)
        return RedirectResponse(f"{FRONTEND_URL}/")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/test_auth_service.py -v`
Expected: PASS (1 passed).

- [ ] **Step 7: Commit**

```bash
git add backend/features/auth/
git add backend/tests/test_auth_service.py
git commit -m "refactor(auth): extract complete_login() into a shared service" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: `features/mcp/` package + `@needs_kite` guard

**Files:**
- Create: `backend/features/mcp/__init__.py` (empty)
- Create: `backend/features/mcp/guards.py`
- Test: `backend/tests/test_mcp_tools.py`

**Interfaces:**
- Consumes: `core.kite.is_authenticated`, `core.kite.kite` (for `login_url()`), `kiteconnect.exceptions.TokenException`.
- Produces: `needs_kite(fn)` decorator; `login_payload() -> dict` returning `{"login_url": str, "message": str}`; `auth_required() -> dict` returning `{"status": "auth_required", **login_payload()}`.

- [ ] **Step 1: Create the empty package init**

Create `backend/features/mcp/__init__.py` (empty file).

- [ ] **Step 2: Write the failing tests**

Create `backend/tests/test_mcp_tools.py`:

```python
from kiteconnect.exceptions import TokenException

import features.mcp.guards as guards


def _fake_login_url(monkeypatch):
    monkeypatch.setattr(guards.kite, "login_url", lambda: "http://login-url")


def test_needs_kite_passes_through_when_authenticated(monkeypatch):
    _fake_login_url(monkeypatch)
    monkeypatch.setattr(guards, "is_authenticated", lambda: True)

    @guards.needs_kite
    def tool():
        return {"ok": True}

    assert tool() == {"ok": True}


def test_needs_kite_blocks_when_unauthenticated(monkeypatch):
    _fake_login_url(monkeypatch)
    monkeypatch.setattr(guards, "is_authenticated", lambda: False)

    @guards.needs_kite
    def tool():
        raise AssertionError("must not run")

    out = tool()
    assert out["status"] == "auth_required"
    assert out["login_url"] == "http://login-url"


def test_needs_kite_catches_token_exception(monkeypatch):
    _fake_login_url(monkeypatch)
    monkeypatch.setattr(guards, "is_authenticated", lambda: True)

    @guards.needs_kite
    def tool():
        raise TokenException("Token is invalid or has expired.")

    out = tool()
    assert out["status"] == "auth_required"
    assert "login_url" in out
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run pytest tests/test_mcp_tools.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'features.mcp.guards'`.

- [ ] **Step 4: Implement `features/mcp/guards.py`**

```python
"""Shared MCP tool helpers: the fail-loud Kite auth guard and its payloads."""
from __future__ import annotations

import functools

from kiteconnect.exceptions import TokenException

from core.kite import is_authenticated, kite


def login_payload() -> dict:
    return {
        "login_url": kite.login_url(),
        "message": (
            "Kite token missing or expired. Open login_url, authorize, then call "
            "kite_complete_login(request_token) with the request_token from the redirect."
        ),
    }


def auth_required() -> dict:
    return {"status": "auth_required", **login_payload()}


def needs_kite(fn):
    """Wrap a tool that touches Kite so a missing/expired token returns a
    login-URL payload instead of raising an opaque exception to the client."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        if not is_authenticated():
            return auth_required()
        try:
            return fn(*args, **kwargs)
        except TokenException:
            return auth_required()

    return wrapper
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_mcp_tools.py -v`
Expected: PASS (3 passed).

- [ ] **Step 6: Commit**

```bash
git add backend/features/mcp/__init__.py backend/features/mcp/guards.py backend/tests/test_mcp_tools.py
git commit -m "feat(mcp): add package and fail-loud @needs_kite auth guard" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: `portfolio_tools.py` — `portfolio_holdings()`

**Files:**
- Create: `backend/features/mcp/portfolio_tools.py`
- Test: append to `backend/tests/test_mcp_tools.py`

**Interfaces:**
- Consumes: `features.portfolio.data.get_holdings` (returns a DataFrame with `tradingsymbol, quantity, average_price, last_price`), `features.mcp.guards.needs_kite`.
- Produces: `portfolio_holdings() -> dict` = `{"holdings": [{symbol, qty, avg_price, ltp, value, pnl, pnl_pct}], "totals": {value, invested, pnl, pnl_pct, num_holdings}}`; `register(mcp) -> None`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_mcp_tools.py`:

```python
import pandas as pd

import features.mcp.portfolio_tools as portfolio_tools


def test_portfolio_holdings_formats_rows_and_totals(monkeypatch):
    monkeypatch.setattr(guards, "is_authenticated", lambda: True)
    df = pd.DataFrame([
        {"tradingsymbol": "INFY", "quantity": 10, "average_price": 100.0, "last_price": 150.0},
        {"tradingsymbol": "TCS", "quantity": 5, "average_price": 200.0, "last_price": 180.0},
    ])
    monkeypatch.setattr(portfolio_tools, "get_holdings", lambda: df)

    out = portfolio_tools.portfolio_holdings()

    # Sorted by value desc: INFY (1500) before TCS (900)
    assert [h["symbol"] for h in out["holdings"]] == ["INFY", "TCS"]
    infy = out["holdings"][0]
    assert infy["value"] == 1500.0
    assert infy["pnl"] == 500.0
    assert infy["pnl_pct"] == 50.0
    assert out["totals"]["value"] == 2400.0
    assert out["totals"]["invested"] == 2000.0
    assert out["totals"]["pnl"] == 400.0
    assert out["totals"]["num_holdings"] == 2
    # No raw instrument tokens leak
    assert "instrument_token" not in infy


def test_portfolio_holdings_empty(monkeypatch):
    monkeypatch.setattr(guards, "is_authenticated", lambda: True)
    monkeypatch.setattr(portfolio_tools, "get_holdings", lambda: pd.DataFrame())

    out = portfolio_tools.portfolio_holdings()
    assert out["holdings"] == []
    assert out["totals"]["num_holdings"] == 0
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_mcp_tools.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'features.mcp.portfolio_tools'`.

- [ ] **Step 3: Implement `features/mcp/portfolio_tools.py`**

```python
"""MCP tool: live holdings, formatted and rounded."""
from __future__ import annotations

from features.portfolio.data import get_holdings

from .guards import needs_kite


def _empty_totals() -> dict:
    return {"value": 0.0, "invested": 0.0, "pnl": 0.0, "pnl_pct": 0.0, "num_holdings": 0}


@needs_kite
def portfolio_holdings() -> dict:
    """Current live holdings with per-position P&L, plus portfolio totals.

    Returns rows sorted by market value (largest first). Amounts are rounded;
    instrument tokens and raw broker fields are omitted for a compact payload.
    """
    df = get_holdings()
    if df is None or df.empty:
        return {"holdings": [], "totals": _empty_totals()}

    rows = []
    for _, r in df.iterrows():
        qty = float(r["quantity"])
        avg = float(r["average_price"])
        ltp = float(r["last_price"])
        value = ltp * qty
        invested = avg * qty
        pnl = value - invested
        rows.append({
            "symbol": str(r["tradingsymbol"]),
            "qty": qty,
            "avg_price": round(avg, 2),
            "ltp": round(ltp, 2),
            "value": round(value, 2),
            "pnl": round(pnl, 2),
            "pnl_pct": round((pnl / invested * 100) if invested else 0.0, 2),
        })

    rows.sort(key=lambda h: h["value"], reverse=True)
    total_value = sum(h["value"] for h in rows)
    total_invested = sum(h["avg_price"] * h["qty"] for h in rows)
    total_pnl = total_value - total_invested
    return {
        "holdings": rows,
        "totals": {
            "value": round(total_value, 2),
            "invested": round(total_invested, 2),
            "pnl": round(total_pnl, 2),
            "pnl_pct": round((total_pnl / total_invested * 100) if total_invested else 0.0, 2),
            "num_holdings": len(rows),
        },
    }


def register(mcp) -> None:
    mcp.tool(portfolio_holdings)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_mcp_tools.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/features/mcp/portfolio_tools.py backend/tests/test_mcp_tools.py
git commit -m "feat(mcp): add portfolio_holdings tool" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: `fragility_tools.py` — `portfolio_metrics()`

**Files:**
- Create: `backend/features/mcp/fragility_tools.py`
- Test: append to `backend/tests/test_mcp_tools.py`

**Interfaces:**
- Consumes: `features.fragility.service.get_diversity_analysis` (returns the `to_dict()` shape: `{"scalars": {...}, "max_correlation_pair", "principal_bets", "correlation": {"symbols", "matrix"}, "tickers_excluded"}`), `features.mcp.guards.needs_kite`.
- Produces: `portfolio_metrics() -> dict` (compact 5-metric summary, no matrix); `register(mcp) -> None`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_mcp_tools.py`:

```python
import features.mcp.fragility_tools as fragility_tools


_FULL_ANALYSIS = {
    "scalars": {
        "num_positions": 8,
        "diversification_ratio": 1.42,
        "enb": 3.1,
        "effective_positions": 5.4,
        "normalized_entropy": 0.81,
        "weight_entropy": 1.68,
        "concentration_gap": 1.74,
        "portfolio_vol": 0.184,
        "portfolio_vol_daily": 0.0116,
        "portfolio_variance": 0.000134,
        "avg_correlation": 0.36,
        "max_correlation": 0.72,
    },
    "max_correlation_pair": ["INFY", "TCS"],
    "principal_risk_contributions": [0.4, 0.2],
    "principal_bets": [[{"symbol": "INFY", "loading": 0.7, "weight": 0.49}]],
    "correlation": {"symbols": ["INFY", "TCS"], "matrix": [[1.0, 0.72], [0.72, 1.0]]},
    "tickers_excluded": ["NEWSTOCK"],
}


def test_portfolio_metrics_is_compact(monkeypatch):
    monkeypatch.setattr(guards, "is_authenticated", lambda: True)
    monkeypatch.setattr(fragility_tools, "get_diversity_analysis", lambda: _FULL_ANALYSIS)

    out = fragility_tools.portfolio_metrics()

    assert out["num_positions"] == 8
    assert out["diversification_ratio"] == 1.42
    assert out["enb"] == 3.1
    assert out["max_correlation_pair"] == ["INFY", "TCS"]
    assert out["top_principal_bet"] == [{"symbol": "INFY", "loading": 0.7, "weight": 0.49}]
    assert out["tickers_excluded"] == ["NEWSTOCK"]
    # The raw matrix must NOT be in the payload
    assert "correlation" not in out
    assert "matrix" not in out


def test_portfolio_metrics_empty(monkeypatch):
    monkeypatch.setattr(guards, "is_authenticated", lambda: True)
    empty = {"scalars": {"num_positions": 0}, "tickers_excluded": []}
    monkeypatch.setattr(fragility_tools, "get_diversity_analysis", lambda: empty)

    out = fragility_tools.portfolio_metrics()
    assert out["num_positions"] == 0
    assert "note" in out
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_mcp_tools.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'features.mcp.fragility_tools'`.

- [ ] **Step 3: Implement `features/mcp/fragility_tools.py`**

```python
"""MCP tool: the five-metric diversification suite as a compact summary."""
from __future__ import annotations

from features.fragility.service import get_diversity_analysis

from .guards import needs_kite


@needs_kite
def portfolio_metrics() -> dict:
    """Descriptive diversification metrics for the current portfolio.

    Compact summary of the five-metric suite (diversification ratio, effective
    number of bets, weight entropy, correlation structure, concentration gap).
    Raw covariance/correlation matrices are intentionally omitted.
    """
    full = get_diversity_analysis()
    s = full.get("scalars", {})

    if int(s.get("num_positions", 0)) == 0:
        return {
            "num_positions": 0,
            "note": "Insufficient holdings or price history to compute diversification metrics.",
            "tickers_excluded": full.get("tickers_excluded", []),
        }

    bets = full.get("principal_bets") or []
    return {
        "num_positions": s["num_positions"],
        "diversification_ratio": s["diversification_ratio"],
        "enb": s["enb"],
        "effective_positions": s["effective_positions"],
        "normalized_entropy": s["normalized_entropy"],
        "weight_entropy": s["weight_entropy"],
        "concentration_gap": s["concentration_gap"],
        "portfolio_vol_annualized": s["portfolio_vol"],
        "avg_correlation": s["avg_correlation"],
        "max_correlation": s["max_correlation"],
        "max_correlation_pair": full.get("max_correlation_pair"),
        "top_principal_bet": bets[0] if bets else [],
        "tickers_excluded": full.get("tickers_excluded", []),
    }


def register(mcp) -> None:
    mcp.tool(portfolio_metrics)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_mcp_tools.py -v`
Expected: PASS (7 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/features/mcp/fragility_tools.py backend/tests/test_mcp_tools.py
git commit -m "feat(mcp): add portfolio_metrics tool" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: `screener_tools.py` — `screen_strategy()`

**Files:**
- Create: `backend/features/mcp/screener_tools.py`
- Test: append to `backend/tests/test_mcp_tools.py`

**Interfaces:**
- Consumes: `features.screener.service.get_individual` (returns `{"strategy", "results": [{"symbol", "score"}], "last_updated"}`), `features.screener.engine.REGISTRY` (dict keyed by strategy name).
- Produces: `screen_strategy(name: str, universe: str = "NSE500", limit: int = 20) -> dict`; `register(mcp) -> None`. Not guarded (cache-only).

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_mcp_tools.py`:

```python
import features.mcp.screener_tools as screener_tools


def test_screen_strategy_top_n_and_total(monkeypatch):
    results = [{"symbol": f"S{i}", "score": float(50 - i)} for i in range(30)]
    monkeypatch.setattr(
        screener_tools, "get_individual",
        lambda name: {"strategy": name, "results": results, "last_updated": "2026-07-25T18:00:00"},
    )

    out = screener_tools.screen_strategy("momentum_12_1", limit=5)
    assert out["total_matches"] == 30
    assert len(out["top"]) == 5
    assert out["top"][0]["symbol"] == "S0"
    assert out["strategy"] == "momentum_12_1"
    assert out["universe"] == "NSE500"
    assert out["last_updated"] == "2026-07-25T18:00:00"


def test_screen_strategy_unknown_name():
    out = screener_tools.screen_strategy("not_a_strategy")
    assert "error" in out
    assert "ma_crossover" in out["valid_strategies"]


def test_screen_strategy_unsupported_universe():
    out = screener_tools.screen_strategy("breakout", universe="SP500")
    assert "error" in out
    assert out["supported_universes"] == ["NSE500"]


def test_screen_strategy_empty_cache(monkeypatch):
    monkeypatch.setattr(
        screener_tools, "get_individual",
        lambda name: {"strategy": name, "results": [], "last_updated": None},
    )
    out = screener_tools.screen_strategy("breakout")
    assert out["total_matches"] == 0
    assert "note" in out
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_mcp_tools.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'features.mcp.screener_tools'`.

- [ ] **Step 3: Implement `features/mcp/screener_tools.py`**

```python
"""MCP tool: run one screener strategy, cache-only, top-N + total_matches."""
from __future__ import annotations

from features.screener.engine import REGISTRY
from features.screener.service import get_individual

_SUPPORTED_UNIVERSES = ["NSE500"]


def screen_strategy(name: str, universe: str = "NSE500", limit: int = 20) -> dict:
    """Run a single technical screening strategy over the cached NSE500 universe.

    Reads only the screener cache (no live market calls). Returns the top-`limit`
    passing symbols ranked by raw score, plus the full `total_matches` count.
    Valid `name` values: ma_crossover, momentum_12_1, breakout, rsi_reversion,
    high_52w. Only the NSE500 universe is supported.
    """
    if name not in REGISTRY:
        return {"error": f"Unknown strategy: {name!r}", "valid_strategies": list(REGISTRY)}
    if universe not in _SUPPORTED_UNIVERSES:
        return {"error": f"Unsupported universe: {universe!r}", "supported_universes": _SUPPORTED_UNIVERSES}

    data = get_individual(name)
    results = data.get("results", [])
    out = {
        "strategy": name,
        "universe": universe,
        "total_matches": len(results),
        "top": results[: max(0, int(limit))],
        "last_updated": data.get("last_updated"),
    }
    if not results:
        out["note"] = "No matches in cache. The screener cache may be unseeded — log in to trigger a refresh."
    return out


def register(mcp) -> None:
    mcp.tool(screen_strategy)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_mcp_tools.py -v`
Expected: PASS (11 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/features/mcp/screener_tools.py backend/tests/test_mcp_tools.py
git commit -m "feat(mcp): add screen_strategy tool (top-N + total_matches)" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 7: `market_tools.py` — `quote()`

**Files:**
- Create: `backend/features/mcp/market_tools.py`
- Test: append to `backend/tests/test_mcp_tools.py`

**Interfaces:**
- Consumes: `core.kite.get_kite` (whose `.ltp(list)` returns `{"NSE:SYM": {"last_price": float, ...}}`), `features.mcp.guards.needs_kite`.
- Produces: `quote(symbols: list[str]) -> dict` = `{"quotes": [{symbol, ltp}], "not_found": [str]}`; `register(mcp) -> None`. Cap: 50 symbols.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_mcp_tools.py`:

```python
import features.mcp.market_tools as market_tools


class _FakeKite:
    def __init__(self, data):
        self._data = data
        self.called_with = None

    def ltp(self, instruments):
        self.called_with = instruments
        return self._data


def test_quote_maps_symbols_and_rounds(monkeypatch):
    monkeypatch.setattr(guards, "is_authenticated", lambda: True)
    fake = _FakeKite({
        "NSE:INFY": {"last_price": 1543.256},
        "NSE:TCS": {"last_price": 3890.0},
    })
    monkeypatch.setattr(market_tools, "get_kite", lambda: fake)

    out = market_tools.quote(["infy", "TCS"])

    assert fake.called_with == ["NSE:INFY", "NSE:TCS"]
    assert {"symbol": "INFY", "ltp": 1543.26} in out["quotes"]
    assert out["not_found"] == []


def test_quote_collects_not_found(monkeypatch):
    monkeypatch.setattr(guards, "is_authenticated", lambda: True)
    fake = _FakeKite({"NSE:INFY": {"last_price": 1500.0}})
    monkeypatch.setattr(market_tools, "get_kite", lambda: fake)

    out = market_tools.quote(["INFY", "BOGUS"])
    assert [q["symbol"] for q in out["quotes"]] == ["INFY"]
    assert out["not_found"] == ["BOGUS"]


def test_quote_empty_input(monkeypatch):
    monkeypatch.setattr(guards, "is_authenticated", lambda: True)
    out = market_tools.quote([])
    assert out == {"quotes": [], "not_found": []}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_mcp_tools.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'features.mcp.market_tools'`.

- [ ] **Step 3: Implement `features/mcp/market_tools.py`**

```python
"""MCP tool: live last-traded price for NSE symbols via the warm Kite session."""
from __future__ import annotations

from core.kite import get_kite

from .guards import needs_kite

_MAX_SYMBOLS = 50


@needs_kite
def quote(symbols: list[str]) -> dict:
    """Live last-traded price (LTP) for a list of NSE symbols.

    Symbols are plain tradingsymbols (e.g. "INFY", "TCS"); the NSE exchange
    prefix is added internally. Capped at 50 symbols per call. Symbols with no
    quote are returned in `not_found`.
    """
    if not symbols:
        return {"quotes": [], "not_found": []}

    cleaned = [str(s).strip().upper() for s in symbols if str(s).strip()][:_MAX_SYMBOLS]
    keys = [f"NSE:{s}" for s in cleaned]
    data = get_kite().ltp(keys)

    quotes, not_found = [], []
    for sym in cleaned:
        entry = data.get(f"NSE:{sym}")
        if entry and entry.get("last_price") is not None:
            quotes.append({"symbol": sym, "ltp": round(float(entry["last_price"]), 2)})
        else:
            not_found.append(sym)
    return {"quotes": quotes, "not_found": not_found}


def register(mcp) -> None:
    mcp.tool(quote)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_mcp_tools.py -v`
Expected: PASS (14 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/features/mcp/market_tools.py backend/tests/test_mcp_tools.py
git commit -m "feat(mcp): add quote tool (live LTP via kite.ltp)" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 8: `auth_tools.py` — `kite_session_status()` + `kite_complete_login()`

**Files:**
- Create: `backend/features/mcp/auth_tools.py`
- Test: append to `backend/tests/test_mcp_tools.py`

**Interfaces:**
- Consumes: `core.kite.is_authenticated`, `core.kite.get_kite`, `core.kite.kite` (for `login_url()`), `kiteconnect.exceptions.TokenException`, `features.auth.service.complete_login` (Task 2).
- Produces: `kite_session_status() -> dict` = `{authenticated, token_valid, user_id, login_url}`; `kite_complete_login(request_token: str) -> dict` = `{status, user_id}` or `{status: "error", message, login_url}`; `register(mcp) -> None`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_mcp_tools.py`:

```python
import features.mcp.auth_tools as auth_tools


class _ProfileKite:
    def __init__(self, profile=None, raise_token=False):
        self._profile = profile or {}
        self._raise = raise_token

    def profile(self):
        if self._raise:
            raise TokenException("expired")
        return self._profile

    def login_url(self):
        return "http://login-url"


def test_session_status_unauthenticated(monkeypatch):
    monkeypatch.setattr(auth_tools, "is_authenticated", lambda: False)
    monkeypatch.setattr(auth_tools.kite, "login_url", lambda: "http://login-url")

    out = auth_tools.kite_session_status()
    assert out["authenticated"] is False
    assert out["token_valid"] is False
    assert out["login_url"] == "http://login-url"


def test_session_status_valid_probe(monkeypatch):
    monkeypatch.setattr(auth_tools, "is_authenticated", lambda: True)
    kobj = _ProfileKite(profile={"user_id": "AB1234"})
    monkeypatch.setattr(auth_tools, "get_kite", lambda: kobj)
    monkeypatch.setattr(auth_tools.kite, "login_url", lambda: "http://login-url")

    out = auth_tools.kite_session_status()
    assert out["authenticated"] is True
    assert out["token_valid"] is True
    assert out["user_id"] == "AB1234"


def test_session_status_expired_probe(monkeypatch):
    monkeypatch.setattr(auth_tools, "is_authenticated", lambda: True)
    monkeypatch.setattr(auth_tools, "get_kite", lambda: _ProfileKite(raise_token=True))
    monkeypatch.setattr(auth_tools.kite, "login_url", lambda: "http://login-url")

    out = auth_tools.kite_session_status()
    assert out["authenticated"] is True
    assert out["token_valid"] is False


def test_complete_login_success(monkeypatch):
    monkeypatch.setattr(auth_tools, "complete_login", lambda rt: {"user_id": "AB1234", "access_token": "tok"})
    out = auth_tools.kite_complete_login("req-token")
    assert out["status"] == "authenticated"
    assert out["user_id"] == "AB1234"


def test_complete_login_error(monkeypatch):
    def boom(rt):
        raise TokenException("bad request token")

    monkeypatch.setattr(auth_tools, "complete_login", boom)
    monkeypatch.setattr(auth_tools.kite, "login_url", lambda: "http://login-url")
    out = auth_tools.kite_complete_login("bad")
    assert out["status"] == "error"
    assert "login_url" in out
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_mcp_tools.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'features.mcp.auth_tools'`.

- [ ] **Step 3: Implement `features/mcp/auth_tools.py`**

```python
"""MCP tools: report Kite session status and complete the login handshake."""
from __future__ import annotations

from kiteconnect.exceptions import TokenException

from core.kite import get_kite, is_authenticated, kite
from features.auth.service import complete_login


def kite_session_status() -> dict:
    """Report whether the Kite session is live.

    `authenticated` reflects whether a token is held; `token_valid` is confirmed
    by a lightweight profile probe (so an expired token reads as invalid, not
    merely present). Always returns a login_url to guide re-auth.
    """
    if not is_authenticated():
        return {"authenticated": False, "token_valid": False, "user_id": None, "login_url": kite.login_url()}
    try:
        profile = get_kite().profile()
        return {
            "authenticated": True,
            "token_valid": True,
            "user_id": profile.get("user_id"),
            "login_url": kite.login_url(),
        }
    except TokenException:
        return {"authenticated": True, "token_valid": False, "user_id": None, "login_url": kite.login_url()}


def kite_complete_login(request_token: str) -> dict:
    """Exchange a Zerodha request_token for a live session.

    Obtain request_token by opening the login_url (from kite_session_status),
    authorizing, and copying it from the redirect URL. On success the screener
    refresh is kicked off automatically.
    """
    try:
        result = complete_login(request_token)
        return {"status": "authenticated", "user_id": result.get("user_id")}
    except Exception as e:
        # Keep the real failure reason; still hand back a login_url to retry.
        return {"status": "error", "message": str(e), "login_url": kite.login_url()}


def register(mcp) -> None:
    mcp.tool(kite_session_status)
    mcp.tool(kite_complete_login)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_mcp_tools.py -v`
Expected: PASS (19 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/features/mcp/auth_tools.py backend/tests/test_mcp_tools.py
git commit -m "feat(mcp): add kite_session_status and kite_complete_login tools" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 9: `server.py` + mount into `main.py`

**Files:**
- Create: `backend/features/mcp/server.py`
- Modify: `backend/main.py`
- Modify: `backend/pyproject.toml` + `backend/uv.lock` (via `uv add fastmcp`)
- Test: `backend/tests/test_mcp_server.py`

**Interfaces:**
- Consumes: `register(mcp)` from all five tool modules; `fastmcp.FastMCP`.
- Produces: `build_server() -> FastMCP`; module globals `mcp` and `mcp_app = mcp.http_app(path="/")`.

- [ ] **Step 1: Add the FastMCP dependency**

Run: `uv add fastmcp`
Expected: `pyproject.toml` gains `fastmcp>=3.2...`; `uv.lock` updates. Verify the resolved version is 3.2.x: `uv run python -c "import fastmcp; print(fastmcp.__version__)"`.

- [ ] **Step 2: Write the failing test**

Create `backend/tests/test_mcp_server.py`:

```python
import anyio
from fastmcp import Client

from features.mcp.server import build_server

_EXPECTED_TOOLS = {
    "portfolio_holdings",
    "portfolio_metrics",
    "screen_strategy",
    "quote",
    "kite_session_status",
    "kite_complete_login",
}


def test_all_tools_registered():
    mcp = build_server()

    async def _list():
        async with Client(mcp) as client:
            return await client.list_tools()

    names = {t.name for t in anyio.run(_list)}
    assert names >= _EXPECTED_TOOLS


def test_screen_strategy_callable_end_to_end():
    # Unknown-strategy path returns before touching the cache or Kite, so this
    # exercises registration + call + structured return with no live session.
    mcp = build_server()

    async def _call():
        async with Client(mcp) as client:
            return await client.call_tool("screen_strategy", {"name": "bogus"})

    result = anyio.run(_call)
    assert "bogus" in str(result.data)
    assert "valid_strategies" in str(result.data)
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `uv run pytest tests/test_mcp_server.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'features.mcp.server'`.

- [ ] **Step 4: Implement `features/mcp/server.py`**

```python
"""Builds the read-only FastMCP server and its ASGI app for mounting.

Tools import the service layer directly (no HTTP self-calls). Each feature
module exposes register(mcp); this module is the only one that imports fastmcp.
"""
from __future__ import annotations

from fastmcp import FastMCP

from . import auth_tools, fragility_tools, market_tools, portfolio_tools, screener_tools

_MODULES = (auth_tools, portfolio_tools, fragility_tools, screener_tools, market_tools)


def build_server() -> FastMCP:
    mcp = FastMCP("Kite Portfolio (read-only)")
    for module in _MODULES:
        module.register(mcp)
    return mcp


mcp = build_server()
mcp_app = mcp.http_app(path="/")
```

- [ ] **Step 5: Mount into `backend/main.py`**

Replace the file with:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from features.auth.routes import router as auth_router
from features.portfolio.routes import router as portfolio_router
from features.exit.routes import router as exit_router
from features.fragility.routes import router as fragility_router
from features.screener.routes import router as screener_router
from features.mcp.server import mcp_app

# The MCP ASGI app's lifespan runs its streamable-HTTP session manager; it MUST
# be attached to the parent app or MCP requests fail.
app = FastAPI(lifespan=mcp_app.lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api/auth")
app.include_router(portfolio_router, prefix="/api/portfolio")
app.include_router(exit_router, prefix="/api/exit")
app.include_router(fragility_router, prefix="/api/fragility")
app.include_router(screener_router, prefix="/api/screener")

# Streamable-HTTP MCP endpoint at http://localhost:8000/mcp/
app.mount("/mcp", mcp_app)
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `uv run pytest tests/test_mcp_server.py -v`
Expected: PASS (2 passed).

- [ ] **Step 7: Run the full suite + import-check main**

Run: `uv run pytest -q`
Expected: all tests pass.
Run: `uv run python -c "import main; print('mounted:', any(getattr(r, 'path', '') == '/mcp' for r in main.app.routes))"`
Expected: prints `mounted: True`.

- [ ] **Step 8: Commit**

```bash
git add backend/features/mcp/server.py backend/main.py backend/pyproject.toml backend/uv.lock backend/tests/test_mcp_server.py
git commit -m "feat(mcp): build FastMCP server and mount it into the FastAPI app" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 10: Docs — CLAUDE.md + Claude Desktop client config

**Files:**
- Create: `backend/features/mcp/README.md`
- Modify: `CLAUDE.md`

**Interfaces:** None (documentation).

- [ ] **Step 1: Write the client config + how-to at `backend/features/mcp/README.md`**

```markdown
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

## Connect Claude Desktop

The backend must be running (`uv run uvicorn main:app --reload` from `backend/`)
and you must have completed a Kite login (via the web app, or the
`kite_session_status` → `kite_complete_login` tool flow).

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
```

- [ ] **Step 2: Document the feature in `CLAUDE.md`**

In the "What This Project Is" list, add a fifth bullet:

```markdown
- **MCP Server** — read-only Model Context Protocol server (`features/mcp/`) mounted into the FastAPI app at `/mcp`, exposing holdings, the diversification suite, the screener, live quotes, and Kite session tools to an AI assistant
```

In the Backend architecture section, after the Screener paragraph, add:

```markdown
**MCP server** (`features/mcp/`) — a read-only FastMCP v3 server mounted into the
same FastAPI process via `mcp.http_app()` (`main.py` attaches `mcp_app.lifespan`
and mounts at `/mcp`). One tool module per feature area (`portfolio_tools`,
`fragility_tools`, `screener_tools`, `market_tools`, `auth_tools`); each exposes
`register(mcp)` that attaches plain functions via `mcp.tool(fn)`. Tools import the
service layer directly — no HTTP self-calls. Kite-touching tools use the
`@needs_kite` guard (`guards.py`), which returns a `login_url` payload on a
missing/expired token instead of raising. Screener tools are cache-only and
ungated. The Kite token is persisted in `core/kite.py` (table `kite_session`) and
restored on startup if same-IST-day, so a mid-day restart isn't a re-login.
```

Also update the Key Constraints bullet about the in-memory token:

```markdown
- Kite access token is persisted (table `kite_session` in `settings.db`) and restored on startup only if generated the same IST day; tokens still expire ~06:00 IST daily, requiring re-auth via `/api/auth/login` or the `kite_complete_login` MCP tool.
```

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md backend/features/mcp/README.md
git commit -m "docs(mcp): document the MCP server and Claude Desktop client config" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 11: Manual end-to-end verification

**Files:** None (verification checklist — no code, no commit).

This gate covers what unit tests with a mocked Kite cannot: the real mount, a live
login, and a Claude Desktop round-trip.

- [ ] **Step 1: Start the backend**

Run (from `backend/`): `uv run uvicorn main:app --reload`
Expected: starts with no lifespan/import errors.

- [ ] **Step 2: Confirm the MCP endpoint is mounted**

In another shell: `uv run python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/mcp/')"`
Expected: an HTTP error/response from the MCP handler (e.g. 406/400 for a non-MCP request), **not** a connection refused or 404 — the endpoint exists and responds.

- [ ] **Step 3: Verify the auth-fail path (no login yet, or after restart on a fresh day)**

With no active session, use any MCP client (or the `fastmcp` in-memory client) to call `portfolio_holdings` and confirm it returns `{"status": "auth_required", "login_url": ...}` rather than an error. Then open the `login_url`, authorize, and call `kite_complete_login(request_token)` (request_token is in the redirect URL). Expected: `{"status": "authenticated", "user_id": ...}`.

- [ ] **Step 4: Verify live tools after login**

Call `kite_session_status()` → `token_valid: true`. Call `portfolio_holdings()` → real rows + totals. Call `quote(["INFY"])` → a live LTP.

- [ ] **Step 5: Verify the screener tool works cache-only**

Call `screen_strategy("momentum_12_1", limit=5)` → up to 5 rows + `total_matches`. (If `total_matches` is 0 with a `note`, the cache is unseeded — trigger a login/refresh first.)

- [ ] **Step 6: Connect Claude Desktop**

Add the config from `backend/features/mcp/README.md`, restart Claude Desktop, and confirm the `kite-portfolio` tools appear and a natural-language question ("what are my holdings?") invokes `portfolio_holdings`.

- [ ] **Step 7: Confirm no regression to the existing app**

Confirm the React frontend still loads and the REST endpoints (`/api/portfolio/overview`, `/api/screener/status`) still respond as before.

---

## Notes for the implementer

- **Test count in step expectations is cumulative** for `test_mcp_tools.py` (3 → 5 → 7 → 11 → 14 → 19) because each task appends to the same file. If your count differs, re-check the previous task's tests are intact.
- **Do not** apply `@needs_kite` to `screen_strategy`, `kite_session_status`, or `kite_complete_login` — the first is cache-only; the latter two must work precisely when there is no valid token.
- **`mcp.tool(fn)` is the registration call** (FastMCP v3 decorators return the original function, so `fn` stays importable for the unit tests).
- Keep all outputs pre-rounded and compact; never return covariance/correlation matrices or the full screener universe.
