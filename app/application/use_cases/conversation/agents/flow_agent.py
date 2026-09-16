from app.application.ports.flow_confirmation_reply_config_repository_port import (
    FlowConfirmationReplyConfigRepositoryPort,
)
from app.application.use_cases.conversation.nodes import NodeFn
from app.application.use_cases.conversation.state import ConversationState

# Reached when the orchestrator routed to "hablar_con_asesor" but business
# hours are closed (check_business_availability returned False) -- asks the
# user to confirm contact details in-chat so a human can follow up later.
# No backend action is taken here; same as the legacy behavior this ports
# forward (see CLAUDE.md's LangGraph migration notes, flow_agent_node).


def make_flow_agent_node(flow_confirmation_reply_config: FlowConfirmationReplyConfigRepositoryPort) -> NodeFn:
    async def flow_agent_node(state: ConversationState) -> dict:
        reply = await flow_confirmation_reply_config.get_reply(state["tenant_id"])
        return {"final_answer": reply}

    return flow_agent_node
