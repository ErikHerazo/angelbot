from app.adapters.outbound.claude_foundry.claude_foundry_conversation_engine_adapter import (
    ClaudeFoundryConversationEngineAdapter,
)


class FakeConversationHistory:
    def __init__(self, history=None):
        self._history = history if history is not None else []
        self.get_history_calls = []

    async def get_history(self, tenant_id, session_id):
        self.get_history_calls.append((tenant_id, session_id))
        return self._history

    async def append_turn(self, **kwargs):
        pass


class FakePromptConfig:
    def __init__(self, prompt="Responde en {reply_language}."):
        self._prompt = prompt
        self.calls = []

    async def get_base_prompt(self, tenant_id, channel):
        self.calls.append((tenant_id, channel))
        return self._prompt


class FakeBlock:
    def __init__(self, type, **kwargs):
        self.type = type
        for k, v in kwargs.items():
            setattr(self, k, v)


class FakeResponse:
    def __init__(self, content, stop_reason="end_turn"):
        self.content = content
        self.stop_reason = stop_reason


def text_response(text, stop_reason="end_turn"):
    return FakeResponse([FakeBlock("text", text=text)], stop_reason=stop_reason)


def tool_use_response(name, input, tool_use_id="tu_1"):
    return FakeResponse(
        [FakeBlock("tool_use", id=tool_use_id, name=name, input=input)],
        stop_reason="tool_use",
    )


def _make_adapter(
    *,
    history=None,
    prompt="Responde en {reply_language}.",
    search_price_list=None,
    search_main_index=None,
    translate_fn=None,
    resolve_reply_language_fn=None,
    messages_create_fn=None,
    check_business_availability=None,
    get_lookup_procedure_price=None,
):
    async def default_resolve_reply_language(session_id, current_message=None, language_hint=None, history=None):
        return "es"

    async def default_search_price_list(query):
        return []

    async def default_search_main_index(query):
        return []

    async def default_messages_create_fn(*, system, messages, tools):
        return text_response("respuesta de claude")

    return ClaudeFoundryConversationEngineAdapter(
        conversation_history=FakeConversationHistory(history=history),
        prompt_config=FakePromptConfig(prompt=prompt),
        search_price_list=search_price_list or default_search_price_list,
        search_main_index=search_main_index or default_search_main_index,
        translate_fn=translate_fn,
        resolve_reply_language_fn=resolve_reply_language_fn or default_resolve_reply_language,
        messages_create_fn=messages_create_fn or default_messages_create_fn,
        check_business_availability=check_business_availability,
        get_lookup_procedure_price=get_lookup_procedure_price,
    )


async def test_fetches_history_and_includes_it_in_messages_for_normal_channel():
    history = [{"role": "user", "content": "hola"}, {"role": "assistant", "content": "hola, en que ayudo?"}]
    captured = {}

    async def fake_messages_create_fn(*, system, messages, tools):
        captured["system"] = system
        captured["messages"] = messages
        return text_response("respuesta")

    adapter = _make_adapter(history=history, messages_create_fn=fake_messages_create_fn)

    answer = await adapter.generate_reply(
        tenant_id="agb", session_id="sess-1", user_question="cuanto cuesta una rinoplastia", channel="website"
    )

    assert answer == "respuesta"
    assert captured["messages"][0] == {"role": "user", "content": "hola"}
    assert captured["messages"][1] == {"role": "assistant", "content": "hola, en que ayudo?"}
    assert captured["messages"][-1]["role"] == "user"
    assert "cuanto cuesta una rinoplastia" in captured["messages"][-1]["content"]


async def test_skips_history_fetch_for_flow_channel():
    history_port = FakeConversationHistory()
    adapter = _make_adapter()
    adapter._conversation_history = history_port

    await adapter.generate_reply(
        tenant_id="agb", session_id="sess-1", user_question="lead question", channel="flow"
    )

    assert history_port.get_history_calls == []


