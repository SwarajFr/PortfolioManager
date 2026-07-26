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
