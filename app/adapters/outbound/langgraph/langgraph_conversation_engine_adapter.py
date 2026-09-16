from typing import Awaitable, Callable, Optional

from app.core.logging.structured_logger import get_logger

log = get_logger(__name__)


class LangGraphConversationEngineAdapter:
    """Implements ConversationEnginePort by running the LangGraph
    orchestrator + 4-branch StateGraph (see application/use_cases/conversation/).

    `get_graph` is injected rather than built inline because most of the
    graph's dependencies (retrieval_tools, the price/greeting-style config
    ports) are tenant-bound at construction, but generate_reply only receives
    tenant_id per call -- same "build once per tenant, not once per message"
    problem already solved for the price-lookup tool in composition_root.py's
    per-tenant cache, reused the same way here.
    """

    def __init__(self, *, get_graph: Callable[[str], Awaitable[object]]):
        self._get_graph = get_graph

    async def generate_reply(
        self,
        *,
        tenant_id: str,
        session_id: str,
        user_question: str,
        channel: str,
        visitor_language: Optional[str] = None,
    ) -> str:
        with log.operation(tenant_id=tenant_id, session_id=session_id, channel=channel):
            graph = await self._get_graph(tenant_id)

            result = await graph.ainvoke(
                {
                    "tenant_id": tenant_id,
                    "session_id": session_id,
                    "channel": channel,
                    "user_question": user_question,
                    "visitor_language": visitor_language,
                }
            )
            return result.get("final_answer", "")
