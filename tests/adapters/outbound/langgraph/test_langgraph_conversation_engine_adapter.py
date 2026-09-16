from app.adapters.outbound.langgraph.langgraph_conversation_engine_adapter import (
    LangGraphConversationEngineAdapter,
)


class FakeGraph:
    def __init__(self, final_answer: str):
        self._final_answer = final_answer
        self.invoked_with = None

    async def ainvoke(self, initial_state):
        self.invoked_with = initial_state
        return {"final_answer": self._final_answer, "route": "retrieval"}


async def test_generate_reply_invokes_graph_and_returns_final_answer():
    graph = FakeGraph("la respuesta")
    built_for: list[str] = []

    async def get_graph(tenant_id):
        built_for.append(tenant_id)
        return graph

    adapter = LangGraphConversationEngineAdapter(get_graph=get_graph)

    answer = await adapter.generate_reply(
        tenant_id="agb",
        session_id="s1",
        user_question="hola",
        channel="website",
        visitor_language="es",
    )

    assert answer == "la respuesta"
    assert built_for == ["agb"]
    assert graph.invoked_with == {
        "tenant_id": "agb",
        "session_id": "s1",
        "channel": "website",
        "user_question": "hola",
        "visitor_language": "es",
    }


async def test_generate_reply_defaults_to_empty_string_when_no_final_answer():
    class EmptyGraph:
        async def ainvoke(self, state):
            return {"route": "flow"}

    async def get_graph(tenant_id):
        return EmptyGraph()

    adapter = LangGraphConversationEngineAdapter(get_graph=get_graph)

    answer = await adapter.generate_reply(
        tenant_id="agb", session_id="s1", user_question="hola", channel="website"
    )

    assert answer == ""