async def test_formats_prompt_with_resolved_reply_language():
    captured = {}

    async def fake_resolve_reply_language(session_id, current_message=None, language_hint=None, history=None):
        return "en"

    async def fake_messages_create_fn(*, system, messages, tools):
        captured["system"] = system
        return text_response("ok")

    adapter = _make_adapter(
        prompt="Reply in {reply_language}.",
        resolve_reply_language_fn=fake_resolve_reply_language,
        messages_create_fn=fake_messages_create_fn,
    )

    await adapter.generate_reply(
        tenant_id="agb", session_id="sess-1", user_question="hi", channel="website"
    )

    assert captured["system"] == "Reply in Inglés."


async def test_translates_question_before_searching_when_reply_language_is_not_spanish():
    translate_calls = []
    search_calls = []

    async def fake_translate(text, to_lang, from_lang=None):
        translate_calls.append((text, to_lang))
        return "pregunta en español"

    async def fake_resolve_reply_language(session_id, current_message=None, language_hint=None, history=None):
        return "en"

    async def fake_search_main_index(query):
        search_calls.append(query)
        return []

    adapter = _make_adapter(
        translate_fn=fake_translate,
        resolve_reply_language_fn=fake_resolve_reply_language,
        search_main_index=fake_search_main_index,
    )

    await adapter.generate_reply(
        tenant_id="agb", session_id="sess-1", user_question="how much is a rhinoplasty", channel="website"
    )

    assert translate_calls == [("how much is a rhinoplasty", "es")]
    assert search_calls == ["pregunta en español"]


async def test_injects_main_index_chunks_into_the_user_message():
    captured = {}

    async def fake_search_main_index(query):
        return ["fragmento relevante sobre rinoplastia"]

    async def fake_messages_create_fn(*, system, messages, tools):
        captured["messages"] = messages
        return text_response("ok")

    adapter = _make_adapter(
        search_main_index=fake_search_main_index,
        messages_create_fn=fake_messages_create_fn,
    )

    await adapter.generate_reply(
        tenant_id="agb", session_id="sess-1", user_question="rinoplastia", channel="website"
    )

    user_content = captured["messages"][-1]["content"]
    assert "FRAGMENTOS RELEVANTES" in user_content
    assert "fragmento relevante sobre rinoplastia" in user_content


async def test_falls_back_to_text_price_search_when_no_price_tool_wired():
    captured = {}

    async def fake_search_price_list(query):
        return [{"procedure_name": "rinoplastia", "price_range_eur": "7500-8500"}]

    async def fake_messages_create_fn(*, system, messages, tools):
        captured["messages"] = messages
        captured["tools"] = tools
        return text_response("ok")

    adapter = _make_adapter(
        search_price_list=fake_search_price_list,
        messages_create_fn=fake_messages_create_fn,
    )

    await adapter.generate_reply(
        tenant_id="agb", session_id="sess-1", user_question="rinoplastia", channel="website"
    )

    user_content = captured["messages"][-1]["content"]
    assert "PRECIOS ENCONTRADOS" in user_content
    assert "rinoplastia" in user_content
    assert captured["tools"] == []


async def test_still_returns_answer_when_main_index_search_fails():
    async def failing_search_main_index(query):
        raise RuntimeError("search down")

    adapter = _make_adapter(search_main_index=failing_search_main_index)

    answer = await adapter.generate_reply(
        tenant_id="agb", session_id="sess-1", user_question="hola", channel="website"
    )

    assert answer == "respuesta de claude"


# --- Tool-calling: is_customer_service_available / procedures_and_treatments_price_list ---


async def test_wires_check_business_availability_tool_and_omits_text_price_search():
    class FakeCheckBusinessAvailability:
        def __init__(self):
            self.calls = []

        async def execute(self, tenant_id):
            self.calls.append(tenant_id)
            return True

    fake_use_case = FakeCheckBusinessAvailability()
    captured = {}

    async def fake_messages_create_fn(*, system, messages, tools):
        captured["tools"] = tools
        return text_response("ok")

    adapter = _make_adapter(
        check_business_availability=fake_use_case,
        messages_create_fn=fake_messages_create_fn,
    )

    await adapter.generate_reply(
        tenant_id="agb", session_id="sess-1", user_question="hola", channel="website"
    )

    tool_names = {t["name"] for t in captured["tools"]}
    assert tool_names == {"is_customer_service_available"}


