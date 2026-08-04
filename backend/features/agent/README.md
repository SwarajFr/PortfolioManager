# Agent (in-app chat, local LLM, read-only)

A chat tab where the user asks what to sell, top up or buy, and a local LLM
answers by calling the advisor tools. Provider-agnostic: built on the
OpenAI-compatible Chat Completions API, defaulting to a local Ollama model.

## The model does not do the analysis

The ranking happens in Python (`features/advisor/`). Each tool returns candidates
whose reasons are already written out, and the system prompt's job is to stop the
model doing arithmetic of its own — a small local model comparing numbers in a
holdings table is exactly where hallucinated advice comes from. So the prompt is
mostly prohibitions: never calculate a number, never name a ticker the tools did
not return, report an empty result as empty.

This is also why the tab works on a 9 GB local model at all.

## Prerequisite — run a local model with Ollama

1. Install Ollama.
2. Pull a Gemma 4 model: `ollama pull gemma4:e4b` (9.6 GB; laptop/CPU-friendly).
   Other sizes: `gemma4:e2b` (7.2 GB), `gemma4:26b`, `gemma4:31b` — set the
   `model` setting to match what you pull.
3. Ollama serves the OpenAI-compatible API at `http://localhost:11434/v1` — the
   agent's default. If it isn't running, the tab shows a clear "can't reach the
   model" message instead of crashing.

## Point at a different provider

Set in `backend/.env` (both optional; shown with their defaults):

    LLM_BASE_URL=http://localhost:11434/v1
    LLM_API_KEY=ollama

Repoint `LLM_BASE_URL` + `LLM_API_KEY` at any OpenAI-compatible endpoint and set
the `agent_settings.model` to that provider's model — no code change. Worth doing
if narration quality disappoints: the tools stay identical, only the prose improves.

## Tools (all read-only)

A deliberate subset of what MCP exposes — every extra tool is one more chance for
a small model to pick the wrong one.

`portfolio_actions` · `buy_ideas` · `portfolio_holdings` · `advice_history` ·
`investor_profile`

The model extracts the horizon and target from the question and passes them as
arguments ("what can I buy for 5% in 2 months" → `horizon_months=2,
target_gain_pct=5`). Nothing is hardcoded; omitted arguments fall back to the
user's saved profile. No order flow.

## Memory

- **Conversation** — held in the frontend's `chatStore.js`, outside React so it
  survives switching tabs. Not persisted across a reload.
- **Investor profile** — `advisor_settings`, edited in the Profile drawer, and
  summarised into the system prompt on every turn by `_profile_line()`.
- **Recommendation journal** — written by the advisor service, read back via
  `advice_history`. See `features/advisor/README.md`.

## Layout

- `settings.py` — `agent_settings` table: `model`, `max_tokens`,
  `max_tool_iterations`, `system_prompt`. Unscoped: it configures the LLM, not
  the portfolio.
- `tools.py` — OpenAI-format tool `SCHEMAS` + `dispatch()` into the MCP tools
  (a tool failure returns `{"error": ...}`, never crashes the loop).
- `service.py` — `run_chat(history)`: the manual OpenAI-format tool loop, plus
  the investor-profile line appended to the system prompt.
- `routes.py` — `POST /api/agent/chat`.
