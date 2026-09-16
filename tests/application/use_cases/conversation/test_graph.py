from app.application.use_cases.conversation.graph import build_conversation_graph
from tests.application.use_cases.conversation.fakes import (
    FakeCannedReplyConfig,
    FakeCheckBusinessAvailability,
    FakeConversationHistory,
    FakeLLM,
    FakePromptConfig,
    FakeReplyLanguageEnforcer,
    FakeReplyLanguageResolver,
    FakeRetrievalTools,
    FakeTranslation,
)


def _tool_call_response(intent: str, call_id="c1"):
    return {"content": None, "tool_calls": [{"id": call_id, "name": "classify_intent", "arguments": {"intent": intent}}]}


def _build_graph(*, llm, check_available=True, retrieval_call_result=None):
    return build_conversation_graph(
        llm=llm,
        conversation_history=FakeConversationHistory(),
        reply_language_resolver=FakeReplyLanguageResolver(),
        reply_language_enforcer=FakeReplyLanguageEnforcer(),
        translation=FakeTranslation(),
        prompt_config=FakePromptConfig(),
        retrieval_tools=FakeRetrievalTools(call_result=retrieval_call_result),
        check_business_availability=FakeCheckBusinessAvailability(check_available),
        advisor_available_reply_config=FakeCannedReplyConfig("habla con un asesor"),
        agenda_reply_config=FakeCannedReplyConfig("agenda aqui"),
        flow_confirmation_reply_config=FakeCannedReplyConfig("confirma tus datos"),
        max_history=6,
    )


def _initial_state(question="hola"):
    return {
        "tenant_id": "agb",
        "session_id": "s1",
        "channel": "website",
        "user_question": question,
        "visitor_language": None,
    }


async def test_route_retrieval_without_tool_calls():
    llm = FakeLLM(
        [
            _tool_call_response("info_general"),
            {"content": "no debería usarse", "tool_calls": None},  # generate_with_tools
            {"content": "respuesta final", "tool_calls": None},  # generate_final
        ]
    )
    graph = _build_graph(llm=llm)

    result = await graph.ainvoke(_initial_state())

    assert result["route"] == "retrieval"
    assert result["final_answer"] == "respuesta final"
    assert len(llm.calls) == 3


async def test_route_retrieval_with_one_tool_call():
    llm = FakeLLM(
        [
            _tool_call_response("info_general"),
            {
                "content": None,
                "tool_calls": [{"id": "t1", "name": "search_price_catalog", "arguments": {"query": "nariz"}}],
            },
            {"content": None, "tool_calls": None},  # after tool result, no more calls
            {"content": "el precio es 5000 euros", "tool_calls": None},  # generate_final
        ]
    )
    graph = _build_graph(llm=llm, retrieval_call_result=[{"procedure_name": "RINOPLASTIA", "price_range_eur": "5000"}])

    result = await graph.ainvoke(_initial_state("cuanto cuesta la rinoplastia"))

    assert result["route"] == "retrieval"
    assert result["final_answer"] == "el precio es 5000 euros"
    assert len(llm.calls) == 4
    # Tool result message made it into the running message list.
    tool_messages = [m for m in result["messages"] if m.get("role") == "tool"]
    assert len(tool_messages) == 1
    assert "RINOPLASTIA" in tool_messages[0]["content"]


async def test_route_agenda():
    llm = FakeLLM([_tool_call_response("agendar_cita")])
    graph = _build_graph(llm=llm)

    result = await graph.ainvoke(_initial_state("quiero agendar una cita"))

    assert result["route"] == "agenda"
    assert result["final_answer"] == "agenda aqui"
    assert len(llm.calls) == 1


async def test_route_direct_when_advisor_available():
    llm = FakeLLM([_tool_call_response("hablar_con_asesor")])
    graph = _build_graph(llm=llm, check_available=True)

    result = await graph.ainvoke(_initial_state("quiero hablar con un asesor"))

    assert result["route"] == "direct"
    assert result["final_answer"] == "habla con un asesor"


async def test_route_flow_when_advisor_unavailable():
    llm = FakeLLM([_tool_call_response("hablar_con_asesor")])
    graph = _build_graph(llm=llm, check_available=False)

    result = await graph.ainvoke(_initial_state("quiero hablar con un asesor"))

    assert result["route"] == "flow"
    assert result["final_answer"] == "confirma tus datos"


async def test_defaults_to_info_general_when_no_tool_call_returned():
    llm = FakeLLM(
        [
            {"content": "sin tool call", "tool_calls": None},  # orchestrator didn't call classify_intent
            {"content": None, "tool_calls": None},
            {"content": "respuesta", "tool_calls": None},
        ]
    )
    graph = _build_graph(llm=llm)

    result = await graph.ainvoke(_initial_state())

    assert result["route"] == "retrieval"
