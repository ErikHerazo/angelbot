from app.application.use_cases.conversation.minor_patient_guard import (
    make_minor_patient_guard_node,
    route_after_minor_patient_guard,
)


class FakeDeferralConfig:
    def __init__(self, reply: str):
        self._reply = reply
        self.calls = []

    async def get_reply(self, tenant_id):
        self.calls.append(tenant_id)
        return self._reply


def _state(translated_query=None, user_question="hola", history=None):
    return {
        "tenant_id": "agb",
        "translated_query": translated_query,
        "user_question": user_question,
        "history": history or [],
    }


async def test_triggers_when_current_message_mentions_an_age_under_16():
    config = FakeDeferralConfig("hay que valorarlo con un especialista")
    node = make_minor_patient_guard_node(config)

    result = await node(_state(translated_query="tengo 15 años y quiero un aumento de labios"))

    assert result == {
        "minor_patient_guard_triggered": True,
        "final_answer": "hay que valorarlo con un especialista",
        "patient_age": 15,
    }
    assert config.calls == ["agb"]


async def test_triggers_when_the_age_was_mentioned_in_a_previous_turn():
    config = FakeDeferralConfig("hay que valorarlo con un especialista")
    node = make_minor_patient_guard_node(config)

    history = [
        {"role": "user", "content": "quiero un aumento de labios"},
        {"role": "assistant", "content": "¿qué edad tienes?"},
        {"role": "user", "content": "tengo 15 años"},
    ]
    result = await node(_state(translated_query="cuanto cuesta", history=history))

    assert result["minor_patient_guard_triggered"] is True
    assert config.calls == ["agb"]


async def test_does_not_trigger_for_age_16_or_above():
    config = FakeDeferralConfig("hay que valorarlo con un especialista")
    node = make_minor_patient_guard_node(config)

    result = await node(_state(translated_query="tengo 16 años y quiero un aumento de labios"))

    assert result == {"minor_patient_guard_triggered": False, "patient_age": 16}
    assert config.calls == []


async def test_does_not_trigger_for_adult_ages():
    config = FakeDeferralConfig("hay que valorarlo con un especialista")
    node = make_minor_patient_guard_node(config)

    result = await node(_state(translated_query="tengo 34 años, cuanto cuesta una rinoplastia"))

    assert result == {"minor_patient_guard_triggered": False, "patient_age": 34}
    assert config.calls == []


async def test_does_not_trigger_when_no_age_is_mentioned():
    config = FakeDeferralConfig("hay que valorarlo con un especialista")
    node = make_minor_patient_guard_node(config)

    result = await node(_state(translated_query="cuanto cuesta una rinoplastia"))

    assert result == {"minor_patient_guard_triggered": False, "patient_age": None}
    assert config.calls == []


async def test_falls_back_to_user_question_when_translated_query_is_missing():
    config = FakeDeferralConfig("hay que valorarlo con un especialista")
    node = make_minor_patient_guard_node(config)

    result = await node(_state(translated_query=None, user_question="mi hija tiene 14 años"))

    assert result["minor_patient_guard_triggered"] is True


def test_route_after_guard_goes_to_enforce_language_when_triggered():
    assert route_after_minor_patient_guard({"minor_patient_guard_triggered": True}) == "enforce_language"


def test_route_after_guard_continues_to_pectus_poland_guard_when_not_triggered():
    assert route_after_minor_patient_guard({"minor_patient_guard_triggered": False}) == "pectus_poland_guard"
    assert route_after_minor_patient_guard({}) == "pectus_poland_guard"
