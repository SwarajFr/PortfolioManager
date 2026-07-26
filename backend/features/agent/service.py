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

    ``history`` is the text-only [{role, content}] conversation from the client.
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