async def test_price_tool_wired_via_per_tenant_factory_and_disables_text_price_search():
    class FakeLookupProcedurePrice:
        def __init__(self):
            self.calls = []

        async def execute(self, tenant_id, name_surgery_or_treatment):
            self.calls.append((tenant_id, name_surgery_or_treatment))
            return []

    fake_use_case = FakeLookupProcedurePrice()
    factory_calls = []
    text_search_calls = []

    async def fake_get_lookup_procedure_price(tenant_id):
        factory_calls.append(tenant_id)
        return fake_use_case

    async def fake_search_price_list(query):
        text_search_calls.append(query)
        return []

    captured = {}

    async def fake_messages_create_fn(*, system, messages, tools):
        captured["tools"] = tools
        return text_response("ok")

    adapter = _make_adapter(
        get_lookup_procedure_price=fake_get_lookup_procedure_price,
        search_price_list=fake_search_price_list,
        messages_create_fn=fake_messages_create_fn,
    )

    await adapter.generate_reply(
        tenant_id="agb", session_id="sess-1", user_question="hola", channel="website"
    )

    assert factory_calls == ["agb"]
    assert text_search_calls == []  # tool real disponible -> no se usa el retrieval de texto
    tool_names = {t["name"] for t in captured["tools"]}
    assert tool_names == {"procedures_and_treatments_price_list"}


async def test_executes_tool_use_and_feeds_result_back_for_final_answer():
    class FakeLookupProcedurePrice:
        async def execute(self, tenant_id, name_surgery_or_treatment):
            return []

    calls = []

    async def fake_get_lookup_procedure_price(tenant_id):
        return FakeLookupProcedurePrice()

    responses = [
        tool_use_response(
            "procedures_and_treatments_price_list",
            {"name_surgery_or_treatment": "rinoplastia"},
            tool_use_id="tu_42",
        ),
        text_response("La rinoplastia cuesta entre 7500 y 8500 euros."),
    ]

    async def fake_messages_create_fn(*, system, messages, tools):
        calls.append(messages)
        return responses.pop(0)

    adapter = _make_adapter(
        get_lookup_procedure_price=fake_get_lookup_procedure_price,
        messages_create_fn=fake_messages_create_fn,
    )

    answer = await adapter.generate_reply(
        tenant_id="agb", session_id="sess-1", user_question="cuanto cuesta la rinoplastia", channel="website"
    )

    assert answer == "La rinoplastia cuesta entre 7500 y 8500 euros."
    assert len(calls) == 2
    # segunda llamada debe incluir el tool_result correlacionado por tool_use_id
    second_call_messages = calls[1]
    tool_result_message = second_call_messages[-1]
    assert tool_result_message["role"] == "user"
    assert tool_result_message["content"][0]["type"] == "tool_result"
    assert tool_result_message["content"][0]["tool_use_id"] == "tu_42"


async def test_unknown_tool_name_returns_error_result_without_crashing():
    responses = [
        tool_use_response("some_unwired_tool", {}, tool_use_id="tu_1"),
        text_response("respuesta final"),
    ]

    async def fake_messages_create_fn(*, system, messages, tools):
        return responses.pop(0)

    adapter = _make_adapter(messages_create_fn=fake_messages_create_fn)

    answer = await adapter.generate_reply(
        tenant_id="agb", session_id="sess-1", user_question="hola", channel="website"
    )

    assert answer == "respuesta final"


async def test_stops_after_max_iterations_and_still_returns_best_effort_answer():
    async def fake_check_availability(tenant_id):
        return True

    class FakeCheckBusinessAvailability:
        async def execute(self, tenant_id):
            return True

    call_count = {"n": 0}

    async def fake_messages_create_fn(*, system, messages, tools):
        call_count["n"] += 1
        # Siempre pide la misma tool -- nunca converge a una respuesta final.
        return tool_use_response("is_customer_service_available", {"input": ""}, tool_use_id=f"tu_{call_count['n']}")

    adapter = _make_adapter(
        check_business_availability=FakeCheckBusinessAvailability(),
        messages_create_fn=fake_messages_create_fn,
    )

    answer = await adapter.generate_reply(
        tenant_id="agb", session_id="sess-1", user_question="hola", channel="website"
    )

    assert answer == ""
    assert call_count["n"] == 4  # MAX_TOOL_ITERATIONS
