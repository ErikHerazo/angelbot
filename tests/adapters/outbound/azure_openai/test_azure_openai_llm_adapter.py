from types import SimpleNamespace

import httpx
import pytest
from openai import RateLimitError

from app.adapters.outbound.azure_openai.azure_openai_llm_adapter import AzureOpenAILLMAdapter


def _completion_response(*, content=None, tool_calls=None):
    message = SimpleNamespace(content=content, tool_calls=tool_calls)
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def _tool_call(id_: str, name: str, arguments: str):
    return SimpleNamespace(id=id_, function=SimpleNamespace(name=name, arguments=arguments))


class FakeClient:
    def __init__(self, response=None, error=None):
        self._response = response
        self._error = error
        self.calls: list[dict] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    async def _create(self, **kwargs):
        self.calls.append(kwargs)
        if self._error:
            raise self._error
        return self._response


def _make_adapter(primary: FakeClient, secondary: FakeClient) -> AzureOpenAILLMAdapter:
    return AzureOpenAILLMAdapter(
        primary_client=primary,
        secondary_client=secondary,
        deployment_primary="primary-deployment",
        deployment_secondary="secondary-deployment",
        temperature=0.2,
        max_tokens=1200,
    )


async def test_complete_uses_primary_by_default():
    primary = FakeClient(response=_completion_response(content="hola"))
    secondary = FakeClient()
    adapter = _make_adapter(primary, secondary)

    result = await adapter.complete(messages=[{"role": "user", "content": "hi"}])

    assert result == {"content": "hola", "tool_calls": None}
    assert primary.calls[0]["model"] == "primary-deployment"
    assert secondary.calls == []


async def test_complete_parses_tool_calls():
    response = _completion_response(tool_calls=[_tool_call("call_1", "search", '{"query": "nariz"}')])
    primary = FakeClient(response=response)
    secondary = FakeClient()
    adapter = _make_adapter(primary, secondary)

    result = await adapter.complete(messages=[])

    assert result == {"content": None, "tool_calls": [{"id": "call_1", "name": "search", "arguments": {"query": "nariz"}}]}


async def test_rate_limit_fails_over_to_secondary_and_cools_down_primary():
    request = httpx.Request("POST", "https://example.com")
    response = httpx.Response(429, headers={"retry-after": "5"}, request=request)
    error = RateLimitError("rate limited", response=response, body=None)

    primary = FakeClient(error=error)
    secondary = FakeClient(response=_completion_response(content="from secondary"))
    adapter = _make_adapter(primary, secondary)

    result = await adapter.complete(messages=[])

    assert result["content"] == "from secondary"
    assert secondary.calls[0]["model"] == "secondary-deployment"

    # Primary is now in cooldown -- a second call should skip straight to secondary.
    secondary.calls.clear()
    result_2 = await adapter.complete(messages=[])
    assert result_2["content"] == "from secondary"
    assert len(primary.calls) == 1  # not retried
    assert len(secondary.calls) == 1
