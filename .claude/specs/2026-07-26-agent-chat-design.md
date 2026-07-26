# In-App "Agent" Chat Tab (local LLM, read-only)

**Date:** 2026-07-26
**Status:** Approved

## Goal

Add a fifth frontend tab, **Agent**, alongside Overview / Exit / Fragility /
Screener: a natural-language chat where the user asks about their portfolio and
an LLM answers by calling the existing read-only analytics as tools. The LLM
runs **locally via Ollama (Gemma 4)** by default — no per-token cost, no cloud
API key, portfolio data never leaves the machine — but the agent is built
**provider-agnostic** against the OpenAI-compatible Chat Completions API, so the
same code points at any OpenAI-compatible endpoint (local or cloud) by changing
two settings.

**Read-only.** The agent's tools are the four read-only analytics tools only —
no order flow, no new analytics. It builds on the MCP tool layer
(`features/mcp/*_tools.py`), reusing those functions so the external MCP server
and the in-app agent share one tool implementation.

## Decisions (confirmed with user)

- **LLM provider:** local **Ollama** running **Gemma 4**, accessed via Ollama's
  **OpenAI-compatible** endpoint (`http://localhost:11434/v1`). Chosen over the
  paid Anthropic API for $0/message, no API key, and local privacy. The Anthropic
  SDK is **not** used.
- **Default model:** `gemma4:e4b` (9.6 GB; laptop/CPU-friendly). A setting — the
  user matches it to whatever they `ollama pull` (`gemma4:e2b|e4b|26b|31b`) or a
  cloud model tag.
- **Provider-agnostic client:** the `openai` Python SDK with a configurable
  `base_url` + `api_key`. Default `base_url=http://localhost:11434/v1`,
  `api_key="ollama"` (Ollama ignores it). Repoint to OpenAI/Groq/Together/etc.
  with one env change — no code change.
- **Response UX:** spinner-then-reply. The frontend POSTs the conversation, the
  backend runs the whole tool-loop to completion, and returns one JSON payload
  (final text + a compact tool-call trace). No SSE for v1.
- **History:** stateless and text-only. The frontend holds `[{role, content}]`
  and sends it each turn; the backend's internal tool_use/tool_result turns are
  not persisted — only the final assistant text is returned and stored. Fresh
  tools run per question.
