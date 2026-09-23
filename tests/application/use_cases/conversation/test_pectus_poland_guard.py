from app.application.use_cases.conversation.pectus_poland_guard import (
    make_pectus_poland_guard_node,
    route_after_pectus_poland_guard,
)


class FakeDisambiguationConfig:
    def __init__(self, reply: str):
        self._reply = reply
        self.calls = []

    async def get_reply(self, tenant_id):
        self.calls.append(tenant_id)
        return self._reply


def _state(translated_query=None, user_question="hola"):
    return {"tenant_id": "agb", "translated_query": translated_query, "user_question": user_question}


async def test_triggers_on_ambiguous_sunken_chest_mention_without_disambiguating_signal():
    config = FakeDisambiguationConfig("¿centro del pecho o un lado?")
    node = make_pectus_poland_guard_node(config)

    result = await node(_state(translated_query="tengo el pecho hundido de un lado"))

    assert result == {"pectus_poland_guard_triggered": True, "final_answer": "¿centro del pecho o un lado?"}
    assert config.calls == ["agb"]


async def test_does_not_trigger_when_message_already_names_the_central_sternal_signal():
    config = FakeDisambiguationConfig("¿centro del pecho o un lado?")
    node = make_pectus_poland_guard_node(config)

    result = await node(_state(translated_query="tengo el esternón hundido en el centro del pecho"))

    assert result == {"pectus_poland_guard_triggered": False}
    assert config.calls == []


async def test_does_not_trigger_when_message_already_names_the_congenital_muscular_signal():
    config = FakeDisambiguationConfig("¿centro del pecho o un lado?")
    node = make_pectus_poland_guard_node(config)

    result = await node(
        _state(translated_query="tengo el pecho hundido de un lado, es de nacimiento por falta de músculo")
    )

    assert result == {"pectus_poland_guard_triggered": False}
    assert config.calls == []


async def test_does_not_trigger_for_unrelated_questions():
    config = FakeDisambiguationConfig("¿centro del pecho o un lado?")
    node = make_pectus_poland_guard_node(config)

    result = await node(_state(translated_query="cuanto cuesta una rinoplastia"))

    assert result == {"pectus_poland_guard_triggered": False}
    assert config.calls == []


async def test_is_accent_and_case_insensitive():
    config = FakeDisambiguationConfig("¿centro del pecho o un lado?")
    node = make_pectus_poland_guard_node(config)

    result = await node(_state(translated_query="TENGO EL ESTERNÓN HUNDIDO"))

    assert result == {"pectus_poland_guard_triggered": False}


async def test_falls_back_to_user_question_when_translated_query_is_missing():
    config = FakeDisambiguationConfig("¿centro del pecho o un lado?")
    node = make_pectus_poland_guard_node(config)

    result = await node(_state(translated_query=None, user_question="tengo el pecho hundido"))

    assert result == {"pectus_poland_guard_triggered": True, "final_answer": "¿centro del pecho o un lado?"}


def test_route_after_guard_goes_to_enforce_language_when_triggered():
    assert route_after_pectus_poland_guard({"pectus_poland_guard_triggered": True}) == "enforce_language"


def test_route_after_guard_continues_to_generate_with_tools_when_not_triggered():
    assert route_after_pectus_poland_guard({"pectus_poland_guard_triggered": False}) == "generate_with_tools"
    assert route_after_pectus_poland_guard({}) == "generate_with_tools"
