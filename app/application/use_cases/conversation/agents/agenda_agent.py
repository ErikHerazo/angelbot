from app.application.ports.agenda_reply_config_repository_port import AgendaReplyConfigRepositoryPort
from app.application.use_cases.conversation.nodes import NodeFn
from app.application.use_cases.conversation.state import ConversationState

# TODO: real online booking. This is the same deliberate stub the diagram's
# agenda_agent branch was designed as before (see CLAUDE.md's LangGraph
# migration notes) -- returns tenant canned copy pointing to the manual
# booking link, not an actual scheduling integration.


def make_agenda_agent_node(agenda_reply_config: AgendaReplyConfigRepositoryPort) -> NodeFn:
    async def agenda_agent_node(state: ConversationState) -> dict:
        reply = await agenda_reply_config.get_reply(state["tenant_id"])
        return {"final_answer": reply}

    return agenda_agent_node