- **Tools exposed:** `portfolio_holdings`, `portfolio_metrics`, `screen_strategy`,
  `quote` — all read-only. Login/session tools are excluded (the tab is behind
  the app's auth gate).

**Accepted tradeoff:** Gemma 4's tool-calling accuracy (~86%) is below
frontier-model reliability; occasional misfires (wrong tool / a re-ask) are
expected and acceptable for four simple tools. The provider-agnostic design lets
the user upgrade the model anytime.

## Architecture

### Backend — `features/agent/`

```
backend/features/agent/
  __init__.py     empty (convention)
  settings.py     agent_settings table: model, max_tokens, max_tool_iterations, system_prompt
  tools.py        OpenAI-format tool SCHEMAS + DISPATCH → features/mcp/*_tools.py
  service.py      run_chat(history) -> dict  (the manual OpenAI-format tool loop)
  routes.py       POST /api/agent/chat
```

`config.py` gains `LLM_BASE_URL` (default `http://localhost:11434/v1`) and
`LLM_API_KEY` (default `"ollama"`). `main.py` mounts `/api/agent` (+1 router).
`uv add openai`.

### The tool loop — `service.py`

```python
client = OpenAI(base_url=LLM_BASE_URL, api_key=LLM_API_KEY)

def run_chat(history: list[dict]) -> dict:
    conf = settings.get_settings()
    msgs = [{"role": "system", "content": conf["system_prompt"]}, *history]
    trace = []
    try:
        for _ in range(conf["max_tool_iterations"]):
            resp = client.chat.completions.create(
                model=conf["model"], messages=msgs,
                tools=tools.SCHEMAS, tool_choice="auto",
                max_tokens=conf["max_tokens"],
            )
            msg = resp.choices[0].message
            msgs.append(_assistant_dict(msg))          # content + tool_calls
            if not msg.tool_calls:
                return {"reply": msg.content or "", "tool_calls": trace, "stop": "done"}
            for tc in msg.tool_calls:
                result = tools.dispatch(tc.function.name, tc.function.arguments)
                trace.append({"name": tc.function.name})
                msgs.append({"role": "tool", "tool_call_id": tc.id,
                             "content": json.dumps(result)})
        return {"reply": "(stopped: tool-call limit reached)", "tool_calls": trace, "stop": "max_iters"}
    except openai.APIConnectionError:
        return {"error": "llm_unreachable",
                "message": f"Can't reach the local model at {LLM_BASE_URL}. Is Ollama running?"}
    except openai.OpenAIError as e:
        return {"error": "agent_error", "message": str(e)}
```

- No `thinking`/`effort` params — those are Anthropic-specific; Gemma reasons
  internally.
- Non-streaming (`base_url` is localhost → no cloud HTTP-timeout concern). Server-
  side streaming can be added later behind the same route without a frontend change.
- `_assistant_dict(msg)` rebuilds the assistant turn as a plain dict (role,
  content, and `tool_calls` as `[{id, type:"function", function:{name, arguments}}]`)
  so the message history stays serializable and mock-testable.

### Tools — `tools.py` (reuse, no duplication)

`SCHEMAS` is the OpenAI function-tool list; `dispatch(name, arguments_json)`
parses the JSON args, routes to the matching `features/mcp` function, and wraps
the call so any exception returns `{"error": str(e)}` (a tool failure never kills
the loop).

| Tool (`function.name`) | Params | → |
|---|---|---|
| `portfolio_holdings` | — | `features.mcp.portfolio_tools.portfolio_holdings` |
| `portfolio_metrics` | — | `features.mcp.fragility_tools.portfolio_metrics` |
| `screen_strategy` | `name` (req), `universe?`, `limit?` | `features.mcp.screener_tools.screen_strategy` |
| `quote` | `symbols` (req, string[]) | `features.mcp.market_tools.quote` |

A Kite-backed tool that returns the `auth_required` payload is passed straight
through; the agent relays "log in" to the user rather than erroring.

### Settings — `agent_settings` table

`model: "gemma4:e4b"` · `max_tokens: 8192` · `max_tool_iterations: 8` ·
`system_prompt`: a concise, explicit read-only-analyst prompt (small local models
follow terse, direct instructions best). The prompt states: use the tools rather
than guess; never fabricate numbers; report figures the tools return and note when
data is stale/unavailable; you **cannot place orders**; if a tool result says
`auth_required`, tell the user to log in.

### Frontend — `features/agent/`

- `constants/navigation.js` +1 (`agent` / "Agent" / eyebrow "Assistant");
  `app/App.jsx` lazy `PAGES.agent`; `services/agentService.js` →
  `postChat(messages)` = `apiClient.post("/agent/chat", { messages })`.
- `features/agent/AgentPage.jsx` — chat UI. Local `useState`: `messages`
  (`[{role, content, toolCalls?}]`), `input`, `pending`, `error`. **All state
  changes happen in the submit handler** (interaction-driven), so there is no
  `useEffect`-setState — this sidesteps the `react-hooks/set-state-in-effect`
  lint entirely and `useAsyncData` is not used here.
- On submit: append the user message, set `pending`, POST the full text-only
  history, append the returned assistant reply (+ its `toolCalls` chip row).
  Pending shows a "thinking…" assistant bubble; errors render inline.
- Reuses `Card` / `Button` / theme vars; the chat surface gets a **frontend-design**
  pass at build time. Does **not** touch Overview / Exit / Fragility / Screener.

## Error handling

- Ollama not running / unreachable → `{error: "llm_unreachable", message}` with the
  base_url and an "Is Ollama running?" hint.
- Model not pulled / other OpenAI-API error → `{error: "agent_error", message}`.
- Tool raises → `{error}` returned as that tool's result; agent relays it.
- Kite not authenticated → tool returns `auth_required`; agent relays "log in".
- Tool-call iteration cap hit → returns partial text + a `stop: "max_iters"` note.

## Dependencies

`uv add openai` (backend). No frontend deps (uses the existing `apiClient`/axios).

## Files changed vs created

- **Created (backend):** `features/agent/{__init__,settings,tools,service,routes}.py`,
  `tests/test_agent.py`.
- **Changed (backend):** `config.py` (+`LLM_BASE_URL`, +`LLM_API_KEY`), `main.py`
  (+1 router), `pyproject.toml`/`uv.lock` (`openai`), CLAUDE.md.
- **Created (frontend):** `services/agentService.js`,
  `features/agent/AgentPage.jsx` (+ small presentational components as needed).
- **Changed (frontend):** `constants/navigation.js` (+1), `app/App.jsx` (+1 lazy page).
- **No changes** to portfolio/exit/fragility/screener/mcp compute or engines.

## Tests (pytest, `uv run`; the `openai` client is mocked — no model/network)

- `run_chat`: fake completion with no `tool_calls` → `reply` extracted, empty trace.
- `run_chat`: fake returns one `tool_calls` message then a final message →
  `dispatch` called with parsed args, a `{"role": "tool", ...}` result appended,
  `tool_calls` trace recorded, final `reply` returned.
- `run_chat`: every turn returns `tool_calls` → stops at `max_tool_iterations`
  with `stop: "max_iters"`.
- `run_chat`: client raises `openai.APIConnectionError` → `{error: "llm_unreachable"}`.
- `tools.dispatch`: known name routes to the right callable; unknown name →
  `{"error": ...}`; a wrapped-tool exception → `{"error": ...}`; JSON args parsed.
- Route: missing/empty `messages` → 400.
- Frontend: `npm run lint` + `npm run build` pass.

## Prerequisite & deliverable

User-side setup (documented in CLAUDE.md + `features/agent/README.md`):
1. Install Ollama.
2. `ollama pull gemma4:e4b` (9.6 GB) — or another size/tag; set `model` to match.
3. Ollama serves the OpenAI-compatible API at `http://localhost:11434/v1` — the
   agent's default. To use a cloud OpenAI-compatible endpoint instead, set
   `LLM_BASE_URL`, `LLM_API_KEY`, and the `model` setting.

## Success criteria

- `uv run pytest` passes (backend) with the `openai` client fully mocked.
- With Ollama running `gemma4:e4b`, the Agent tab answers a portfolio question by
  calling the tools (e.g. "what are my riskiest holdings?" → `portfolio_metrics` +
  `portfolio_holdings` → a grounded answer), showing the tool-call trace.
- No Anthropic key and no cloud calls in the default configuration; portfolio data
  stays on the machine.
- Repointing `LLM_BASE_URL` + `model` drives the same tab against any
  OpenAI-compatible endpoint with no code change.
- Existing REST endpoints, the MCP server, and the other four tabs behave exactly
  as before.
