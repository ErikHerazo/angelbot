from types import SimpleNamespace

from app.adapters.outbound.claude_foundry.claude_foundry_llm_adapter import ClaudeFoundryLLMAdapter


def _text_block(text):
    return SimpleNamespace(type="text", text=text)


def _tool_use_block(id_, name, input_):
    return SimpleNamespace(type="tool_use", id=id_, name=name, input=input_)


def _response(*blocks, stop_reason="end_turn"):
    return SimpleNamespace(content=list(blocks), stop_reason=stop_reason)


def _make_adapter(response):
    captured = {}

    async def fake_messages_create_fn(**kwargs):
        captured.update(kwargs)
        return response

    adapter = ClaudeFoundryLLMAdapter(deployment="claude-sonnet-5-clinyq", messages_create_fn=fake_messages_create_fn)
    return adapter, captured


async def test_merges_system_messages_and_returns_text():
    adapter, captured = _make_adapter(_response(_text_block("hola")))

    result = await adapter.complete(
        messages=[
            {"role": "system", "content": "Eres un asistente."},
            {"role": "user", "content": "hi"},
            {"role": "system", "content": "Responde en español."},
        ]
    )

    assert result == {"content": "hola", "tool_calls": None}
    assert captured["system"] == "Eres un asistente.\n\nResponde en español."
    assert captured["messages"] == [{"role": "user", "content": "hi"}]


async def test_forced_tool_choice_and_tool_schema_translation():
    adapter, captured = _make_adapter(
        _response(_tool_use_block("call_1", "classify_intent", {"intent": "info_general"}))
    )

    result = await adapter.complete(
        messages=[{"role": "user", "content": "hola"}],
        tools=[{"type": "function", "function": {"name": "classify_intent", "description": "d", "parameters": {"type": "object"}}}],
        tool_choice={"type": "function", "function": {"name": "classify_intent"}},
    )

    assert result == {
        "content": None,
        "tool_calls": [{"id": "call_1", "name": "classify_intent", "arguments": {"intent": "info_general"}}],
    }
    assert captured["tools"] == [{"name": "classify_intent", "description": "d", "input_schema": {"type": "object"}}]
    assert captured["tool_choice"] == {"type": "tool", "name": "classify_intent"}


async def test_assistant_tool_calls_and_tool_result_round_trip():
    adapter, captured = _make_adapter(_response(_text_block("el precio es 5000")))

    messages = [
        {"role": "system", "content": "sistema"},
        {"role": "user", "content": "cuanto cuesta"},
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {"id": "t1", "type": "function", "function": {"name": "search_price_catalog", "arguments": '{"query": "nariz"}'}}
            ],
        },
        {"role": "tool", "tool_call_id": "t1", "content": '[{"procedure_name": "RINOPLASTIA"}]'},
    ]

    await adapter.complete(messages=messages)

    assert captured["messages"] == [
        {"role": "user", "content": "cuanto cuesta"},
        {
            "role": "assistant",
            "content": [{"type": "tool_use", "id": "t1", "name": "search_price_catalog", "input": {"query": "nariz"}}],
        },
        {
            "role": "user",
            "content": [{"type": "tool_result", "tool_use_id": "t1", "content": '[{"procedure_name": "RINOPLASTIA"}]'}],
        },
    ]


async def test_tool_choice_auto_and_none_translation():
    adapter, captured = _make_adapter(_response(_text_block("ok")))

    await adapter.complete(messages=[{"role": "user", "content": "hi"}], tool_choice="auto")
    assert captured["tool_choice"] == {"type": "auto"}

    await adapter.complete(messages=[{"role": "user", "content": "hi"}], tool_choice="none")
    assert captured["tool_choice"] == {"type": "none"}
