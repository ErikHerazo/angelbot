from app.adapters.outbound.azure_openai.azure_openai_conversation_engine_adapter import (
    AzureOpenAIConversationEngineAdapter,
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


async def test_fetches_history_and_passes_it_to_rag_runner_for_normal_channel():
    history = [{"role": "user", "content": "hola"}]
    fake_history_port = FakeConversationHistory(history=history)
    captured = {}

    async def fake_rag_runner(**kwargs):
        captured.update(kwargs)
        return "respuesta generada"

    adapter = AzureOpenAIConversationEngineAdapter(
        conversation_history=fake_history_port,
        rag_runner=fake_rag_runner,
    )

    answer = await adapter.generate_reply(
        tenant_id="agb",
        session_id="sess-1",
        user_question="hola",
        channel="website",
        visitor_language="es",
    )

    assert answer == "respuesta generada"
    assert fake_history_port.get_history_calls == [("agb", "sess-1")]
    assert captured["history"] == history
    assert captured["session_id"] == "sess-1"
    assert captured["channel"] == "website"
    assert captured["visitor_language"] == "es"


async def test_skips_history_fetch_for_flow_channel():
    fake_history_port = FakeConversationHistory()
    captured = {}

    async def fake_rag_runner(**kwargs):
        captured.update(kwargs)
        return "respuesta sintetica"

    adapter = AzureOpenAIConversationEngineAdapter(
        conversation_history=fake_history_port,
        rag_runner=fake_rag_runner,
    )

    answer = await adapter.generate_reply(
        tenant_id="agb",
        session_id="sess-1",
        user_question="lead question",
        channel="flow",
    )

    assert answer == "respuesta sintetica"
    assert fake_history_port.get_history_calls == []
    assert captured["history"] is None


async def test_always_includes_the_dependency_free_flag_tool_overrides():
    captured = {}

    async def fake_rag_runner(**kwargs):
        captured.update(kwargs)
        return "ok"

    adapter = AzureOpenAIConversationEngineAdapter(
        conversation_history=FakeConversationHistory(),
        rag_runner=fake_rag_runner,
    )

    await adapter.generate_reply(
        tenant_id="agb", session_id="sess-1", user_question="hola", channel="website"
    )

    assert "flag_revision_or_reintervention_price_request" in captured["tool_overrides"]
    assert "flag_emotional_distress" in captured["tool_overrides"]
    assert "flag_minor_patient" in captured["tool_overrides"]
    assert "is_customer_service_available" not in captured["tool_overrides"]
    assert "procedures_and_treatments_price_list" not in captured["tool_overrides"]


async def test_wires_check_business_availability_tool_bound_to_tenant():
    class FakeCheckBusinessAvailability:
        def __init__(self):
            self.calls = []

        async def execute(self, tenant_id):
            self.calls.append(tenant_id)
            return True

    fake_use_case = FakeCheckBusinessAvailability()
    captured = {}

    async def fake_rag_runner(**kwargs):
        captured.update(kwargs)
        return "ok"

    adapter = AzureOpenAIConversationEngineAdapter(
        conversation_history=FakeConversationHistory(),
        rag_runner=fake_rag_runner,
        check_business_availability=fake_use_case,
    )

    await adapter.generate_reply(
        tenant_id="agb", session_id="sess-1", user_question="hola", channel="website"
    )

    tool = captured["tool_overrides"]["is_customer_service_available"]
    await tool(input="")

    assert fake_use_case.calls == ["agb"]


async def test_wires_lookup_procedure_price_tool_via_per_tenant_factory():
    class FakeLookupProcedurePrice:
        def __init__(self):
            self.calls = []

        async def execute(self, tenant_id, name_surgery_or_treatment):
            self.calls.append((tenant_id, name_surgery_or_treatment))
            return []

    fake_use_case = FakeLookupProcedurePrice()
    factory_calls = []

    async def fake_get_lookup_procedure_price(tenant_id):
        factory_calls.append(tenant_id)
        return fake_use_case

    captured = {}

    async def fake_rag_runner(**kwargs):
        captured.update(kwargs)
        return "ok"

    adapter = AzureOpenAIConversationEngineAdapter(
        conversation_history=FakeConversationHistory(),
        rag_runner=fake_rag_runner,
        get_lookup_procedure_price=fake_get_lookup_procedure_price,
    )

    await adapter.generate_reply(
        tenant_id="agb", session_id="sess-1", user_question="hola", channel="website"
    )

    assert factory_calls == ["agb"]

    tool = captured["tool_overrides"]["procedures_and_treatments_price_list"]
    await tool(name_surgery_or_treatment="rinoplastia")

    assert fake_use_case.calls == [("agb", "rinoplastia")]


async def test_base_prompt_override_is_none_without_prompt_config():
    captured = {}

    async def fake_rag_runner(**kwargs):
        captured.update(kwargs)
        return "ok"

    adapter = AzureOpenAIConversationEngineAdapter(
        conversation_history=FakeConversationHistory(),
        rag_runner=fake_rag_runner,
    )

    await adapter.generate_reply(
        tenant_id="agb", session_id="sess-1", user_question="hola", channel="website"
    )

    assert captured["base_prompt_override"] is None


async def test_fetches_base_prompt_for_tenant_and_channel_when_prompt_config_given():
    class FakePromptConfig:
        def __init__(self):
            self.calls = []

        async def get_base_prompt(self, tenant_id, channel):
            self.calls.append((tenant_id, channel))
            return "prompt de agb para website"

    fake_prompt_config = FakePromptConfig()
    captured = {}

    async def fake_rag_runner(**kwargs):
        captured.update(kwargs)
        return "ok"

    adapter = AzureOpenAIConversationEngineAdapter(
        conversation_history=FakeConversationHistory(),
        rag_runner=fake_rag_runner,
        prompt_config=fake_prompt_config,
    )

    await adapter.generate_reply(
        tenant_id="agb", session_id="sess-1", user_question="hola", channel="website"
    )

    assert fake_prompt_config.calls == [("agb", "website")]
    assert captured["base_prompt_override"] == "prompt de agb para website"


async def test_still_calls_rag_runner_when_lookup_procedure_price_factory_fails():
    async def failing_factory(tenant_id):
        raise KeyError("secret not found")

    captured = {}

    async def fake_rag_runner(**kwargs):
        captured.update(kwargs)
        return "respuesta a pesar del fallo"

    adapter = AzureOpenAIConversationEngineAdapter(
        conversation_history=FakeConversationHistory(),
        rag_runner=fake_rag_runner,
        get_lookup_procedure_price=failing_factory,
    )

    answer = await adapter.generate_reply(
        tenant_id="agb", session_id="sess-1", user_question="hola", channel="website"
    )

    assert answer == "respuesta a pesar del fallo"
    assert "procedures_and_treatments_price_list" not in captured["tool_overrides"]
    # las tools de señal, que no dependen de nada, siguen presentes
    assert "flag_revision_or_reintervention_price_request" in captured["tool_overrides"]


async def test_still_calls_rag_runner_when_prompt_config_fails():
    class FailingPromptConfig:
        async def get_base_prompt(self, tenant_id, channel):
            raise FileNotFoundError("prompt file missing")

    captured = {}

    async def fake_rag_runner(**kwargs):
        captured.update(kwargs)
        return "respuesta con prompt legacy"

    adapter = AzureOpenAIConversationEngineAdapter(
        conversation_history=FakeConversationHistory(),
        rag_runner=fake_rag_runner,
        prompt_config=FailingPromptConfig(),
    )

    answer = await adapter.generate_reply(
        tenant_id="agb", session_id="sess-1", user_question="hola", channel="website"
    )

    assert answer == "respuesta con prompt legacy"
    assert captured["base_prompt_override"] is None
