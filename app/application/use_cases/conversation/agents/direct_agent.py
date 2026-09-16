from app.application.ports.advisor_available_reply_config_repository_port import (
    AdvisorAvailableReplyConfigRepositoryPort,
)
from app.application.use_cases.conversation.nodes import NodeFn
from app.application.use_cases.conversation.state import ConversationState

# Reached only when the orchestrator already confirmed business hours are
# open (route="direct" is only set when check_business_availability
# returned True) -- this node just returns the canned "click the advisor
# button" reply, no further check needed.


def make_direct_agent_node(advisor_available_reply_config: AdvisorAvailableReplyConfigRepositoryPort) -> NodeFn:
    async def direct_agent_node(state: ConversationState) -> dict:
        reply = await advisor_available_reply_config.get_reply(state["tenant_id"])
        return {"final_answer": reply}

    return direct_agent_node
