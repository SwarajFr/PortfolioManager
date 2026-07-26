# In-App Agent Chat (local LLM) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an "Agent" tab where the user asks about their portfolio in natural language and a local Gemma 4 model (via Ollama) answers by calling the existing read-only analytics as tools.

**Architecture:** A new `features/agent/` package holds the tool schemas (`tools.py`, reusing `features/mcp/*_tools.py`), a manual OpenAI-format tool loop (`service.py`) against a provider-agnostic OpenAI-compatible client (default: Ollama at `http://localhost:11434/v1`), and a FastAPI route (`POST /api/agent/chat`). The frontend adds an interaction-driven chat page and a nav entry. Spinner-then-reply; stateless text-only history.

**Tech Stack:** Python ≥3.12, FastAPI, `openai` SDK, Ollama + Gemma 4 (`gemma4:e4b`), React 19 / Vite, Tailwind v4, uv.

## Global Constraints

Every task's requirements implicitly include this section.

- **`uv` for backend deps** (`uv add`, `uv run`); run everything from `backend/`. No `pip`.
- **Provider-agnostic LLM:** the `openai` SDK with `base_url` + `api_key` from `config.py` (`LLM_BASE_URL` default `http://localhost:11434/v1`, `LLM_API_KEY` default `"ollama"`); `model` from `agent_settings` (default `gemma4:e4b`). No Anthropic SDK. No `thinking`/`effort` params (Anthropic-only).
- **Read-only.** Tools are the four read-only MCP tool functions only — no order flow, no new analytics. Reuse `features/mcp/*_tools.py`; do not reimplement them.
- **Frontend:** React 19 with the `react-hooks/set-state-in-effect` lint as an error — **no `setState` inside `useEffect`**. The chat is interaction-driven (state changes only in the submit handler); the one effect does `scrollIntoView` on a ref (a DOM call, not `setState`). `apiClient` is a **named export**. Reuse `PageShell`, `Button`, `cn`, and `--color-*` / `--radius-*` CSS vars.
- **Every commit message ends with the trailer:** `-m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"`
- Continue on the existing **`feat/mcp-server`** branch (the agent reuses that branch's MCP tool layer).

---

### Task 1: config LLM vars + `features/agent/` package + settings

**Files:**
- Modify: `backend/config.py`
- Create: `backend/features/agent/__init__.py` (empty)
- Create: `backend/features/agent/settings.py`
- Test: `backend/tests/test_agent_settings.py`

**Interfaces:**
- Consumes: `core.settings_store.{load_settings,save_settings,reset_settings}`.
- Produces: `config.LLM_BASE_URL`, `config.LLM_API_KEY`; `settings.get_settings() -> dict` (keys `model`, `max_tokens`, `max_tool_iterations`, `system_prompt`), `settings.save_agent_settings`, `settings.reset_agent_settings`. Table `agent_settings`.

- [ ] **Step 1: Add LLM config to `backend/config.py`**

Append after the existing `FRONTEND_URL` line:

```python
# Local-first LLM for the in-app Agent tab (OpenAI-compatible endpoint).
# Defaults target Ollama; override to point at any OpenAI-compatible provider.
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")
LLM_API_KEY = os.getenv("LLM_API_KEY", "ollama")
```

- [ ] **Step 2: Create the empty package init**

Create `backend/features/agent/__init__.py` (empty file).

- [ ] **Step 3: Write the failing test**

Create `backend/tests/test_agent_settings.py`:

```python
import core.settings_store as store
import features.agent.settings as agent_settings


def test_defaults_on_empty_db(monkeypatch, tmp_path):
    monkeypatch.setattr(store, "DB_PATH", str(tmp_path / "settings.db"))
    conf = agent_settings.get_settings()
    assert conf["model"] == "gemma4:e4b"
    assert conf["max_tool_iterations"] == 8
    assert "read-only" in conf["system_prompt"].lower()
```

- [ ] **Step 4: Run the test to verify it fails**

Run: `uv run pytest tests/test_agent_settings.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'features.agent.settings'`.

- [ ] **Step 5: Implement `backend/features/agent/settings.py`**

```python
from core.settings_store import (
    load_settings,
    reset_settings as reset_stored_settings,
    save_settings as save_stored_settings,
)

_TABLE = "agent_settings"

_SYSTEM_PROMPT = (
    "You are a read-only portfolio assistant for the user's Zerodha (NSE India) holdings. "
    "Answer using the provided tools rather than guessing; never invent numbers or ticker symbols. "
    "Report only figures the tools return, and say so plainly when data is unavailable or a tool "
    "reports an error. You are READ-ONLY and cannot place, modify, or cancel orders. "
    'If a tool result contains "status": "auth_required", tell the user to log in to Kite first. '
    "Be concise."
)

_DEFAULTS = {
    "model": "gemma4:e4b",
    "max_tokens": 8192,
    "max_tool_iterations": 8,
    "system_prompt": _SYSTEM_PROMPT,
}


def get_settings() -> dict:
    return load_settings(_TABLE, _DEFAULTS)


def save_agent_settings(config: dict) -> None:
    save_stored_settings(_TABLE, {**_DEFAULTS, **config})


def reset_agent_settings() -> dict:
    return reset_stored_settings(_TABLE, _DEFAULTS)
```

- [ ] **Step 6: Run the test to verify it passes**

Run: `uv run pytest tests/test_agent_settings.py -v`
Expected: PASS (1 passed).

- [ ] **Step 7: Commit**

```bash
git add backend/config.py backend/features/agent/__init__.py backend/features/agent/settings.py backend/tests/test_agent_settings.py
git commit -m "feat(agent): add package, LLM config, and agent_settings" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: `tools.py` — OpenAI tool schemas + dispatch

**Files:**
- Create: `backend/features/agent/tools.py`
- Test: `backend/tests/test_agent_tools.py`

**Interfaces:**
- Consumes: `features.mcp.portfolio_tools.portfolio_holdings`, `features.mcp.fragility_tools.portfolio_metrics`, `features.mcp.screener_tools.screen_strategy`, `features.mcp.market_tools.quote`.
- Produces: `SCHEMAS: list[dict]` (OpenAI chat.completions function tools); `dispatch(name: str, arguments_json: str) -> dict`; `_HANDLERS: dict[str, callable]`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_agent_tools.py`:

```python
import features.agent.tools as agent_tools


def test_schemas_cover_all_handlers():
    names = {s["function"]["name"] for s in agent_tools.SCHEMAS}
    assert names == set(agent_tools._HANDLERS)


def test_dispatch_routes_and_parses_args(monkeypatch):
    seen = {}
    monkeypatch.setitem(
        agent_tools._HANDLERS, "screen_strategy",
        lambda **kw: (seen.update(kw), {"ok": True})[1],
    )
    out = agent_tools.dispatch("screen_strategy", '{"name": "breakout", "limit": 5}')
    assert out == {"ok": True}
    assert seen == {"name": "breakout", "limit": 5}


def test_dispatch_unknown_tool():
    assert "error" in agent_tools.dispatch("nope", "{}")


def test_dispatch_bad_json():
    assert "error" in agent_tools.dispatch("quote", "{not json")


def test_dispatch_handler_exception(monkeypatch):
    def boom(**kw):
        raise ValueError("kaboom")

    monkeypatch.setitem(agent_tools._HANDLERS, "quote", boom)
    out = agent_tools.dispatch("quote", '{"symbols": ["X"]}')
    assert "error" in out and "kaboom" in out["error"]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_agent_tools.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'features.agent.tools'`.

- [ ] **Step 3: Implement `backend/features/agent/tools.py`**

```python
"""OpenAI-format tool schemas + dispatch, reusing the read-only MCP tools."""
from __future__ import annotations

import json

from features.mcp.fragility_tools import portfolio_metrics
from features.mcp.market_tools import quote
from features.mcp.portfolio_tools import portfolio_holdings
from features.mcp.screener_tools import screen_strategy

_HANDLERS = {
    "portfolio_holdings": portfolio_holdings,
    "portfolio_metrics": portfolio_metrics,
    "screen_strategy": screen_strategy,
    "quote": quote,
}

SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "portfolio_holdings",
            "description": "Current live holdings with per-position P&L and portfolio totals. No arguments.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "portfolio_metrics",
            "description": (
                "Diversification metrics for the portfolio: diversification ratio, effective number "
                "of bets (ENB), weight entropy, average/max correlation, concentration gap. No arguments."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "screen_strategy",
            "description": (
                "Run one NSE500 technical screener strategy and return the top matches with a total count. "
                "Valid names: ma_crossover, momentum_12_1, breakout, rsi_reversion, high_52w."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "strategy name"},
                    "universe": {"type": "string", "description": "only NSE500 is supported"},
                    "limit": {"type": "integer", "description": "max results to return"},
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "quote",
            "description": "Live last-traded price for a list of NSE symbols, e.g. [\"INFY\", \"TCS\"].",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbols": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "NSE tradingsymbols",
                    }
                },
                "required": ["symbols"],
            },
        },
    },
]


def dispatch(name: str, arguments_json: str) -> dict:
    """Route a tool call to its handler. Never raises — a failure is returned as {'error': ...}."""
    handler = _HANDLERS.get(name)
    if handler is None:
        return {"error": f"unknown tool: {name}"}
    try:
        args = json.loads(arguments_json or "{}")
    except json.JSONDecodeError as e:
        return {"error": f"invalid tool arguments: {e}"}
    try:
        return handler(**args)
    except Exception as e:  # a broken tool must not kill the agent loop
        return {"error": f"{type(e).__name__}: {e}"}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_agent_tools.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/features/agent/tools.py backend/tests/test_agent_tools.py
git commit -m "feat(agent): OpenAI tool schemas + dispatch reusing MCP tools" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: `uv add openai` + `service.py` tool loop

**Files:**
- Modify: `backend/pyproject.toml` + `backend/uv.lock` (via `uv add openai`)
- Create: `backend/features/agent/service.py`
- Test: `backend/tests/test_agent_service.py`

**Interfaces:**
- Consumes: `openai.OpenAI`, `config.LLM_BASE_URL`, `config.LLM_API_KEY`, `settings.get_settings`, `tools.SCHEMAS`, `tools.dispatch`.
- Produces: `run_chat(history: list[dict]) -> dict` returning `{"reply", "tool_calls", "stop"}` or `{"error", "message"}`; module global `_client`.

- [ ] **Step 1: Add the openai dependency**

Run: `uv add openai`
Verify: `uv run python -c "import openai; print(openai.__version__)"`.

- [ ] **Step 2: Write the failing tests**

Create `backend/tests/test_agent_service.py`:

```python
from types import SimpleNamespace

import httpx
import openai
import pytest

import features.agent.service as agent_service


def _msg(content=None, tool_calls=None):
    return SimpleNamespace(content=content, tool_calls=tool_calls)


def _resp(message):
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def _toolcall(id, name, arguments):
    return SimpleNamespace(id=id, function=SimpleNamespace(name=name, arguments=arguments))


class _FakeClient:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        return self._responses.pop(0)


@pytest.fixture(autouse=True)
def _fixed_settings(monkeypatch):
    monkeypatch.setattr(agent_service.settings, "get_settings", lambda: {
        "model": "test-model", "max_tokens": 256, "max_tool_iterations": 4, "system_prompt": "sys",
    })


def test_direct_answer(monkeypatch):
    monkeypatch.setattr(agent_service, "_client", _FakeClient([_resp(_msg(content="hi there"))]))
    out = agent_service.run_chat([{"role": "user", "content": "hello"}])
    assert out == {"reply": "hi there", "tool_calls": [], "stop": "done"}


def test_tool_then_answer(monkeypatch):
    fake = _FakeClient([
        _resp(_msg(tool_calls=[_toolcall("t1", "quote", '{"symbols": ["INFY"]}')])),
        _resp(_msg(content="INFY is 1500")),
    ])
    monkeypatch.setattr(agent_service, "_client", fake)
    monkeypatch.setattr(agent_service.tools, "dispatch",
                        lambda name, args: {"quotes": [{"symbol": "INFY", "ltp": 1500}]})

    out = agent_service.run_chat([{"role": "user", "content": "price of infy"}])
    assert out["reply"] == "INFY is 1500"
    assert out["tool_calls"] == [{"name": "quote"}]
    # the tool result was carried back on the 2nd model call
    second = fake.calls[1]["messages"]
    assert second[-1]["role"] == "tool" and second[-1]["tool_call_id"] == "t1"
    assert second[-2]["role"] == "assistant" and second[-2]["tool_calls"][0]["id"] == "t1"


def test_iteration_cap(monkeypatch):
    fake = _FakeClient([_resp(_msg(tool_calls=[_toolcall("t", "quote", "{}")])) for _ in range(4)])
    monkeypatch.setattr(agent_service, "_client", fake)
    monkeypatch.setattr(agent_service.tools, "dispatch", lambda name, args: {"ok": 1})
    out = agent_service.run_chat([{"role": "user", "content": "loop"}])
    assert out["stop"] == "max_iters"


def test_unreachable(monkeypatch):
    class _Boom:
        def __init__(self):
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

        def _create(self, **kwargs):
            raise openai.APIConnectionError(request=httpx.Request("POST", "http://localhost:11434/v1"))

    monkeypatch.setattr(agent_service, "_client", _Boom())
    out = agent_service.run_chat([{"role": "user", "content": "hi"}])
    assert out["error"] == "llm_unreachable"
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run pytest tests/test_agent_service.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'features.agent.service'`.

- [ ] **Step 4: Implement `backend/features/agent/service.py`**

```python
"""The read-only agent: a manual OpenAI-format tool loop over the MCP tools."""
from __future__ import annotations

import json

import openai
from openai import OpenAI

from config import LLM_API_KEY, LLM_BASE_URL

from . import settings, tools

_client = OpenAI(base_url=LLM_BASE_URL, api_key=LLM_API_KEY)


def _assistant_dict(msg) -> dict:
    """Rebuild the assistant turn (with tool_calls) as a plain, serializable dict."""
    return {
        "role": "assistant",
        "content": msg.content or "",
        "tool_calls": [
            {
                "id": tc.id,
                "type": "function",
                "function": {"name": tc.function.name, "arguments": tc.function.arguments},
            }
            for tc in msg.tool_calls
        ],
    }


def run_chat(history: list[dict]) -> dict:
    """Run the tool loop to completion and return a compact payload for the UI.

    `history` is the text-only [{role, content}] conversation from the client.
    Returns {"reply", "tool_calls", "stop"} on success, or {"error", "message"}.
    """
    conf = settings.get_settings()
    msgs = [{"role": "system", "content": conf["system_prompt"]}, *history]
    trace: list[dict] = []
    try:
        for _ in range(int(conf["max_tool_iterations"])):
            resp = _client.chat.completions.create(
                model=conf["model"],
                messages=msgs,
                tools=tools.SCHEMAS,
                tool_choice="auto",
                max_tokens=int(conf["max_tokens"]),
            )
            msg = resp.choices[0].message
            if not msg.tool_calls:
                return {"reply": msg.content or "", "tool_calls": trace, "stop": "done"}
            msgs.append(_assistant_dict(msg))
            for tc in msg.tool_calls:
                result = tools.dispatch(tc.function.name, tc.function.arguments)
                trace.append({"name": tc.function.name})
                msgs.append({"role": "tool", "tool_call_id": tc.id, "content": json.dumps(result)})
        return {
            "reply": "Stopped after too many tool calls without a final answer.",
            "tool_calls": trace,
            "stop": "max_iters",
        }
    except openai.APIConnectionError:
        return {
            "error": "llm_unreachable",
            "message": f"Can't reach the model at {LLM_BASE_URL}. Is Ollama running with the model pulled?",
        }
    except openai.OpenAIError as e:
        return {"error": "agent_error", "message": str(e)}
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_agent_service.py -v`
Expected: PASS (4 passed).

- [ ] **Step 6: Commit**

```bash
git add backend/features/agent/service.py backend/tests/test_agent_service.py backend/pyproject.toml backend/uv.lock
git commit -m "feat(agent): add openai dep and the tool-loop service" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: `routes.py` + mount in `main.py`

**Files:**
- Create: `backend/features/agent/routes.py`
- Modify: `backend/main.py`
- Test: `backend/tests/test_agent_routes.py`

**Interfaces:**
- Consumes: `service.run_chat`.
- Produces: `router` with `POST /chat` (mounted at `/api/agent`).

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_agent_routes.py`:

```python
from fastapi import FastAPI
from starlette.testclient import TestClient

import features.agent.routes as routes


def _app():
    app = FastAPI()
    app.include_router(routes.router, prefix="/api/agent")
    return app


def test_requires_messages():
    client = TestClient(_app())
    assert client.post("/api/agent/chat", json={}).status_code == 400


def test_happy_path(monkeypatch):
    monkeypatch.setattr(routes, "run_chat", lambda msgs: {"reply": "ok", "tool_calls": []})
    client = TestClient(_app())
    r = client.post("/api/agent/chat", json={"messages": [{"role": "user", "content": "hi"}]})
    assert r.status_code == 200 and r.json()["reply"] == "ok"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_agent_routes.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'features.agent.routes'`.

- [ ] **Step 3: Implement `backend/features/agent/routes.py`**

```python
from fastapi import APIRouter, HTTPException, Request

from .service import run_chat

router = APIRouter()


@router.post("/chat")
async def chat(request: Request):
    body = await request.json()
    messages = body.get("messages")
    if not messages or not isinstance(messages, list):
        raise HTTPException(status_code=400, detail="messages (a non-empty list) is required")
    return run_chat(messages)
```

- [ ] **Step 4: Mount the router in `backend/main.py`**

Add the import alongside the other feature routers:

```python
from features.agent.routes import router as agent_router
```

Add the include after the screener router line:

```python
app.include_router(agent_router, prefix="/api/agent")
```

- [ ] **Step 5: Run the tests + full suite**

Run: `uv run pytest tests/test_agent_routes.py -v`
Expected: PASS (2 passed).
Run: `uv run pytest -q`
Expected: all tests pass.
Run: `uv run python -c "import main; print('agent mounted:', any(getattr(r,'path','').startswith('/api/agent') for r in main.app.routes))"`
Expected: prints `agent mounted: True`.

- [ ] **Step 6: Commit**

```bash
git add backend/features/agent/routes.py backend/main.py backend/tests/test_agent_routes.py
git commit -m "feat(agent): add /api/agent/chat route and mount it" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: Frontend — service + AgentPage chat UI

**Files:**
- Create: `frontend/src/services/agentService.js`
- Create: `frontend/src/features/agent/AgentPage.jsx`

**Interfaces:**
- Consumes: `apiClient` (named export), `PageShell`, `Button`, `cn`.
- Produces: `postChat(messages) -> Promise<data>`; default-exported `AgentPage`.

- [ ] **Step 1: Create `frontend/src/services/agentService.js`**

```javascript
import { apiClient } from "./apiClient";

export async function postChat(messages) {
  const { data } = await apiClient.post("/agent/chat", { messages });
  return data;
}
```

- [ ] **Step 2: Create `frontend/src/features/agent/AgentPage.jsx`**

```jsx
import { useEffect, useRef, useState } from "react";
import PageShell from "../../components/layout/PageShell";
import Button from "../../components/ui/Button";
import { cn } from "../../utils/classNames";
import { postChat } from "../../services/agentService";

export default function AgentPage() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [pending, setPending] = useState(false);
  const endRef = useRef(null);

  // DOM side effect only (no setState) — safe under react-hooks/set-state-in-effect.
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, pending]);

  async function handleSend(event) {
    event.preventDefault();
    const text = input.trim();
    if (!text || pending) return;

    const history = [...messages, { role: "user", content: text }];
    setMessages(history);
    setInput("");
    setPending(true);
    try {
      const data = await postChat(history.map((m) => ({ role: m.role, content: m.content })));
      const reply = data.error
        ? { role: "assistant", content: data.message || "The agent hit an error.", error: true }
        : { role: "assistant", content: data.reply || "(no answer)", toolCalls: data.tool_calls || [] };
      setMessages((prev) => [...prev, reply]);
    } catch (err) {
      setMessages((prev) => [...prev, { role: "assistant", content: err.message, error: true }]);
    } finally {
      setPending(false);
    }
  }

  return (
    <PageShell eyebrow="Assistant" title="Agent">
      <div className="flex min-h-[60vh] flex-col gap-4">
        <div className="flex-1 space-y-4 overflow-y-auto pr-1">
          {messages.length === 0 ? (
            <p className="font-mono text-[0.75rem] leading-relaxed text-[var(--color-text-muted)]">
              Ask about your holdings, diversification, a screener strategy, or a live quote. The
              assistant runs locally via Ollama and is read-only — it can look things up but never
              places orders.
            </p>
          ) : null}

          {messages.map((m, i) => (
            <div
              key={i}
              className={cn(
                "max-w-[85%] rounded-[var(--radius-sm)] border px-3.5 py-2.5 text-[0.8125rem] leading-relaxed",
                m.role === "user"
                  ? "ml-auto border-[var(--color-accent)] bg-[var(--color-surface-soft)] text-[var(--color-text)]"
                  : m.error
                    ? "border-[var(--color-loss)] text-[var(--color-loss)]"
                    : "border-[var(--color-border)] bg-[var(--color-surface-soft)] text-[var(--color-text)]",
              )}
            >
              <p className="whitespace-pre-wrap">{m.content}</p>
              {m.toolCalls && m.toolCalls.length > 0 ? (
                <div className="mt-2 flex flex-wrap gap-1">
                  {m.toolCalls.map((t, j) => (
                    <span
                      key={j}
                      className="rounded-[var(--radius-sm)] border border-[var(--color-border)] px-1.5 py-0.5 font-mono text-[0.5625rem] uppercase tracking-[0.1em] text-[var(--color-text-muted)]"
                    >
                      {t.name}
                    </span>
                  ))}
                </div>
              ) : null}
            </div>
          ))}

          {pending ? (
            <div className="max-w-[85%] rounded-[var(--radius-sm)] border border-[var(--color-border)] bg-[var(--color-surface-soft)] px-3.5 py-2.5">
              <span className="font-mono text-[0.6875rem] uppercase tracking-[0.12em] text-[var(--color-text-muted)]">
                Thinking…
              </span>
            </div>
          ) : null}

          <div ref={endRef} />
        </div>

        <form onSubmit={handleSend} className="flex items-end gap-2 border-t border-[var(--color-border)] pt-4">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) handleSend(e);
            }}
            rows={2}
            placeholder="Ask about your portfolio…"
            className="flex-1 resize-none rounded-[var(--radius-sm)] border border-[var(--color-border)] bg-transparent px-3 py-2 text-[0.8125rem] text-[var(--color-text)] outline-none focus:border-[var(--color-accent)]"
          />
          <Button type="submit" variant="primary" disabled={pending || !input.trim()}>
            Send
          </Button>
        </form>
      </div>
    </PageShell>
  );
}
```

- [ ] **Step 3: (Optional design pass)** Invoke the `frontend-design` skill to refine the chat surface (bubble spacing, empty state, pending shimmer) while keeping the structure and the no-`setState`-in-effect rule. Not required to pass build/lint.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/services/agentService.js frontend/src/features/agent/AgentPage.jsx
git commit -m "feat(agent): add chat service and AgentPage UI" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: Wire the nav entry + lazy page

**Files:**
- Modify: `frontend/src/constants/navigation.js`
- Modify: `frontend/src/app/App.jsx`

**Interfaces:**
- Consumes: `AgentPage` (default export).
- Produces: nav item `agent`; `PAGES.agent`.

- [ ] **Step 1: Add the nav entry in `frontend/src/constants/navigation.js`**

Append to the `NAV_ITEMS` array (after the `screener` entry):

```javascript
  {
    id: "agent",
    label: "Agent",
    eyebrow: "Assistant",
    description: "Ask about your portfolio in natural language",
  },
```

- [ ] **Step 2: Register the lazy page in `frontend/src/app/App.jsx`**

Add the lazy import alongside the others:

```javascript
const AgentPage = lazy(() => import("../features/agent/AgentPage"));
```

Add it to the `PAGES` map:

```javascript
const PAGES = {
  overview: PortfolioOverviewPage,
  exit: ExitSignalsPage,
  fragility: FragilityPage,
  screener: ScreenerPage,
  agent: AgentPage,
};
```

- [ ] **Step 3: Verify lint + build**

Run (from `frontend/`): `npm run lint`
Expected: passes (no `react-hooks/set-state-in-effect` violation in `AgentPage.jsx`).
Run: `npm run build`
Expected: builds successfully.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/constants/navigation.js frontend/src/app/App.jsx
git commit -m "feat(agent): add Agent nav tab and lazy route" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 7: Docs — CLAUDE.md + agent README

**Files:**
- Create: `backend/features/agent/README.md`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Write `backend/features/agent/README.md`**

```markdown
# Agent (in-app chat, local LLM, read-only)

A chat tab where the user asks about their portfolio and a local LLM answers by
calling the read-only analytics as tools. Provider-agnostic: built on the
OpenAI-compatible Chat Completions API, defaulting to a local Ollama model.

## Prerequisite — run a local model with Ollama

1. Install Ollama.
2. Pull a Gemma 4 model: `ollama pull gemma4:e4b` (9.6 GB; laptop/CPU-friendly).
   Other sizes: `gemma4:e2b` (7.2 GB), `gemma4:26b`, `gemma4:31b` — set the
   `model` setting to match what you pull.
3. Ollama serves the OpenAI-compatible API at `http://localhost:11434/v1` — the
   agent's default. If it isn't running, the tab shows a clear "can't reach the
   model" message.

## Point at a different provider

Set in `backend/.env` (both optional; shown with defaults):

    LLM_BASE_URL=http://localhost:11434/v1
    LLM_API_KEY=ollama

Repoint `LLM_BASE_URL` + `LLM_API_KEY` at any OpenAI-compatible endpoint and set
the `agent_settings.model` to that provider's model — no code change.

## Tools (all read-only)

portfolio_holdings · portfolio_metrics · screen_strategy · quote — the same
functions the MCP server exposes (`features/mcp/*_tools.py`). No order flow.
```

- [ ] **Step 2: Update `CLAUDE.md`**

- In "What This Project Is", change the feature-area count from **Five** to **Six** and add a bullet after the MCP Server bullet:

```markdown
- **Agent** — in-app chat tab (`features/agent/`) where a local LLM (Ollama / Gemma 4, provider-agnostic via the OpenAI-compatible API) answers portfolio questions by calling the read-only MCP tools; no order flow
```

- In the Backend architecture section, after the MCP server paragraph, add:

```markdown
**Agent** (`features/agent/`) — a read-only chat agent. `service.run_chat(history)` runs a manual OpenAI-format tool loop (`openai` SDK) against a provider-agnostic endpoint (`config.LLM_BASE_URL`/`LLM_API_KEY`, default local Ollama at `:11434/v1`; `model` from `agent_settings`, default `gemma4:e4b`). `tools.py` exposes the four read-only MCP tool functions as OpenAI function tools and dispatches calls to them (a tool failure returns `{"error": …}`, never crashes the loop). `routes.py` mounts `POST /api/agent/chat` at `/api/agent`. Requires a local model — see `features/agent/README.md`.
```

- In the Frontend architecture section, update the `activeView` list to include `agent`:

```markdown
`activeView` string drives lazy-loaded page switching (`overview` / `exit` / `fragility` / `screener` / `agent`).
```

- In the required `backend/.env` block, add the two optional LLM vars with a note that they default to local Ollama.

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md backend/features/agent/README.md
git commit -m "docs(agent): document the local-LLM Agent tab and Ollama setup" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 8: Manual end-to-end verification

**Files:** None (verification checklist — no code, no commit).

- [ ] **Step 1: Confirm Ollama is serving the model**

Run: `uv run python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:11434/api/tags').status)"`
Expected: `200`. And `ollama list` shows `gemma4:e4b`.

- [ ] **Step 2: Start backend + frontend**

Backend (from `backend/`): `uv run python -m uvicorn main:app --reload`
Frontend (from `frontend/`): `npm run dev`

- [ ] **Step 3: Exercise the Agent tab**

Open the app, log in to Kite, open the **Agent** tab, and ask:
- "What are my holdings?" → expect a `portfolio_holdings` chip + a grounded answer.
- "How diversified am I?" → expect `portfolio_metrics`.
- "Run the momentum screen" → expect `screen_strategy` + top matches.
- "What's the price of INFY?" → expect `quote`.

- [ ] **Step 4: Verify the failure paths**

- Stop Ollama and send a message → expect the "can't reach the model" bubble (not a crash).
- Ask something the tools can't answer → expect a plain "I can't" rather than fabricated numbers.
- Confirm the agent never offers to place/modify orders.

- [ ] **Step 5: Confirm no regression**

The other four tabs and the REST/MCP endpoints behave as before; `uv run pytest -q` is green.

---

## Notes for the implementer

- **`_client` is module-global**; tests monkeypatch `agent_service._client` and `agent_service.tools.dispatch`. Keep them at module scope.
- **OpenAI chat.completions tool format** is the nested `{"type":"function","function":{...}}` shape (not the flat Responses-API shape). Tool-call args arrive as a JSON **string** on `tc.function.arguments` — `dispatch` parses them.
- **Do not** add `thinking`/`effort`/Anthropic params — this is the OpenAI-compatible path.
- Keep `AgentPage` interaction-driven: the only `useEffect` does `scrollIntoView` (no `setState`).
