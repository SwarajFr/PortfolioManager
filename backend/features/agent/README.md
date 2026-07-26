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
   model" message instead of crashing.

## Point at a different provider

Set in `backend/.env` (both optional; shown with their defaults):

    LLM_BASE_URL=http://localhost:11434/v1
    LLM_API_KEY=ollama

Repoint `LLM_BASE_URL` + `LLM_API_KEY` at any OpenAI-compatible endpoint and set
the `agent_settings.model` to that provider's model — no code change.

## Tools (all read-only)

`portfolio_holdings` · `portfolio_metrics` · `screen_strategy` · `quote` — the
same functions the MCP server exposes (`features/mcp/*_tools.py`). No order flow.

## Layout

- `settings.py` — `agent_settings` table: `model`, `max_tokens`,
  `max_tool_iterations`, `system_prompt`.
- `tools.py` — OpenAI-format tool `SCHEMAS` + `dispatch()` into the MCP tools
  (a tool failure returns `{"error": ...}`, never crashes the loop).
- `service.py` — `run_chat(history)`: the manual OpenAI-format tool loop.
- `routes.py` — `POST /api/agent/chat`.
