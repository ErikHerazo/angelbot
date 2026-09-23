from app.application.use_cases.conversation.agents.retrieval_agent import make_generate_with_tools_node
from tests.application.use_cases.conversation.fakes import FakeLLM, FakePromptConfig, FakeRetrievalTools


def _state(**overrides):
    state = {
        "tenant_id": "agb",
        "channel": "website",
        "reply_language": "Español",
        "history": [],
        "translated_query": "cuanto cuesta un aumento de labios",
        "user_question": "cuanto cuesta un aumento de labios",
    }
    state.update(overrides)
    return state


async def test_no_age_note_injected_when_patient_age_is_unknown():
    llm = FakeLLM([{"content": "respuesta", "tool_calls": None}])
    node = make_generate_with_tools_node(
        llm=llm, prompt_config=FakePromptConfig(), retrieval_tools=FakeRetrievalTools()
    )

    await node(_state())

    system_message = llm.calls[0]["messages"][0]
    assert system_message["role"] == "system"
    assert "NOTA DEL SISTEMA" not in system_message["content"]


async def test_no_age_note_injected_for_an_adult():
    llm = FakeLLM([{"content": "respuesta", "tool_calls": None}])
    node = make_generate_with_tools_node(
        llm=llm, prompt_config=FakePromptConfig(), retrieval_tools=FakeRetrievalTools()
    )

    await node(_state(patient_age=34))

    system_message = llm.calls[0]["messages"][0]
    assert "NOTA DEL SISTEMA" not in system_message["content"]


async def test_age_note_injected_for_16_and_17_year_olds():
    for age in (16, 17):
        llm = FakeLLM([{"content": "respuesta", "tool_calls": None}])
        node = make_generate_with_tools_node(
            llm=llm, prompt_config=FakePromptConfig(), retrieval_tools=FakeRetrievalTools()
        )

        await node(_state(patient_age=age))

        system_message = llm.calls[0]["messages"][0]
        assert "NOTA DEL SISTEMA" in system_message["content"]
        assert f"{age} años NO es menor de 16 años" in system_message["content"]


async def test_no_age_note_injected_for_a_minor_under_16_already_handled_by_the_guard():
    # No debería llegar aquí en la práctica (minor_patient_guard corta antes),
    # pero si llegara, no tiene sentido reforzar "puedes dar la información".
    llm = FakeLLM([{"content": "respuesta", "tool_calls": None}])
    node = make_generate_with_tools_node(
        llm=llm, prompt_config=FakePromptConfig(), retrieval_tools=FakeRetrievalTools()
    )

    await node(_state(patient_age=12))

    system_message = llm.calls[0]["messages"][0]
    assert "NOTA DEL SISTEMA" not in system_message["content"]
